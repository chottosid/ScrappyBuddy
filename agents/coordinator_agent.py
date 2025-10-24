import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from models import MonitoringTarget, ChangeDetection
from workflows.monitoring_workflow import monitoring_workflow
from agents.scheduler_agent import SchedulerAgent
from database import db
from config import Config

logger = logging.getLogger(__name__)

class CoordinatorAgent:
    """
    Coordinator agent that orchestrates monitoring using LangGraph workflows
    """
    def __init__(self):
        self.scheduler = SchedulerAgent()
        self.workflow = monitoring_workflow
        
        self.changes_collection = db.get_collection(Config.CHANGES_COLLECTION)
        self.targets_collection = db.get_collection(Config.TARGETS_COLLECTION)

    
    def monitor_target(self, target_data: Dict[str, Any], previous_content: str = None) -> Dict[str, Any]:
        """Monitor a single target using LangGraph workflow"""
        
        try:
            logger.info(f"Starting LangGraph monitoring for {target_data['url']}")
            
            # Run the LangGraph workflow
            result = self.workflow.run_monitoring_sync(target_data, previous_content)
            
            logger.info(f"LangGraph workflow completed for {target_data['url']}: success={result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"LangGraph workflow failed for {target_data['url']}: {e}")
            return {
                "workflow_id": "unknown",
                "target_url": target_data["url"],
                "success": False,
                "error": str(e),
                "changes_detected": [],
                "current_content": None,
                "step": "coordinator_failed",
                "retry_count": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
    
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle for all due targets using LangGraph"""
        
        logger.info("Starting monitoring cycle with LangGraph workflows")
        
        targets = self.scheduler.get_targets_to_monitor()
        
        if not targets:
            logger.info("No targets due for monitoring")
            return
        
        logger.info(f"Found {len(targets)} targets due for monitoring")
        
        results = []
        
        for target in targets:
            try:
                logger.info(f"Processing target: {target.url}")
                
                # Convert MonitoringTarget to dict for workflow
                target_data = {
                    "url": str(target.url),
                    "target_type": target.target_type.value,
                    "frequency_minutes": target.frequency_minutes,
                    "name": target.name
                }
                
                # Get previous content for comparison
                previous_content = self._get_previous_content(str(target.url))
                
                # Run LangGraph workflow
                result = self.monitor_target(target_data, previous_content)
                
                # Store current content for next comparison if successful
                if result["success"] and result.get("current_content"):
                    self._store_current_content(str(target.url), result["current_content"])
                
                # Update last checked timestamp
                self.scheduler.update_last_checked(str(target.url))
                
                results.append(result)
                
                if result["success"]:
                    changes_count = len(result.get("changes_detected", []))
                    logger.info(f"Successfully monitored {target.url}: {changes_count} changes detected")
                else:
                    logger.error(f"Failed to monitor {target.url}: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Failed to monitor {target.url}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                results.append({
                    "workflow_id": "unknown",
                    "target_url": str(target.url),
                    "success": False,
                    "error": str(e),
                    "changes_detected": [],
                    "current_content": None,
                    "step": "cycle_failed",
                    "retry_count": 0,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                })
        
        # Log summary
        successful = sum(1 for r in results if r["success"])
        total_changes = sum(len(r.get("changes_detected", [])) for r in results)
        
        logger.info(f"Monitoring cycle completed: {successful}/{len(results)} targets successful, {total_changes} total changes detected")

    
    def _get_previous_content(self, target_url: str) -> str:
        """Get the last stored content for a target"""
        try:
            # Get stored content from targets collection
            targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
            # Convert URL to string if it's a Pydantic URL object
            url_str = str(target_url)
            target = targets_collection.find_one({"url": url_str})
            
            if target and target.get("last_content"):
                return target["last_content"]
            return ""
            
        except Exception as e:
            logger.error(f"Failed to get previous content for {target_url}: {e}")
            return ""
    
    def _store_current_content(self, target_url: str, content: str):
        """Store current content for future comparison"""
        try:
            # Store content snapshot in targets collection for next comparison
            targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
            # Convert URL to string if it's a Pydantic URL object
            url_str = str(target_url)
            targets_collection.update_one(
                {"url": url_str},
                {"$set": {"last_content": content}}
            )

        except Exception as e:
            logger.error(f"Failed to store content for {target_url}: {e}")