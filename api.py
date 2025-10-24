from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime
from database import db
from models import MonitoringTarget, TargetType, ChangeDetection
from config import Config
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
    user_id: str
    name: Optional[str] = None

class UpdateTargetRequest(BaseModel):
    frequency_minutes: Optional[int] = None
    active: Optional[bool] = None
    name: Optional[str] = None

# Database connection handled by global db instance

@app.post("/targets", response_model=dict)
async def add_target(request: AddTargetRequest):
    """Add a new monitoring target"""
    try:
        target = MonitoringTarget(**request.dict())
        
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        # Check if target already exists
        existing = targets_collection.find_one({"url": str(target.url)})
        if existing:
            raise HTTPException(status_code=400, detail="Target already exists")
        
        # Insert new target - convert URL to string for MongoDB
        target_dict = target.dict()
        target_dict['url'] = str(target_dict['url'])  # Convert Pydantic URL to string
        result = targets_collection.insert_one(target_dict)
        
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
            "user_id": target_dict['user_id'],
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
async def get_targets(user_id: Optional[str] = None):
    """Get all monitoring targets"""
    try:
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        query = {}
        if user_id:
            query["user_id"] = user_id
        
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
async def remove_target(target_url: str):
    """Remove a monitoring target"""
    try:
        logger.info(f"Attempting to remove target: {target_url}")
        
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        result = targets_collection.delete_one({"url": target_url})
        
        logger.info(f"Delete result for {target_url}: deleted_count={result.deleted_count}")
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Target not found")
        
        # Note: Celery tasks for removed targets will naturally stop when target is not found
        logger.info(f"Target {target_url} removed, future tasks will be skipped")
        
        return {"message": "Target removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove target: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/targets/{target_url:path}")
async def update_target(target_url: str, request: UpdateTargetRequest):
    """Update a monitoring target"""
    try:
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
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
    skip: int = 0
):
    """Get recent changes"""
    try:
        changes_collection = db.get_collection(Config.CHANGES_COLLECTION)
        
        query = {}
        if target_url:
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