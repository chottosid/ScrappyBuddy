"""
LangGraph-native analyzer node
Handles content analysis and change detection with AI-powered summarization
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from models import MonitoringWorkflowState
from config import Config

logger = logging.getLogger(__name__)

def analyzer_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState:
    """
    LangGraph node for analyzing content changes
    
    Args:
        state: Current workflow state with current and previous content
        
    Returns:
        Updated state with change detection results
    """
    target_url = state["target_url"]
    target_type = state["target_type"]
    current_content = state.get("current_content", "")
    previous_content = state.get("previous_content", "")
    
    logger.info(f"Analyzing content changes for {target_url}")
    
    try:
        # Check if we have content to analyze
        if not current_content:
            raise ValueError("No current content to analyze")
        
        # If no previous content, this is the first check
        if not previous_content:
            logger.info(f"First time monitoring {target_url}, no changes to detect")
            state["step"] = "analysis_completed_first_run"
            state["changes_detected"] = []
            
            # Add informational message
            info_message = AIMessage(
                content=f"First monitoring run for {target_url}. Baseline content established."
            )
            state["messages"] = state.get("messages", []) + [info_message]
            
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            return state
        
        # Check for identical content
        if current_content == previous_content:
            logger.info(f"No changes detected for {target_url} - content identical")
            state["step"] = "analysis_completed_no_changes"
            state["changes_detected"] = []
            
            # Add no-change message
            no_change_message = AIMessage(
                content=f"No changes detected in {target_url}. Content remains identical."
            )
            state["messages"] = state.get("messages", []) + [no_change_message]
            
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            return state
        
        # Content has changed, analyze with AI
        logger.info(f"Content changes detected for {target_url}, analyzing with AI...")
        
        changes = _detect_meaningful_changes(
            previous_content, 
            current_content,
            target_type
        )
        
        if changes:
            # Create change detection record
            change_record = {
                "target_id": target_url,
                "target_url": target_url,
                "change_type": target_type,
                "summary": changes,
                "before_content": previous_content,
                "after_content": current_content,
                "detected_at": datetime.now(timezone.utc).isoformat()
            }
            
            state["changes_detected"] = [change_record]
            state["step"] = "analysis_completed_changes_found"
            
            # Add change detection message
            change_message = AIMessage(
                content=f"Meaningful changes detected in {target_url}: {changes[:200]}..."
            )
            state["messages"] = state.get("messages", []) + [change_message]
            
            logger.info(f"Meaningful changes detected for {target_url}: {changes[:100]}...")
            
        else:
            # Changes exist but not meaningful
            state["changes_detected"] = []
            state["step"] = "analysis_completed_minor_changes"
            
            # Add minor change message
            minor_change_message = AIMessage(
                content=f"Minor changes detected in {target_url} but not significant enough to notify."
            )
            state["messages"] = state.get("messages", []) + [minor_change_message]
            
            logger.info(f"Minor changes detected for {target_url}, not significant enough to notify")
        
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        
    except Exception as e:
        error_msg = f"Failed to analyze changes for {target_url}: {str(e)}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "analysis_failed"
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return state

def _detect_meaningful_changes(before: str, after: str, target_type: str) -> str:
    """Use Gemini to detect and summarize meaningful changes"""
    
    try:
        # Initialize Gemini
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1
        )
        
        system_message = SystemMessage(content=f"""
        You are an expert content analyst for a {target_type} monitoring system.
        Your job is to identify MEANINGFUL changes between content versions.
        
        IGNORE: Minor formatting, timestamps, whitespace, or insignificant updates.
        
        FOCUS ON:
        - Job title changes (for LinkedIn profiles)
        - New posts or announcements  
        - Company updates or news
        - Contact information changes
        - Major content additions or removals
        - Product launches or updates
        - Personnel changes
        - Policy updates
        - Service changes
        
        If there are meaningful changes, provide a concise summary (max 200 words).
        If no meaningful changes, respond with "NO_MEANINGFUL_CHANGES".
        
        Be specific about what changed and why it matters.
        """)
        
        human_message = HumanMessage(content=f"""
        Compare these two content versions for {target_type}:
        
        BEFORE CONTENT:
        {before[:3000]}
        
        AFTER CONTENT:
        {after[:3000]}
        
        Analyze and summarize any meaningful changes:
        """)
        
        # Use Gemini with proper message format
        messages = [system_message, human_message]
        response = llm.invoke(messages)
        result = response.content.strip()
        
        logger.debug(f"Gemini analysis result: {result[:100]}...")
        
        if "NO_MEANINGFUL_CHANGES" in result.upper():
            return ""
        
        return result
        
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        # Fallback to simple text comparison
        return _simple_change_detection(before, after)

def _simple_change_detection(before: str, after: str) -> str:
    """Fallback simple change detection when AI fails"""
    try:
        before_lines = set(before.split('\n'))
        after_lines = set(after.split('\n'))
        
        added_lines = after_lines - before_lines
        removed_lines = before_lines - after_lines
        
        if not added_lines and not removed_lines:
            # Try word-level comparison
            before_words = set(before.split())
            after_words = set(after.split())
            
            added_words = after_words - before_words
            removed_words = before_words - after_words
            
            if added_words or removed_words:
                summary_parts = []
                if added_words:
                    sample_added = list(added_words)[:5]
                    summary_parts.append(f"New words: {', '.join(sample_added)}")
                if removed_words:
                    sample_removed = list(removed_words)[:5]
                    summary_parts.append(f"Removed words: {', '.join(sample_removed)}")
                return "; ".join(summary_parts)
            
            return ""
        
        summary_parts = []
        if added_lines:
            # Filter out very short or likely insignificant lines
            meaningful_added = [line for line in added_lines if len(line.strip()) > 10]
            if meaningful_added:
                sample_added = list(meaningful_added)[:2]
                summary_parts.append(f"Added content: {'; '.join(sample_added)}")
        
        if removed_lines:
            # Filter out very short or likely insignificant lines
            meaningful_removed = [line for line in removed_lines if len(line.strip()) > 10]
            if meaningful_removed:
                sample_removed = list(meaningful_removed)[:2]
                summary_parts.append(f"Removed content: {'; '.join(sample_removed)}")
        
        return "; ".join(summary_parts) if summary_parts else ""
        
    except Exception as e:
        logger.error(f"Simple change detection failed: {e}")
        return f"Content changed (length: {len(before)} -> {len(after)})"