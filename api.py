from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime, timedelta
from database import db
from models import MonitoringTarget, TargetType, ChangeDetection, User, UserCreate, UserLogin, UserResponse, Token
from config import Config
from auth import create_access_token, authenticate_user, get_current_active_user
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Content Monitoring API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Request models
class AddTargetRequest(BaseModel):
    url: HttpUrl
    target_type: TargetType
    frequency_minutes: int = 60
    name: Optional[str] = None

class UpdateTargetRequest(BaseModel):
    frequency_minutes: Optional[int] = None
    active: Optional[bool] = None
    name: Optional[str] = None

class UpdateNotificationPreferencesRequest(BaseModel):
    email_notifications: Optional[bool] = None
    console_notifications: Optional[bool] = None

# Database connection handled by global db instance

@app.post("/targets", response_model=dict)
async def add_target(request: AddTargetRequest, current_user: User = Depends(get_current_active_user)):
    """Add a new monitoring target"""
    try:
        # Create target without user_id
        target = MonitoringTarget(**request.model_dump())
        
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        # Check if user already has this target in their monitored list
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        if user_doc and str(target.url) in user_doc.get("monitored_targets", []):
            raise HTTPException(status_code=400, detail="Target already exists for this user")
        
        # Insert new target - convert URL to string for MongoDB
        target_dict = target.model_dump()
        target_dict['url'] = str(target_dict['url'])  # Convert Pydantic URL to string
        result = targets_collection.insert_one(target_dict)
        
        # Add target URL to user's monitored_targets list
        users_collection.update_one(
            {"email": current_user.email},
            {"$addToSet": {"monitored_targets": target_dict['url']}}
        )
        
        # Queue immediate monitoring task via Celery
        try:
            from celery_app import monitor_target_task
            monitor_target_task.delay(str(target.url))
            logger.info(f"Queued monitoring task for new target: {target.url}")
        except Exception as e:
            logger.warning(f"Failed to queue monitoring task: {e}")
        
        # Prepare response with serializable data
        response_target = {
            "url": target_dict['url'],
            "target_type": target_dict['target_type'],
            "frequency_minutes": target_dict['frequency_minutes'],
            "name": target_dict.get('name'),
            "active": target_dict['active'],
            "created_at": target_dict['created_at'].isoformat(),
            "last_checked": target_dict['last_checked'].isoformat() if target_dict.get('last_checked') else None
        }
        
        return {
            "id": str(result.inserted_id),
            "message": "Target added successfully",
            "target": response_target
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions (like 400 errors) without modification
        raise
    except Exception as e:
        import traceback
        logger.error(f"Failed to add target: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/targets", response_model=List[dict])
async def get_targets(current_user: User = Depends(get_current_active_user)):
    """Get all monitoring targets for the authenticated user"""
    try:
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        # Get user's monitored targets
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        monitored_urls = user_doc.get("monitored_targets", []) if user_doc else []
        
        # Only return targets that the user is monitoring
        query = {"url": {"$in": monitored_urls}} if monitored_urls else {"url": {"$in": []}}
        
        targets = list(targets_collection.find(query))
        
        # Convert ObjectId and datetime to string
        for target in targets:
            target["_id"] = str(target["_id"])
            if "created_at" in target:
                target["created_at"] = target["created_at"].isoformat()
            if "last_checked" in target and target["last_checked"]:
                target["last_checked"] = target["last_checked"].isoformat()
        
        return targets
        
    except Exception as e:
        logger.error(f"Failed to get targets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/targets/{target_url:path}")
async def remove_target(target_url: str, current_user: User = Depends(get_current_active_user)):
    """Remove a monitoring target"""
    try:
        logger.info(f"Attempting to remove target: {target_url}")
        
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        # Check if user has this target in their monitored list
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        if not user_doc or target_url not in user_doc.get("monitored_targets", []):
            raise HTTPException(status_code=404, detail="Target not found")
        
        # Remove target URL from user's monitored_targets list first
        users_collection.update_one(
            {"email": current_user.email},
            {"$pull": {"monitored_targets": target_url}}
        )
        
        # Check if any other users are monitoring this target
        other_users = users_collection.find_one({"monitored_targets": target_url})
        
        # Only delete the target from targets collection if no other users are monitoring it
        if not other_users:
            result = targets_collection.delete_one({"url": target_url})
        else:
            # Target is still being monitored by other users, so don't delete it
            result = type('MockResult', (), {'deleted_count': 1})()
        
        logger.info(f"Delete result for {target_url}: deleted_count={result.deleted_count}")
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Target not found")
        

        
        return {"message": "Target removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove target: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/targets/{target_url:path}")
async def update_target(target_url: str, request: UpdateTargetRequest, current_user: User = Depends(get_current_active_user)):
    """Update a monitoring target"""
    try:
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Check if user has this target in their monitored list
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        if not user_doc or target_url not in user_doc.get("monitored_targets", []):
            raise HTTPException(status_code=404, detail="Target not found")
        
        # Update the target
        result = targets_collection.update_one(
            {"url": target_url},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Target not found")
        
        return {"message": "Target updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update target: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/changes", response_model=List[dict])
async def get_changes(
    target_url: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_active_user)
):
    """Get recent changes for the authenticated user's targets"""
    try:
        changes_collection = db.get_collection(Config.CHANGES_COLLECTION)
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        # Get user's monitored target URLs
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        user_target_urls = user_doc.get("monitored_targets", []) if user_doc else []
        
        # Build query to only show changes for user's targets
        query = {"target_url": {"$in": user_target_urls}}
        if target_url:
            # Ensure the specific target_url belongs to the user
            if target_url not in user_target_urls:
                raise HTTPException(status_code=404, detail="Target not found")
            query["target_url"] = target_url
        
        changes = list(
            changes_collection
            .find(query)
            .sort("detected_at", -1)
            .skip(skip)
            .limit(limit)
        )
        
        # Convert ObjectId to string and datetime to ISO format
        for change in changes:
            change["_id"] = str(change["_id"])
            if "detected_at" in change:
                change["detected_at"] = change["detected_at"].isoformat()
        
        return changes
        
    except Exception as e:
        logger.error(f"Failed to get changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        
        # Check if user already exists
        existing_user = users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password strength
        if len(user_data.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        if len(user_data.password) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be no longer than 72 characters"
            )
        
        # Create new user
        hashed_password = User.get_password_hash(user_data.password)
        user_doc = {
            "email": user_data.email,
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "is_active": True,
            "notification_preferences": {
                "email_notifications": True,
                "console_notifications": True
            },
            "monitored_targets": [],
            "created_at": datetime.now()
        }
        
        result = users_collection.insert_one(user_doc)
        
        # Return user response (without password)
        return UserResponse(
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=True,
            created_at=user_doc["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/auth/login", response_model=Token)
async def login_user(user_credentials: UserLogin):
    """Login user and return access token"""
    try:
        user = authenticate_user(user_credentials.email, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to login user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return UserResponse(
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )

@app.get("/user/notification-preferences")
async def get_notification_preferences(current_user: User = Depends(get_current_active_user)):
    """Get user's notification preferences"""
    try:
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        user_doc = users_collection.find_one({"email": current_user.email})
        
        if user_doc and "notification_preferences" in user_doc:
            return user_doc["notification_preferences"]
        
        # Return default preferences
        return {
            "email_notifications": True,
            "console_notifications": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/user/notification-preferences")
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Update user's notification preferences"""
    try:
        users_collection = db.get_collection(Config.USERS_COLLECTION)
        
        # Get current preferences
        user_doc = users_collection.find_one({"email": current_user.email})
        current_prefs = user_doc.get("notification_preferences", {
            "email_notifications": True,
            "console_notifications": True
        }) if user_doc else {
            "email_notifications": True,
            "console_notifications": True
        }
        
        # Update only provided fields
        update_data = {}
        if request.email_notifications is not None:
            current_prefs["email_notifications"] = request.email_notifications
        if request.console_notifications is not None:
            current_prefs["console_notifications"] = request.console_notifications
        
        # Update in database
        result = users_collection.update_one(
            {"email": current_user.email},
            {"$set": {"notification_preferences": current_prefs}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "message": "Notification preferences updated successfully",
            "preferences": current_prefs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML"""
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)