import logging
from datetime import datetime, timedelta
from typing import List
from database import db
from models import MonitoringTarget
from config import Config

logger = logging.getLogger(__name__)

class SchedulerAgent:
    def __init__(self):
        self.targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
    
    def get_targets_to_monitor(self) -> List[MonitoringTarget]:
        """Get targets that need to be monitored based on their schedule"""
        try:
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
            
            # Find targets that are due for monitoring
            # Calculate time threshold for each frequency
            query = {"active": True}
            
            # Get all active targets and filter in Python for better readability
            all_targets = list(self.targets_collection.find(query))
            due_targets = []
            
            logger.debug(f"Checking {len(all_targets)} active targets for monitoring")
            
            for target_data in all_targets:
                frequency_minutes = target_data.get('frequency_minutes', 60)
                last_checked = target_data.get('last_checked')
                target_url = target_data.get('url', 'unknown')
                
                logger.debug(f"Target {target_url}: frequency={frequency_minutes}min, last_checked={last_checked}")
                
                # Never checked or due for check
                if not last_checked:
                    logger.debug(f"Target {target_url} never checked, adding to due list")
                    due_targets.append(target_data)
                else:
                    # Ensure last_checked is timezone-aware
                    if last_checked.tzinfo is None:
                        last_checked = last_checked.replace(tzinfo=timezone.utc)
                    
                    next_check_time = last_checked + timedelta(minutes=frequency_minutes)
                    logger.debug(f"Target {target_url}: next check at {next_check_time}, current time {current_time}")
                    
                    if current_time >= next_check_time:
                        logger.debug(f"Target {target_url} is due for monitoring")
                        due_targets.append(target_data)
                    else:
                        time_until_due = (next_check_time - current_time).total_seconds()
                        logger.debug(f"Target {target_url} not due yet, {time_until_due} seconds remaining")
            
            targets = []
            
            for target_data in due_targets:
                try:
                    # Convert MongoDB document to Pydantic model
                    target_data['_id'] = str(target_data['_id'])
                    target = MonitoringTarget(**target_data)
                    targets.append(target)
                except Exception as e:
                    logger.error(f"Failed to parse target {target_data.get('url')}: {e}")
            
            logger.debug(f"Found {len(targets)} targets ready for monitoring")
            return targets
            
        except Exception as e:
            logger.error(f"Failed to get targets to monitor: {e}")
            return []
    
    def update_last_checked(self, target_url: str):
        """Update the last_checked timestamp for a target"""
        try:
            from datetime import timezone
            self.targets_collection.update_one(
                {"url": target_url},
                {"$set": {"last_checked": datetime.now(timezone.utc)}}
            )
            logger.debug(f"Updated last_checked for {target_url}")
        except Exception as e:
            logger.error(f"Failed to update last_checked for {target_url}: {e}")