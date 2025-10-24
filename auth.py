from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import User, TokenData
from database import db
from config import Config
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = Config.JWT_SECRET_KEY if hasattr(Config, 'JWT_SECRET_KEY') else "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    return token_data

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get the current authenticated user"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    users_collection = db.get_collection(Config.USERS_COLLECTION)
    user_doc = users_collection.find_one({"email": token_data.email})
    
    if user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Convert MongoDB document to User model
    user = User(
        email=user_doc["email"],
        hashed_password=user_doc["hashed_password"],
        full_name=user_doc.get("full_name"),
        is_active=user_doc.get("is_active", True),
        notification_preferences=user_doc.get("notification_preferences", {}),
        created_at=user_doc["created_at"]
    )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password"""
    users_collection = db.get_collection(Config.USERS_COLLECTION)
    user_doc = users_collection.find_one({"email": email})
    
    if not user_doc:
        return None
    
    user = User(
        email=user_doc["email"],
        hashed_password=user_doc["hashed_password"],
        full_name=user_doc.get("full_name"),
        is_active=user_doc.get("is_active", True),
        notification_preferences=user_doc.get("notification_preferences", {}),
        created_at=user_doc["created_at"]
    )
    
    if not User.verify_password(password, user.hashed_password):
        return None
    
    return user