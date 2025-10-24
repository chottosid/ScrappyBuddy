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
                logger.info("No changes to notify")
                return state
            
            for change in state.changes_detected:
                # Console notification (always available)
                self._console_notification(change)
                
                # Email notification (if configured)
                if self.smtp_configured:
                    self._email_notification(change)
                
            logger.info(f"Sent notifications for {len(state.changes_detected)} changes")
            
        except Exception as e:
            error_msg = f"Failed to send notifications: {str(e)}"
            logger.error(error_msg)
            state.error = error_msg
            
        return state
    
    def _console_notification(self, change: ChangeDetection):
        """Print notification to console"""
        print("\n" + "="*60)
        print("🔔 CHANGE DETECTED")
        print("="*60)
        print(f"Source: {change.target_url}")
        print(f"Type: {change.change_type}")
        print(f"Time: {change.detected_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Summary: {change.summary}")
        print("="*60 + "\n")
    
    def _email_notification(self, change: ChangeDetection):
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.SMTP_USER
            msg['To'] = Config.SMTP_USER  # For now, send to self
            msg['Subject'] = f"Change Detected: {change.target_url}"
            
            body = f"""
            A change has been detected in your monitored content:
            
            Source: {change.target_url}
            Type: {change.change_type}
            Time: {change.detected_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Summary:
            {change.summary}
            
            ---
            Monitoring System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent for {change.target_url}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")