import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional
from models import MonitoringState

logger = logging.getLogger(__name__)

class ScraperAgent:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_content(self, state: MonitoringState) -> MonitoringState:
        """Fetch content from the target URL"""
        try:
            url = str(state.target.url)
            logger.debug(f"Scraping content from: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse content based on target type
            if state.target.target_type.value == "linkedin_profile":
                content = self._extract_linkedin_profile(response.text)
            elif state.target.target_type.value == "linkedin_company":
                content = self._extract_linkedin_company(response.text)
            else:  # website
                content = self._extract_website_content(response.text)
            
            state.current_content = content
            logger.debug(f"Successfully scraped content from {url} (length: {len(content)})")

            
        except Exception as e:
            error_msg = f"Failed to scrape {state.target.url}: {str(e)}"
            logger.error(error_msg)
            state.error = error_msg
            
        return state
    
    def _extract_linkedin_profile(self, html: str) -> str:
        """Extract relevant content from LinkedIn profile"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract key profile information
        content_parts = []
        
        # Name and headline
        name = soup.find('h1')
        if name:
            content_parts.append(f"Name: {name.get_text().strip()}")
        
        # Current position
        headline = soup.find('div', class_='text-body-medium')
        if headline:
            content_parts.append(f"Headline: {headline.get_text().strip()}")
        
        # Recent posts (simplified)
        posts = soup.find_all('div', class_='feed-shared-update-v2')[:3]
        for i, post in enumerate(posts):
            post_text = post.get_text().strip()[:200]
            content_parts.append(f"Recent Post {i+1}: {post_text}")
        
        return "\n".join(content_parts)
    
    def _extract_linkedin_company(self, html: str) -> str:
        """Extract relevant content from LinkedIn company page"""
        soup = BeautifulSoup(html, 'html.parser')
        
        content_parts = []
        
        # Company name
        company_name = soup.find('h1')
        if company_name:
            content_parts.append(f"Company: {company_name.get_text().strip()}")
        
        # About section
        about = soup.find('section', {'data-section': 'about'})
        if about:
            about_text = about.get_text().strip()[:500]
            content_parts.append(f"About: {about_text}")
        
        # Recent updates
        updates = soup.find_all('div', class_='org-update')[:3]
        for i, update in enumerate(updates):
            update_text = update.get_text().strip()[:200]
            content_parts.append(f"Update {i+1}: {update_text}")
        
        return "\n".join(content_parts)
    
    def _extract_website_content(self, html: str) -> str:
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
                headings.append(heading.get_text().strip())
        
        # Strategy 3: Get all paragraphs
        paragraphs = []
        for p in soup.find_all('p'):
            p_text = p.get_text().strip()
            if len(p_text) > 20:  # Only meaningful paragraphs
                paragraphs.append(p_text)
        
        # Strategy 4: Fallback to body content
        if not content_parts:
            body = soup.find('body')
            if body:
                # Clean up whitespace and get text
                body_text = ' '.join(body.get_text().split())
                content_parts.append(body_text)
        
        # Combine all content
        result_parts = []
        if title_text:
            result_parts.append(f"Title: {title_text}")
        if meta_desc_text:
            result_parts.append(f"Description: {meta_desc_text}")
        if headings:
            result_parts.append(f"Headings: {' | '.join(headings[:20])}")  # First 20 headings
        if paragraphs:
            # Join more paragraphs and limit total length to ~2000 chars
            paragraph_text = ' '.join(paragraphs[:15])[:2000]
            result_parts.append(f"Content: {paragraph_text}")  # First 15 paragraphs
        if content_parts:
            # Limit main content to 5000 characters
            main_text = content_parts[0][:5000] if content_parts[0] else ""
            if main_text:
                result_parts.append(f"Main: {main_text}")
        
        return "\n".join(result_parts)