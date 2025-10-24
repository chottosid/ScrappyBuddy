"""
LangGraph-native notifier node
Handles notifications for detected changes with multiple delivery methods
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from langchain_core.messages import AIMessage

from models import MonitoringWorkflowState
from config import Config
from database import db

logger = logging.getLogger(__name__)

def notifier_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState:
    """
    LangGraph node for sending notifications about detected changes
    
    Args:
        state: Current workflow state with detected changes
        
    Returns:
        Updated state with notification results
    """
    target_url = state["target_url"]
    changes_detected = state.get("changes_detected", [])
    
    logger.info(f"Processing notifications for {target_url}")
    
    try:
        if not changes_detected:
            logger.info(f"No changes to notify for {target_url}")
            state["step"] = "notification_skipped"
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            return state
        
        # Get users monitoring this target
        users_monitoring_target = _get_users_monitoring_target(target_url)
        
        if not users_monitoring_target:
            logger.warning(f"No users monitoring target: {target_url}")
            state["step"] = "notification_no_users"
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            return state
        
        notification_results = []
        
        # Send notifications to each user
        for user_data in users_monitoring_target:
            user_email = user_data.get('email')
            user_preferences = user_data.get('notification_preferences', {})
            
            user_notifications = []
            
            # Process each change for this user
            for change in changes_detected:
                # Console notification
                if user_preferences.get("console_notifications", True):
                    console_result = _send_console_notification(change, user_email)
                    user_notifications.append(console_result)
                
                # Email notification
                if user_preferences.get("email_notifications", True):
                    email_result = _send_email_notification(change, user_email)
                    user_notifications.append(email_result)
            
            notification_results.append({
                "user_email": user_email,
                "notifications_sent": len(user_notifications),
                "results": user_notifications
            })
        
        # Update state with results
        state["step"] = "notification_completed"
        state["notification_results"] = notification_results
        
        total_notifications = sum(len(r["results"]) for r in notification_results)
        
        # Add success message
        success_message = AIMessage(
            content=f"Sent {total_notifications} notifications to {len(users_monitoring_target)} users for changes in {target_url}"
        )
        state["messages"] = state.get("messages", []) + [success_message]
        
        logger.info(f"Sent {total_notifications} notifications for {target_url}")
        
    except Exception as e:
        error_msg = f"Failed to send notifications for {target_url}: {str(e)}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "notification_failed"
    
    finally:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return state

def _get_users_monitoring_target(target_url: str) -> List[Dict[str, Any]]:
    """Get all users who are monitoring this target"""
    try:
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

def _send_console_notification(change: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    """Send console notification"""
    try:
        # Parse datetime if it's a string
        detected_at = change.get("detected_at")
        if isinstance(detected_at, str):
            try:
                detected_at = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
            except:
                detected_at = datetime.now(timezone.utc)
        elif not detected_at:
            detected_at = datetime.now(timezone.utc)
        
        print("\n" + "="*60)
        print("🔔 CHANGE DETECTED")
        print("="*60)
        print(f"User: {user_email}")
        print(f"Source: {change['target_url']}")
        print(f"Type: {change['change_type']}")
        print(f"Time: {detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Summary: {change['summary']}")
        print("="*60 + "\n")
        
        return {
            "type": "console",
            "success": True,
            "message": "Console notification sent"
        }
        
    except Exception as e:
        logger.error(f"Failed to send console notification: {e}")
        return {
            "type": "console",
            "success": False,
            "error": str(e)
        }

def _send_email_notification(change: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    """Send email notification"""
    try:
        # Check if SMTP is configured
        smtp_configured = all([
            Config.SMTP_HOST,
            Config.SMTP_USER,
            Config.SMTP_PASSWORD
        ])
        
        if not smtp_configured:
            return {
                "type": "email",
                "success": False,
                "error": "SMTP not configured"
            }
        
        # Parse datetime if it's a string
        detected_at = change.get("detected_at")
        if isinstance(detected_at, str):
            try:
                detected_at = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
            except:
                detected_at = datetime.now(timezone.utc)
        elif not detected_at:
            detected_at = datetime.now(timezone.utc)
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = Config.SMTP_USER
        msg['To'] = user_email
        msg['Subject'] = f"Change Detected: {change['target_url']}"
        
        body = f"""
        A change has been detected in your monitored content:
        
        Source: {change['target_url']}
        Type: {change['change_type']}
        Time: {detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
        
        Summary:
        {change['summary']}
        
        ---
        Content Monitoring System
        
        You're receiving this because you're monitoring this URL. 
        To manage your monitoring targets, visit your dashboard.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent to {user_email}")
        
        return {
            "type": "email",
            "success": True,
            "message": f"Email sent to {user_email}"
        }
        
    except Exception as e:
        logger.error(f"Failed to send email notification to {user_email}: {e}")
        return {
            "type": "email",
            "success": False,
            "error": str(e)
        }