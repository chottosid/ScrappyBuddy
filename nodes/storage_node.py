"""
LangGraph-native storage node
Handles data persistence and state updates
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from langchain_core.messages import AIMessage

from models import MonitoringWorkflowState
from config import Config
from database import db

logger = logging.getLogger(__name__)

def storage_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState:
    """
    LangGraph node for storing monitoring results and updating target state
    
    Args:
        state: Current workflow state with results to store
        
    Returns:
        Updated state with storage results
    """
    target_url = state["target_url"]
    current_content = state.get("current_content")
    changes_detected = state.get("changes_detected", [])
    
    logger.info(f"Storing results for {target_url}")
    
    try:
        storage_results = []
        
        # Store detected changes
        if changes_detected:
            changes_collection = db.get_collection(Config.CHANGES_COLLECTION)
            
            for change in changes_detected:
                # Ensure proper datetime format
                if isinstance(change.get("detected_at"), str):
                    try:
                        change["detected_at"] = datetime.fromisoformat(
                            change["detected_at"].replace('Z', '+00:00')
                        )
                    except:
                        change["detected_at"] = datetime.now(timezone.utc)
                
                # Insert change record
                result = changes_collection.insert_one(change)
                storage_results.append({
                    "type": "change_record",
                    "id": str(result.inserted_id),
                    "success": True
                })
                
                logger.info(f"Stored change record {result.inserted_id} for {target_url}")
        
        # Update target with current content and last_checked timestamp
        if current_content:
            targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
            
            update_data = {
                "last_content": current_content,
                "last_checked": datetime.now(timezone.utc)
            }
            
            result = targets_collection.update_one(
                {"url": target_url},
                {"$set": update_data}
            )
            
            if result.matched_count > 0:
                storage_results.append({
                    "type": "target_update",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "success": True
                })
                logger.info(f"Updated target content and timestamp for {target_url}")
            else:
                logger.warning(f"No target found to update for {target_url}")
                storage_results.append({
                    "type": "target_update",
                    "success": False,
                    "error": "Target not found"
                })
        
        # Store workflow execution record for audit trail
        workflow_collection = db.get_collection("workflow_executions")
        
        workflow_record = {
            "workflow_id": state["workflow_id"],
            "target_url": target_url,
            "target_type": state["target_type"],
            "started_at": state["started_at"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "success": not bool(state.get("error")),
            "error": state.get("error"),
            "changes_count": len(changes_detected),
            "retry_count": state.get("retry_count", 0),
            "final_step": state.get("step", "unknown")
        }
        
        workflow_result = workflow_collection.insert_one(workflow_record)
        storage_results.append({
            "type": "workflow_record",
            "id": str(workflow_result.inserted_id),  # Convert ObjectId to string
            "success": True
        })
        
        # Update state with storage results
        state["step"] = "storage_completed"
        state["storage_results"] = storage_results
        
        # Add success message
        success_message = AIMessage(
            content=f"Successfully stored {len(changes_detected)} changes and updated target state for {target_url}"
        )
        state["messages"] = state.get("messages", []) + [success_message]
        
        logger.info(f"Storage completed for {target_url}: {len(storage_results)} operations")
        
    except Exception as e:
        error_msg = f"Failed to store results for {target_url}: {str(e)}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "storage_failed"
    
    finally:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return state