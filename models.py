from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# Use system time instead of UTC
def get_current_time():
    return datetime.now()

class TargetType(str, Enum):
    LINKEDIN_PROFILE = "linkedin_profile"
    LINKEDIN_COMPANY = "linkedin_company"
    WEBSITE = "website"

class MonitoringTarget(BaseModel):
    url: HttpUrl
    target_type: TargetType
    frequency_minutes: int = 60  # Default check every hour
    user_id: str
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
    email: str
    notification_preferences: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=get_current_time)

class MonitoringState(BaseModel):
    target: MonitoringTarget
    current_content: Optional[str] = None
    previous_content: Optional[str] = None
    changes_detected: List[ChangeDetection] = []
    error: Optional[str] = None