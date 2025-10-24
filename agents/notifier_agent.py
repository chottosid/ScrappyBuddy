import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from models import MonitoringState, ChangeDetection
from config import Config

logger = logging.getLogger(__name__)

class NotifierAgent:
    def __init__(self):
        self.smtp_configured = all([
            Config.SMTP_HOST,
            Config.SMTP_USER,
            Config.SMTP_PASSWORD
        ])
    
    def send_notifications(self, state: MonitoringState) -> MonitoringState:
        """Send notifications for detected changes"""
        try:
            if not state.changes_detected:
                return state
            
            # Get all users who are monitoring this target
            target_url = str(state.target.url).rstrip('/')  # Remove trailing slash for consistency
            users_monitoring_target = self._get_users_monitoring_target(target_url)
            
            if not users_monitoring_target:
                logger.warning(f"No users monitoring target: {target_url}")
                return state
            
            # Send notifications to each user monitoring this target
            for user_data in users_monitoring_target:
                user_email = user_data.get('email')
                user_preferences = user_data.get('notification_preferences', {})
                
                # Send one notification per user for all changes
                for change in state.changes_detected:
                    # Console notification (if user allows it)
                    if user_preferences.get("console_notifications", True):
                        self._console_notification(change, user_email)
                    
                    # Email notification (if configured and user allows it)
                    if (self.smtp_configured and 
                        user_preferences.get("email_notifications", True)):
                        self._email_notification(change, user_email)
            
            user_count = len(users_monitoring_target)
            change_count = len(state.changes_detected)
            
        except Exception as e:
            error_msg = f"Failed to send notifications: {str(e)}"
            logger.error(error_msg)
            state.error = error_msg
            
        return state
    
    def _console_notification(self, change: ChangeDetection, user_email: str):
        """Print notification to console"""
        print("\n" + "="*60)
        print("🔔 CHANGE DETECTED")
        print("="*60)
        print(f"User: {user_email}")
        print(f"Source: {change.target_url}")
        print(f"Type: {change.change_type}")
        print(f"Time: {change.detected_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Summary: {change.summary}")
        print("="*60 + "\n")
    
    def _email_notification(self, change: ChangeDetection, user_email: str):
        """Send email notification to the user who owns the target"""
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.SMTP_USER
            msg['To'] = user_email
            msg['Subject'] = f"Change Detected: {change.target_url}"
            
            body = f"""
            A change has been detected in your monitored content:
            
            Source: {change.target_url}
            Type: {change.change_type}
            Time: {change.detected_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Summary:
            {change.summary}
            
            ---
            Content Monitoring System
            
            You're receiving this because you're monitoring this URL. 
            To manage your monitoring targets, visit your dashboard.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent to {user_email} for {change.target_url}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification to {user_email}: {e}")
    
    def _get_users_monitoring_target(self, target_url: str) -> List[dict]:
        """Get all users who are monitoring this target"""
        try:
            from database import db
            from config import Config
            
            users_collection = db.get_collection(Config.USERS_COLLECTION)
            
            # Find all users who have this target URL in their monitored_targets list
            users = list(users_collection.find({
                "monitored_targets": target_url,
                "is_active": True
            }))
            
            return users
            
        except Exception as e:
            logger.error(f"Failed to get users monitoring target {target_url}: {e}")
            return []