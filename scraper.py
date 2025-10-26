import requests
import json
import time
import random
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import html2text
from typing import List, Dict, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfluenceScraper:
    def __init__(self, base_url: str = "https://confluence.veeam.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session_cookie = None
        self.pages_data = []
        self.output_dir = "scraped_content"
        
        # Initialize HTML to Markdown converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.body_width = 0  # Don't wrap lines
        
    def set_session_cookie(self, cookie_value: str):
        """Set the session cookie for authentication"""
        self.session_cookie = cookie_value
        self.session.cookies.set('JSESSIONID', cookie_value)
        logger.info("Session cookie set successfully")
        
    def get_space_pages(self, space_key: str, limit: int = 100) -> List[Dict[Any, Any]]:
        """Get all pages from a Confluence space using pagination (start & limit) and include version info."""
        url = f"{self.base_url}/rest/api/content"
        start = 0
        all_pages: List[Dict[Any, Any]] = []
        params = {
            'spaceKey': space_key,
            'limit': limit,
            'expand': 'ancestors,version'
        }
        
        try:
            while True:
                params['start'] = start
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get('results', [])
                all_pages.extend(results)
                logger.info(f"Fetched {len(results)} pages (start={start}) - total so far: {len(all_pages)}")
                # Determine pagination continuation
                size = data.get('size', len(results))
                if size < limit:
                    break
                # advance start
                start += size
                # small delay between paginated requests
                self.random_delay(0.5, 1.5)
            
            logger.info(f"Total pages found in space '{space_key}': {len(all_pages)}")
            return all_pages
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching pages from space '{space_key}': {e}")
            return []

    def get_children_ids(self, page_id: str, limit: int = 100) -> List[str]:
        """Fetch child page IDs for a given page using pagination."""
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        start = 0
        ids: List[str] = []
        params = {'limit': limit}
        try:
            while True:
                params['start'] = start
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get('results', [])
                for r in results:
                    if r and r.get('id'):
                        ids.append(str(r.get('id')))
                size = data.get('size', len(results))
                if size < limit:
                    break
                start += size
                # small delay to avoid hammering the API
                self.random_delay(0.2, 0.8)
            return ids
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error fetching children for page {page_id}: {e}")
            return []

    def get_page_content(self, page_id: str) -> Dict[Any, Any]:
        """Get the full content of a specific page"""
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {
            'expand': 'body.view,ancestors'
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching content for page ID '{page_id}': {e}")
            return {}
    
    def html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to Markdown"""
        if not html_content:
            return ""
            
        # Use BeautifulSoup to clean up the HTML first
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove Confluence-specific div wrappers that don't add semantic meaning
        for div in soup.find_all('div', class_=['contentLayout2', 'columnLayout', 'cell', 'innerCell']):
            div.unwrap()
            
        cleaned_html = str(soup)
        
        # Convert to markdown
        markdown_content = self.html_converter.handle(cleaned_html)
        
        # Clean up extra whitespace
        lines = markdown_content.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_lines.append(line.rstrip())
        
        return '\n'.join(cleaned_lines).strip()
    
    def save_page_content(self, page_data: Dict[Any, Any], content: str):
        """Save page content to a markdown file"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Create safe filename
        title = page_data.get('title', 'Untitled')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        
        filename = f"{page_data['id']}_{safe_title}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        # Prepare metadata
        metadata = f"""---
id: {page_data['id']}
title: {title}
type: {page_data.get('type', 'page')}
status: {page_data.get('status', 'unknown')}
position: {page_data.get('position', 'unknown')}
---

"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(metadata + content)
            
        logger.info(f"Saved page: {filename}")
    
    def build_page_hierarchy(self, pages: List[Dict[Any, Any]]) -> str:
        """Build a markdown representation of the page hierarchy including last modified date, author and children ids."""
        hierarchy_md = "# Page Hierarchy\n\n"
        
        # Sort pages by position if available
        sorted_pages = sorted(pages, key=lambda x: (
            x.get('position', float('inf')) if x.get('position') != -1 else float('inf'),
            x.get('title', '')
        ))
        
        for page in sorted_pages:
            title = page.get('title', 'Untitled')
            page_id = page.get('id', 'unknown')
            position = page.get('position', 'unknown')

            # version may contain author (by) and when
            version = page.get('version') or {}
            author = ''
            when = ''
            if version:
                by = version.get('by') or {}
                author = by.get('displayName') or by.get('username') or by.get('userKey', '')
                when = version.get('when', '')

            # fetch children ids (may be empty)
            children_ids: List[str] = []
            try:
                children_ids = self.get_children_ids(page_id)
            except Exception:
                children_ids = []

            children_str = ', '.join(children_ids) if children_ids else ''

            hierarchy_md += f"- **{title}** (ID: {page_id}, Position: {position}, Last modified: {when}, Author: {author}, Children: [{children_str}])\n"
            
        return hierarchy_md
    
    def get_existing_page_ids(self) -> set:
        """Scan output_dir for existing markdown files and return a set of page IDs (as strings)."""
        ids = set()
        if not os.path.isdir(self.output_dir):
            return ids
        for fname in os.listdir(self.output_dir):
            if not fname.endswith('.md'):
                continue
            parts = fname.split('_', 1)
            if parts and parts[0].isdigit():
                ids.add(parts[0])
        return ids
    
    def update_hierarchy(self, space_key: str):
        """Fetch pages and update/save hierarchy file only."""
        pages = self.get_space_pages(space_key)
        if not pages:
            logger.error("No pages found or error occurred while updating hierarchy")
            return
        os.makedirs(self.output_dir, exist_ok=True)
        hierarchy_content = self.build_page_hierarchy(pages)
        hierarchy_path = os.path.join(self.output_dir, f"{space_key}_hierarchy.md")
        with open(hierarchy_path, 'w', encoding='utf-8') as f:
            f.write(hierarchy_content)
        logger.info(f"Saved page hierarchy: {hierarchy_path}")
    
    def scrape_missing_pages(self, space_key: str, limit:int = 100):
        """Scrape only pages that are not present in the output_dir."""
        logger.info(f"Starting to scrape missing pages in space: {space_key}")
        pages = self.get_space_pages(space_key, limit=limit)
        if not pages:
            logger.error("No pages found or error occurred")
            return
        # Save/refresh hierarchy
        self.update_hierarchy(space_key)
        # Determine which pages are missing
        existing_ids = self.get_existing_page_ids()
        missing_pages = [p for p in pages if str(p.get('id')) not in existing_ids]
        logger.info(f"{len(missing_pages)} pages are missing and will be scraped.")
        # Shuffle to simulate non-sequential access
        random.shuffle(missing_pages)
        for i, page in enumerate(missing_pages):
            page_id = page.get('id')
            title = page.get('title', 'Untitled')
            logger.info(f"Processing missing page {i+1}/{len(missing_pages)}: {title} (ID: {page_id})")
            full_page_data = self.get_page_content(page_id)
            if not full_page_data:
                continue
            html_content = ""
            body = full_page_data.get('body', {})
            if 'view' in body and 'value' in body['view']:
                html_content = body['view']['value']
            markdown_content = self.html_to_markdown(html_content)
            self.save_page_content(full_page_data, markdown_content)
            if i < len(missing_pages) - 1:
                self.random_delay()
        logger.info(f"Missing pages scraping completed. {len(missing_pages)} pages processed.")
    
    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 5.0):
        """Add a random delay to simulate human interaction"""
        delay = random.uniform(min_seconds, max_seconds)
        logger.info(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)
    
    def scrape_space(self, space_key: str):
        """Main method to scrape all pages from a space"""
        logger.info(f"Starting to scrape space: {space_key}")
        
        # Get all pages in the space
        pages = self.get_space_pages(space_key)
        if not pages:
            logger.error("No pages found or error occurred")
            return
            
        # Save page hierarchy
        hierarchy_content = self.build_page_hierarchy(pages)
        hierarchy_path = os.path.join(self.output_dir, f"{space_key}_hierarchy.md")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(hierarchy_path, 'w', encoding='utf-8') as f:
            f.write(hierarchy_content)
        logger.info(f"Saved page hierarchy: {hierarchy_path}")
        
        # Shuffle pages to make requests in non-sequential order
        random.shuffle(pages)
        
        # Process each page
        for i, page in enumerate(pages):
            page_id = page.get('id')
            title = page.get('title', 'Untitled')
            
            logger.info(f"Processing page {i+1}/{len(pages)}: {title} (ID: {page_id})")
            
            # Get page content
            full_page_data = self.get_page_content(page_id)
            if not full_page_data:
                continue
                
            # Extract HTML content
            html_content = ""
            body = full_page_data.get('body', {})
            if 'view' in body and 'value' in body['view']:
                html_content = body['view']['value']
            
            # Convert to markdown
            markdown_content = self.html_to_markdown(html_content)
            
            # Save the page
            self.save_page_content(full_page_data, markdown_content)
            
            # Add random delay between requests (except for the last one)
            if i < len(pages) - 1:
                self.random_delay()
        
        logger.info(f"Scraping completed! {len(pages)} pages processed.")


def main():
    scraper = ConfluenceScraper()
    
    # Get session cookie from user
    print("Confluence Space Scraper")
    print("=" * 30)
    
    session_cookie = input("Please enter your Confluence session cookie (JSESSIONID): ").strip()
    if not session_cookie:
        print("Error: Session cookie is required!")
        return
        
    scraper.set_session_cookie(session_cookie)
    
    # Get space key from user
    space_key = input("Please enter the Confluence space key (e.g., ARR): ").strip()
    if not space_key:
        print("Error: Space key is required!")
        return
    
    # Choose mode
    mode = input("Choose mode - (S)crape all pages, (U)pdate hierarchy, (F)etch missing pages: ").strip().upper()
    if mode not in ['S', 'U', 'F']:
        print("Error: Invalid mode selected!")
        return
    
    # Start scraping
    try:
        if mode == 'S':
            scraper.scrape_space(space_key)
        elif mode == 'U':
            scraper.update_hierarchy(space_key)
        elif mode == 'F':
            scraper.scrape_missing_pages(space_key)
        print(f"\nOperation completed! Check the '{scraper.output_dir}' directory for results.")
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()