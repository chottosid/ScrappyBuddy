"""
LangGraph-native scraper node
Handles content scraping with proper state management and error handling
"""

import logging
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from langchain_core.messages import AIMessage

from models import MonitoringWorkflowState

logger = logging.getLogger(__name__)

def scraper_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState:
    """
    LangGraph node for scraping content from target URLs
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with scraped content or error information
    """
    target_url = state["target_url"]
    target_type = state["target_type"]
    
    logger.info(f"Scraping content from {target_url} (type: {target_type})")
    
    try:
        # Create session with proper headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Fetch content with timeout
        response = session.get(target_url, timeout=30)
        response.raise_for_status()
        
        # Extract content based on target type
        if target_type == "linkedin_profile":
            content = _extract_linkedin_profile(response.text)
        elif target_type == "linkedin_company":
            content = _extract_linkedin_company(response.text)
        else:  # website
            content = _extract_website_content(response.text)
        
        if not content or len(content.strip()) < 10:
            raise ValueError("Extracted content is too short or empty")
        
        # Update state with successful scraping
        state["current_content"] = content
        state["step"] = "scraping_completed"
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Add success message
        success_message = AIMessage(
            content=f"Successfully scraped {len(content)} characters from {target_url}"
        )
        state["messages"] = state.get("messages", []) + [success_message]
        
        logger.info(f"Successfully scraped {len(content)} characters from {target_url}")
        
    except requests.exceptions.Timeout:
        error_msg = f"Timeout while scraping {target_url}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "scraping_failed"
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            error_msg = f"Rate limited by {target_url}"
        elif e.response.status_code == 403:
            error_msg = f"Access forbidden to {target_url}"
        elif e.response.status_code == 404:
            error_msg = f"Target not found: {target_url}"
        else:
            error_msg = f"HTTP error {e.response.status_code} for {target_url}"
        
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "scraping_failed"
        
    except Exception as e:
        error_msg = f"Failed to scrape {target_url}: {str(e)}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["step"] = "scraping_failed"
    
    finally:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return state

def _extract_linkedin_profile(html: str) -> str:
    """Extract relevant content from LinkedIn profile"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    content_parts = []
    
    # Name and headline
    name = soup.find('h1')
    if name:
        content_parts.append(f"Name: {name.get_text().strip()}")
    
    # Current position/headline
    headline_selectors = [
        'div.text-body-medium',
        '.pv-text-details__left-panel h2',
        '.text-heading-xlarge + .text-body-medium'
    ]
    
    for selector in headline_selectors:
        headline = soup.select_one(selector)
        if headline:
            content_parts.append(f"Headline: {headline.get_text().strip()}")
            break
    
    # Experience section
    experience_section = soup.find('section', {'data-section': 'experience'}) or soup.find('div', id='experience')
    if experience_section:
        experience_items = experience_section.find_all(['div', 'li'], limit=3)
        for i, item in enumerate(experience_items):
            item_text = item.get_text().strip()[:200]
            if len(item_text) > 20:
                content_parts.append(f"Experience {i+1}: {item_text}")
    
    # Recent posts/activity
    posts = soup.find_all('div', class_=['feed-shared-update-v2', 'occludable-update'], limit=3)
    for i, post in enumerate(posts):
        post_text = post.get_text().strip()[:200]
        if len(post_text) > 20:
            content_parts.append(f"Recent Post {i+1}: {post_text}")
    
    return "\n".join(content_parts) if content_parts else soup.get_text()[:2000]

def _extract_linkedin_company(html: str) -> str:
    """Extract relevant content from LinkedIn company page"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    content_parts = []
    
    # Company name
    company_name = soup.find('h1') or soup.find('span', class_='org-top-card-summary__title')
    if company_name:
        content_parts.append(f"Company: {company_name.get_text().strip()}")
    
    # Company tagline/industry
    tagline = soup.find('div', class_='org-top-card-summary__tagline')
    if tagline:
        content_parts.append(f"Tagline: {tagline.get_text().strip()}")
    
    # About section
    about_selectors = [
        'section[data-section="about"]',
        '.org-about-us-organization-description',
        '.break-words p'
    ]
    
    for selector in about_selectors:
        about = soup.select_one(selector)
        if about:
            about_text = about.get_text().strip()[:500]
            if len(about_text) > 20:
                content_parts.append(f"About: {about_text}")
            break
    
    # Recent updates/posts
    updates = soup.find_all('div', class_=['org-update', 'feed-shared-update-v2'], limit=3)
    for i, update in enumerate(updates):
        update_text = update.get_text().strip()[:200]
        if len(update_text) > 20:
            content_parts.append(f"Update {i+1}: {update_text}")
    
    return "\n".join(content_parts) if content_parts else soup.get_text()[:2000]

def _extract_website_content(html: str) -> str:
    """Extract relevant content from general website"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    # Get title
    title = soup.find('title')
    title_text = title.get_text().strip() if title else ""
    
    # Get meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    meta_desc_text = meta_desc.get('content', '') if meta_desc else ""
    
    # Get main content with multiple strategies
    content_parts = []
    
    # Strategy 1: Try specific content areas
    content_selectors = ['main', 'article', '.content', '#content', '.main', '[role="main"]']
    for selector in content_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            content_parts.append(content_elem.get_text().strip())
            break
    
    # Strategy 2: Get all headings (h1-h6)
    headings = []
    for i in range(1, 7):
        for heading in soup.find_all(f'h{i}'):
            heading_text = heading.get_text().strip()
            if len(heading_text) > 5:
                headings.append(heading_text)
    
    # Strategy 3: Get meaningful paragraphs
    paragraphs = []
    for p in soup.find_all('p'):
        p_text = p.get_text().strip()
        if len(p_text) > 20:  # Only meaningful paragraphs
            paragraphs.append(p_text)
    
    # Strategy 4: Fallback to body content
    if not content_parts:
        body = soup.find('body')
        if body:
            body_text = ' '.join(body.get_text().split())
            content_parts.append(body_text)
    
    # Combine all content
    result_parts = []
    if title_text:
        result_parts.append(f"Title: {title_text}")
    if meta_desc_text:
        result_parts.append(f"Description: {meta_desc_text}")
    if headings:
        result_parts.append(f"Headings: {' | '.join(headings[:10])}")
    if paragraphs:
        paragraph_text = ' '.join(paragraphs[:10])[:1500]
        result_parts.append(f"Content: {paragraph_text}")
    if content_parts:
        main_text = content_parts[0][:3000] if content_parts[0] else ""
        if main_text and main_text not in str(result_parts):
            result_parts.append(f"Main: {main_text}")
    
    final_content = "\n".join(result_parts)
    
    # Ensure we have some content
    if len(final_content.strip()) < 50:
        # Last resort: get all text
        final_content = soup.get_text()[:2000]
    
    return final_content