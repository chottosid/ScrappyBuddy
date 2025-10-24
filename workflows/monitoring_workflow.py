"""
LangGraph-native monitoring workflow
Implements proper LangGraph architecture with state management, conditional routing, and error handling
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from models import MonitoringWorkflowState, ChangeDetection, TargetType
from nodes.scraper_node import scraper_node
from nodes.analyzer_node import analyzer_node
from nodes.notifier_node import notifier_node
from nodes.storage_node import storage_node
from database import db
from config import Config

logger = logging.getLogger(__name__)

class MonitoringWorkflow:
    """LangGraph-native monitoring workflow orchestrator"""
    
    def __init__(self):
        self.memory = MemorySaver()
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with proper state management and routing"""
        
        # Create the workflow graph
        workflow = StateGraph(MonitoringWorkflowState)
        
        # Add nodes
        workflow.add_node("scrape", scraper_node)
        workflow.add_node("analyze", analyzer_node)
        workflow.add_node("notify", notifier_node)
        workflow.add_node("store", storage_node)
        workflow.add_node("error_handler", self._error_handler_node)
        workflow.add_node("retry_handler", self._retry_handler_node)
        
        # Set entry point
        workflow.set_entry_point("scrape")
        
        # Add conditional edges with proper routing logic
        workflow.add_conditional_edges(
            "scrape",
            self._route_after_scrape,
            {
                "analyze": "analyze",
                "error": "error_handler",
                "retry": "retry_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "analyze",
            self._route_after_analyze,
            {
                "notify": "notify",
                "store": "store",  # No changes detected, skip notification
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "notify",
            self._route_after_notify,
            {
                "store": "store",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "store",
            self._route_after_store,
            {
                "end": END,
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "error_handler",
            self._route_after_error,
            {
                "retry": "retry_handler",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "retry_handler",
            self._route_after_retry,
            {
                "scrape": "scrape",
                "end": END
            }
        )
        
        return workflow.compile(checkpointer=self.memory)
    
    def _route_after_scrape(self, state: MonitoringWorkflowState) -> str:
        """Route after scraping based on success/failure"""
        if state.get("error"):
            if state.get("retry_count", 0) < 3:
                return "retry"
            return "error"
        
        if not state.get("current_content"):
            logger.warning(f"No content scraped for {state['target_url']}")
            return "error"
        
        return "analyze"
    
    def _route_after_analyze(self, state: MonitoringWorkflowState) -> str:
        """Route after analysis based on changes detected"""
        if state.get("error"):
            return "error"
        
        changes = state.get("changes_detected", [])
        if changes:
            return "notify"
        else:
            # No changes detected, skip notification
            return "store"
    
    def _route_after_notify(self, state: MonitoringWorkflowState) -> str:
        """Route after notification"""
        if state.get("error"):
            return "error"
        return "store"
    
    def _route_after_store(self, state: MonitoringWorkflowState) -> str:
        """Route after storage"""
        if state.get("error"):
            return "error"
        return "end"
    
    def _route_after_error(self, state: MonitoringWorkflowState) -> str:
        """Route after error handling"""
        retry_count = state.get("retry_count", 0)
        if retry_count < 3 and not state.get("fatal_error"):
            return "retry"
        return "end"
    
    def _route_after_retry(self, state: MonitoringWorkflowState) -> str:
        """Route after retry logic"""
        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            return "scrape"
        return "end"
    
    def _error_handler_node(self, state: MonitoringWorkflowState) -> MonitoringWorkflowState:
        """Handle errors and determine recovery strategy"""
        error = state.get("error", "Unknown error")
        retry_count = state.get("retry_count", 0)
        
        logger.error(f"Error in workflow for {state['target_url']}: {error}")
        
        # Add error message to conversation
        error_message = AIMessage(
            content=f"Error occurred: {error}. Retry count: {retry_count}"
        )
        
        state["messages"] = state.get("messages", []) + [error_message]
        state["step"] = "error_handled"
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Determine if error is fatal
        fatal_errors = [
            "invalid_url",
            "authentication_failed", 
            "rate_limited_permanently"
        ]
        
        if any(fatal in error.lower() for fatal in fatal_errors):
            state["fatal_error"] = True
        
        return state
    
    def _retry_handler_node(self, state: MonitoringWorkflowState) -> MonitoringWorkflowState:
        """Handle retry logic with exponential backoff"""
        retry_count = state.get("retry_count", 0)
        retry_count += 1
        
        logger.info(f"Retrying workflow for {state['target_url']}, attempt {retry_count}")
        
        # Add retry message
        retry_message = AIMessage(
            content=f"Retrying operation, attempt {retry_count}/3"
        )
        
        state["messages"] = state.get("messages", []) + [retry_message]
        state["retry_count"] = retry_count
        state["step"] = "retrying"
        state["error"] = None  # Clear previous error
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        return state
    
    def create_initial_state(self, target_data: Dict[str, Any], previous_content: str = None) -> MonitoringWorkflowState:
        """Create initial state for monitoring workflow"""
        workflow_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Create initial system message
        system_message = SystemMessage(
            content=f"Starting monitoring workflow for {target_data['target_type']} target: {target_data['url']}"
        )
        
        initial_state: MonitoringWorkflowState = {
            # Target information
            "target_url": str(target_data["url"]),
            "target_type": target_data["target_type"],
            "frequency_minutes": target_data.get("frequency_minutes", 60),
            "target_name": target_data.get("name"),
            
            # Content tracking
            "current_content": None,
            "previous_content": previous_content or "",
            
            # Change detection
            "changes_detected": [],
            
            # Workflow control
            "messages": [system_message],
            "step": "initialized",
            "error": None,
            "retry_count": 0,
            
            # Metadata
            "workflow_id": workflow_id,
            "started_at": current_time,
            "last_updated": current_time
        }
        
        return initial_state
    
    async def run_monitoring(self, target_data: Dict[str, Any], previous_content: str = None) -> Dict[str, Any]:
        """Run monitoring workflow for a single target"""
        try:
            # Create initial state
            initial_state = self.create_initial_state(target_data, previous_content)
            
            logger.info(f"Starting monitoring workflow for {target_data['url']}")
            
            # Run the workflow
            config = {"configurable": {"thread_id": initial_state["workflow_id"]}}
            
            final_state = None
            async for state in self.workflow.astream(initial_state, config):
                final_state = state
                logger.debug(f"Workflow step: {state.get('step', 'unknown')}")
            
            if not final_state:
                raise Exception("Workflow did not produce any output")
            
            # Extract results from the final state
            # Handle case where final_state might be nested
            if isinstance(final_state, dict) and len(final_state) == 1:
                # If final_state is like {'node_name': actual_state}
                final_state = list(final_state.values())[0]
            
            result = {
                "workflow_id": final_state.get("workflow_id", initial_state["workflow_id"]),
                "target_url": final_state.get("target_url", target_data["url"]),
                "success": not bool(final_state.get("error")),
                "error": final_state.get("error"),
                "changes_detected": final_state.get("changes_detected", []),
                "current_content": final_state.get("current_content"),
                "step": final_state.get("step", "completed"),
                "retry_count": final_state.get("retry_count", 0),
                "started_at": final_state.get("started_at", initial_state["started_at"]),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Monitoring workflow completed for {target_data['url']}: {result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed for {target_data['url']}: {e}")
            return {
                "workflow_id": initial_state.get("workflow_id", "unknown"),
                "target_url": target_data["url"],
                "success": False,
                "error": str(e),
                "changes_detected": [],
                "current_content": None,
                "step": "failed",
                "retry_count": 0,
                "started_at": initial_state.get("started_at"),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
    
    def run_monitoring_sync(self, target_data: Dict[str, Any], previous_content: str = None) -> Dict[str, Any]:
        """Synchronous version of run_monitoring for Celery compatibility"""
        import asyncio
        
        try:
            # Create new event loop if none exists
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.run_monitoring(target_data, previous_content))
            
        except Exception as e:
            logger.error(f"Sync workflow execution failed: {e}")
            return {
                "workflow_id": "unknown",
                "target_url": target_data["url"],
                "success": False,
                "error": str(e),
                "changes_detected": [],
                "current_content": None,
                "step": "failed",
                "retry_count": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }

# Global workflow instance
monitoring_workflow = MonitoringWorkflow()