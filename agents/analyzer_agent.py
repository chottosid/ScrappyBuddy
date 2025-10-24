import logging
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from models import MonitoringState, ChangeDetection
from config import Config

logger = logging.getLogger(__name__)

class AnalyzerAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1
        )
    
    def analyze_changes(self, state: MonitoringState) -> MonitoringState:
        """Analyze content changes and generate summaries"""
        try:
            logger.info(f"Analyzing content for {state.target.url}")
            logger.info(f"Previous content length: {len(state.previous_content) if state.previous_content else 0}")
            logger.info(f"Current content length: {len(state.current_content) if state.current_content else 0}")
            
            if not state.previous_content or not state.current_content:
                logger.info("No previous content to compare")
                return state
            
            if state.previous_content == state.current_content:
                logger.info("No changes detected - content is identical")
                return state
            
            # Log the differences for debugging
            logger.info("Content differences detected!")
            if len(state.previous_content) != len(state.current_content):
                logger.info(f"Length changed: {len(state.previous_content)} -> {len(state.current_content)}")
            

            
            logger.info("Content differences detected, analyzing with AI...")
            
            # Detect meaningful changes using LLM
            changes = self._detect_meaningful_changes(
                state.previous_content, 
                state.current_content,
                state.target.target_type.value
            )
            
            if changes:
                change_detection = ChangeDetection(
                    target_id=str(state.target.url),
                    target_url=str(state.target.url),
                    change_type=state.target.target_type.value,
                    summary=changes,
                    before_content=state.previous_content,
                    after_content=state.current_content
                )
                state.changes_detected.append(change_detection)
                logger.info(f"Changes detected: {changes}")
            
        except Exception as e:
            error_msg = f"Failed to analyze changes: {str(e)}"
            logger.error(error_msg)
            state.error = error_msg
            
        return state
    
    def _detect_meaningful_changes(self, before: str, after: str, target_type: str) -> str:
        """Use Gemini 2.5-flash to detect and summarize meaningful changes"""
        
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
        
        If there are meaningful changes, provide a concise summary (max 200 words).
        If no meaningful changes, respond with "NO_MEANINGFUL_CHANGES".
        """)
        
        human_message = HumanMessage(content=f"""
        Compare these two content versions:
        
        BEFORE CONTENT:
        {before[:3000]}
        
        AFTER CONTENT:
        {after[:3000]}
        
        Analyze and summarize any meaningful changes:
        """)
        
        try:
            # Use Gemini 2.5-flash with proper message format
            messages = [system_message, human_message]
            response = self.llm.invoke(messages)
            result = response.content.strip()
            
            logger.info(f"Gemini analysis result: {result[:100]}...")
            
            if "NO_MEANINGFUL_CHANGES" in result.upper():
                return ""
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini 2.5-flash analysis failed: {e}")
            # Fallback to simple text comparison
            return self._simple_change_detection(before, after)
    
    def _simple_change_detection(self, before: str, after: str) -> str:
        """Fallback simple change detection"""
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
                    sample_added = list(added_words)[:5]  # Show first 5 new words
                    summary_parts.append(f"New words: {', '.join(sample_added)}")
                if removed_words:
                    sample_removed = list(removed_words)[:5]  # Show first 5 removed words
                    summary_parts.append(f"Removed words: {', '.join(sample_removed)}")
                return "; ".join(summary_parts)
            
            return ""
        
        summary_parts = []
        if added_lines:
            # Show sample of added content
            sample_added = list(added_lines)[:3]
            summary_parts.append(f"Added {len(added_lines)} lines: {'; '.join(sample_added)}")
        if removed_lines:
            # Show sample of removed content
            sample_removed = list(removed_lines)[:3]
            summary_parts.append(f"Removed {len(removed_lines)} lines: {'; '.join(sample_removed)}")
        
        return "; ".join(summary_parts)