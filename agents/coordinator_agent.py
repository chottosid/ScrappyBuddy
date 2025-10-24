import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from typing import Annotated
from models import MonitoringState, MonitoringTarget, ChangeDetection
from agents.scraper_agent import ScraperAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.notifier_agent import NotifierAgent
from agents.scheduler_agent import SchedulerAgent
from database import db
from config import Config

logger = logging.getLogger(__name__)

class CoordinatorAgent:
    def __init__(self):
        self.scraper = ScraperAgent()
        self.analyzer = AnalyzerAgent()
        self.notifier = NotifierAgent()
        self.scheduler = SchedulerAgent()
        
        self.changes_collection = db.get_collection(Config.CHANGES_COLLECTION)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """Build the LangGraph workflow with proper state management"""
        
        # Define the state schema for LangGraph
        class WorkflowState(TypedDict):
            target: MonitoringTarget
            current_content: str
            previous_content: str
            changes_detected: list
            error: str
            step: str
        
        # Create the workflow
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("scrape", self._scrape_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("notify", self._notify_node)
        workflow.add_node("store", self._store_node)
        
        # Add edges with conditional logic
        workflow.set_entry_point("scrape")
        workflow.add_edge("scrape", "analyze")
        workflow.add_edge("analyze", "notify")
        workflow.add_edge("notify", "store")
        workflow.add_edge("store", END)
        
        return workflow.compile()
    
    def _scrape_node(self, state: dict) -> dict:
        """Scraping node - LangGraph compatible"""
        target = state["target"]

        
        try:
            # Create MonitoringState for agent compatibility
            monitoring_state = MonitoringState(
                target=target,
                previous_content=state.get("previous_content", "")
            )
            
            # Run scraper
            result = self.scraper.scrape_content(monitoring_state)
            
            # Update state
            state["current_content"] = result.current_content or ""
            state["error"] = result.error or ""
            state["step"] = "scrape_completed"
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            state["error"] = str(e)
            state["step"] = "scrape_failed"
        
        return state
    
    def _analyze_node(self, state: dict) -> dict:
        """Analysis node - LangGraph compatible"""
        if state.get("error"):
            return state
        
        target = state["target"]
        
        try:
            # Create MonitoringState for agent compatibility
            monitoring_state = MonitoringState(
                target=target,
                current_content=state.get("current_content", ""),
                previous_content=state.get("previous_content", "")
            )
            
            # Run analyzer
            result = self.analyzer.analyze_changes(monitoring_state)
            
            # Update state
            state["changes_detected"] = [change.dict() for change in result.changes_detected]
            state["error"] = result.error or state.get("error", "")
            state["step"] = "analyze_completed"
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            state["error"] = str(e)
            state["step"] = "analyze_failed"
        
        return state
    
    def _notify_node(self, state: dict) -> dict:
        """Notification node - LangGraph compatible"""
        if state.get("error"):
            return state
        
        target = state["target"]
        
        try:
            # Create MonitoringState for agent compatibility
            monitoring_state = MonitoringState(
                target=target,
                current_content=state.get("current_content", ""),
                previous_content=state.get("previous_content", ""),
                changes_detected=[ChangeDetection(**change) for change in state.get("changes_detected", [])]
            )
            
            # Run notifier
            result = self.notifier.send_notifications(monitoring_state)
            
            # Update state
            state["error"] = result.error or state.get("error", "")
            state["step"] = "notify_completed"
            
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            state["error"] = str(e)
            state["step"] = "notify_failed"
        
        return state
    
    def _store_node(self, state: dict) -> dict:
        """Storage node - LangGraph compatible"""
        target = state["target"]
        
        try:
            # Store detected changes
            changes_detected = state.get("changes_detected", [])
            for change_dict in changes_detected:
                self.changes_collection.insert_one(change_dict)
            
            # Update last checked timestamp
            self.scheduler.update_last_checked(str(target.url))
            

            state["step"] = "store_completed"
            
        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            state["error"] = str(e)
            state["step"] = "store_failed"
        
        return state
    
    def monitor_target(self, target: MonitoringTarget, previous_content: str = None) -> MonitoringState:
        """Monitor a single target using LangGraph workflow"""

        
        # Create initial state for LangGraph
        initial_state = {
            "target": target,
            "current_content": "",
            "previous_content": previous_content or "",
            "changes_detected": [],
            "error": "",
            "step": "initialized"
        }
        
        try:
            # Run the LangGraph workflow
            result = self.workflow.invoke(initial_state)
            
            # Convert back to MonitoringState
            changes_detected = []
            for change_dict in result.get("changes_detected", []):
                if isinstance(change_dict, dict):
                    changes_detected.append(ChangeDetection(**change_dict))
                else:
                    changes_detected.append(change_dict)
            
            final_state = MonitoringState(
                target=target,
                current_content=result.get("current_content", ""),
                previous_content=result.get("previous_content", ""),
                changes_detected=changes_detected,
                error=result.get("error", "")
            )
            

            return final_state
            
        except Exception as e:
            logger.error(f"LangGraph workflow failed for {target.url}: {e}")
            error_state = MonitoringState(
                target=target,
                previous_content=previous_content or "",
                error=str(e)
            )
            return error_state
    
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle for all due targets"""

        
        targets = self.scheduler.get_targets_to_monitor()
        
        if not targets:
            return
            
        for target in targets:
            try:

                
                # Get previous content for comparison
                previous_content = self._get_previous_content(str(target.url))
                
                # Monitor the target
                result = self.monitor_target(target, previous_content)
                
                # Store current content for next comparison
                if result.current_content and not result.error:
                    self._store_current_content(str(target.url), result.current_content)
                elif result.error:
                    logger.error(f"Target {target.url} had error: {result.error}")
                
            except Exception as e:
                logger.error(f"Failed to monitor {target.url}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        

    
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