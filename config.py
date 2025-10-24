import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI")
    REDIS_URL = os.getenv("REDIS_URL")
    
    # Email settings
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    
    # Database
    DATABASE_NAME = "monitoring_system"
    
    # Collections
    TARGETS_COLLECTION = "targets"
    CHANGES_COLLECTION = "changes"
    USERS_COLLECTION = "users"