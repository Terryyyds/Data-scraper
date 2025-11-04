"""Main scraper implementation."""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import structlog
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.models import Post, Comment, ScrapingStats, Checkpoint
from src.rate_limiter import RateLimiter, ExponentialBackoff
from config.settings import settings

logger = structlog.get_logger()


class YDLScraper:
    """Scraper for m.ydl.com/ask."""
    
    def __init__(self):
        """Initialize scraper."""
        self.rate_limiter = RateLimiter(
            qps=settings.QPS_LIMIT,
            burst=settings.BURST,
            jitter_min=settings.JITTER_MIN,
            jitter_max=settings.JITTER_MAX
        )
        self.stats = ScrapingStats()
        self.checkpoint = self._load_checkpoint()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    def _load_checkpoint(self) -> Checkpoint:
        """Load checkpoint from file."""
        checkpoint_path = Path(settings.CHECKPOINT_FILE)
        if checkpoint_path.exists():
            try:
                data = json.loads(checkpoint_path.read_text())
                return Checkpoint(**data)
            except Exception as e:
                logger.warning("checkpoint_load_failed", error=str(e))
        return Checkpoint()
    
    def _save_checkpoint(self):
        """Save checkpoint to file."""
        checkpoint_path = Path(settings.CHECKPOINT_FILE)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(self.checkpoint.model_dump_json(indent=2))
        logger.info("checkpoint_saved", checkpoint=self.checkpoint.model_dump())
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start browser and context."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=settings.HEADLESS
        )
        self.context = await self.browser.new_context(
            viewport={
                "width": settings.VIEWPORT_WIDTH,
                "height": settings.VIEWPORT_HEIGHT
            },
            user_agent=settings.UA_MOBILE,
            locale="zh-CN"
        )
        logger.info("browser_started")
    
    async def close(self):
        """Close browser and context."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("browser_closed")
    
    def _extract_preloaded_state(self, html: str) -> Optional[Dict]:
        """Extract preloadedState from HTML."""
        try:
            # Find window.$G = {...} with preloadedState
            pattern = r'window\.\$G\s*=\s*(\{.*?"preloadedState".*?\});'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                return data.get("preloadedState", {})
        except Exception as e:
            logger.warning("preloaded_state_extraction_failed", error=str(e))
        return None
    
    async def _scroll_to_load_more(self, page: Page, max_empty: int = 8) -> List[Dict]:
        """Scroll page to load more posts."""
        posts = []
        empty_count = 0
        last_post_count = 0
        
        while empty_count < max_empty:
            await self.rate_limiter.acquire()
            
            # Scroll down
            await page.evaluate(f"window.scrollBy(0, {settings.SCROLL_STEP})")
            await asyncio.sleep(1)  # Wait for content to load
            
            # Try to extract posts from current page state
            try:
                # Check if there's an API response intercepted
                # Or extract from DOM/state
                current_posts = await self._extract_posts_from_page(page)
                
                if len(current_posts) == last_post_count:
                    empty_count += 1
                    logger.debug("scroll_no_new_posts", empty_count=empty_count)
                else:
                    empty_count = 0
                    posts = current_posts
                    last_post_count = len(posts)
                    logger.info("scroll_loaded_posts", total=len(posts))
            except Exception as e:
                logger.error("scroll_error", error=str(e))
                empty_count += 1
        
        return posts
    
    async def _extract_posts_from_page(self, page: Page) -> List[Dict]:
        """Extract posts from current page state."""
        # Try to get posts from React state or DOM
        try:
            # Approach 1: Try to access React internal state
            posts_data = await page.evaluate("""
                () => {
                    // Try to find React fiber
                    const appDiv = document.querySelector('#app');
                    if (!appDiv) return null;
                    
                    // Try to find state in various places
                    // This is a heuristic approach
                    const reactKey = Object.keys(appDiv).find(key => 
                        key.startsWith('__reactInternalInstance') || 
                        key.startsWith('__reactFiber')
                    );
                    
                    if (reactKey && appDiv[reactKey]) {
                        // Navigate the fiber tree to find state
                        let fiber = appDiv[reactKey];
                        while (fiber) {
                            if (fiber.memoizedState?.data?.data?.data) {
                                return fiber.memoizedState.data.data.data;
                            }
                            if (fiber.child) {
                                fiber = fiber.child;
                            } else if (fiber.sibling) {
                                fiber = fiber.sibling;
                            } else {
                                break;
                            }
                        }
                    }
                    
                    return null;
                }
            """)
            
            if posts_data and isinstance(posts_data, list):
                return posts_data
        except Exception as e:
            logger.debug("react_state_extraction_failed", error=str(e))
        
        # Approach 2: Parse visible posts from DOM
        try:
            posts_data = await page.evaluate("""
                () => {
                    const posts = [];
                    // This is a placeholder - actual selectors need to be determined
                    // by inspecting the rendered DOM
                    const postElements = document.querySelectorAll('[data-post-id]');
                    for (const el of postElements) {
                        const postId = el.getAttribute('data-post-id');
                        if (postId) {
                            posts.push({ id: parseInt(postId) });
                        }
                    }
                    return posts;
                }
            """)
            return posts_data or []
        except Exception as e:
            logger.debug("dom_extraction_failed", error=str(e))
        
        return []
    
    async def _fetch_post_detail(self, page: Page, post_id: int) -> Optional[Dict]:
        """Fetch detailed post data including all comments."""
        detail_url = f"https://m.ydl.com/ask/detail/{post_id}"
        
        try:
            await self.rate_limiter.acquire()
            
            response = await page.goto(detail_url, wait_until="networkidle")
            if response and response.status != 200:
                self.stats.add_http_status(response.status)
                logger.warning("post_detail_failed", post_id=post_id, status=response.status)
                return None
            
            self.stats.add_http_status(200)
            
            # Extract preloaded state
            html = await page.content()
            preloaded = self._extract_preloaded_state(html)
            
            if preloaded and "data" in preloaded:
                data = preloaded["data"]
                if "data" in data and isinstance(data["data"], dict):
                    return data["data"]
            
            logger.warning("post_detail_no_data", post_id=post_id)
            return None
            
        except Exception as e:
            logger.error("post_detail_error", post_id=post_id, error=str(e))
            self.stats.errors += 1
            return None
    
    async def scrape_list_page(self, url: str = None) -> List[Post]:
        """Scrape posts from list page."""
        url = url or settings.TARGET_ROOT
        posts = []
        
        try:
            page = await self.context.new_page()
            
            await self.rate_limiter.acquire()
            
            response = await page.goto(url, wait_until="networkidle")
            if not response or response.status != 200:
                self.stats.add_http_status(response.status if response else 0)
                logger.error("list_page_failed", url=url, status=response.status if response else None)
                return posts
            
            self.stats.add_http_status(200)
            
            # Extract initial posts from preloaded state
            html = await page.content()
            preloaded = self._extract_preloaded_state(html)
            
            if preloaded and "data" in preloaded:
                data = preloaded["data"]
                if "data" in data and "data" in data["data"]:
                    posts_data = data["data"]["data"]
                    
                    for post_data in posts_data:
                        try:
                            post = Post.from_api_response(post_data, url)
                            posts.append(post)
                            self.stats.total_posts += 1
                            self.stats.total_comments += len(post.comments)
                            
                            logger.info("post_parsed", post_id=post.post_id, comments=len(post.comments))
                        except Exception as e:
                            logger.error("post_parse_error", error=str(e), data=post_data)
                            self.stats.errors += 1
            
            # Scroll to load more posts
            logger.info("starting_scroll_load")
            # Note: The site might not support infinite scroll on initial load
            # We'll need to investigate pagination mechanism
            
            await page.close()
            
        except Exception as e:
            logger.error("scrape_list_error", error=str(e))
            self.stats.errors += 1
        
        return posts
    
    async def scrape_post_details(self, post_ids: List[int]) -> List[Post]:
        """Scrape detailed information for multiple posts."""
        posts = []
        
        page = await self.context.new_page()
        
        for post_id in post_ids:
            try:
                post_data = await self._fetch_post_detail(page, post_id)
                if post_data:
                    detail_url = f"https://m.ydl.com/ask/detail/{post_id}"
                    post = Post.from_api_response(post_data, detail_url)
                    posts.append(post)
                    
                    self.stats.total_posts += 1
                    self.stats.total_comments += len(post.comments)
                    
                    # Update checkpoint
                    if not self.checkpoint.last_post_id or post_id > self.checkpoint.last_post_id:
                        self.checkpoint.last_post_id = post_id
                        self.checkpoint.last_post_time = post.publish_time
                    
                    logger.info("post_detail_scraped", post_id=post_id, comments=len(post.comments))
                else:
                    self.stats.errors += 1
                    
            except Exception as e:
                logger.error("scrape_post_detail_error", post_id=post_id, error=str(e))
                self.stats.errors += 1
        
        await page.close()
        
        return posts
    
    async def scrape_incremental(self) -> List[Post]:
        """Scrape only new posts since last checkpoint."""
        logger.info("incremental_scrape_start", checkpoint=self.checkpoint.model_dump())
        
        posts = await self.scrape_list_page()
        
        # Filter posts newer than checkpoint
        if self.checkpoint.last_post_id:
            new_posts = [p for p in posts if p.post_id > self.checkpoint.last_post_id]
            logger.info("incremental_filter", total=len(posts), new=len(new_posts))
            posts = new_posts
        
        self.checkpoint.last_run_time = datetime.now()
        self.checkpoint.total_posts_scraped += len(posts)
        self._save_checkpoint()
        
        return posts
    
    async def scrape_full(self) -> List[Post]:
        """Scrape all available posts."""
        logger.info("full_scrape_start")
        
        posts = await self.scrape_list_page()
        
        # Get detailed info for all posts
        post_ids = [p.post_id for p in posts]
        detailed_posts = await self.scrape_post_details(post_ids)
        
        self.checkpoint.last_run_time = datetime.now()
        if detailed_posts:
            max_post = max(detailed_posts, key=lambda p: p.post_id)
            self.checkpoint.last_post_id = max_post.post_id
            self.checkpoint.last_post_time = max_post.publish_time
        self.checkpoint.total_posts_scraped += len(detailed_posts)
        self._save_checkpoint()
        
        return detailed_posts
    
    def get_stats(self) -> ScrapingStats:
        """Get scraping statistics."""
        self.stats.end_time = datetime.now()
        return self.stats

