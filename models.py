from pydantic import BaseModel, HttpUrl, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import bcrypt

# Use system time instead of UTC
def get_current_time():
    return datetime.now()

# Password hashing functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Ensure password is within bcrypt limits (72 bytes)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

class TargetType(str, Enum):
    LINKEDIN_PROFILE = "linkedin_profile"
    LINKEDIN_COMPANY = "linkedin_company"
    WEBSITE = "website"

class MonitoringTarget(BaseModel):
    url: HttpUrl
    target_type: TargetType
    frequency_minutes: int = 60  # Default check every hour
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=get_current_time)
    last_checked: Optional[datetime] = None
    active: bool = True

class ChangeDetection(BaseModel):
    target_id: str
    target_url: str
    change_type: str
    summary: str
    before_content: Optional[str] = None
    after_content: Optional[str] = None
    detected_at: datetime = Field(default_factory=get_current_time)
    
class User(BaseModel):
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    notification_preferences: Dict[str, Any] = {
        "email_notifications": True,
        "console_notifications": True
    }
    monitored_targets: List[str] = []  # List of target URLs this user is monitoring
    created_at: datetime = Field(default_factory=get_current_time)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return verify_password(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return hash_password(password)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class MonitoringState(BaseModel):
    target: MonitoringTarget
    current_content: Optional[str] = None
    previous_content: Optional[str] = None
    changes_detected: List[ChangeDetection] = []
    error: Optional[str] = None