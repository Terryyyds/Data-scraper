"""Main scraper implementation."""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import structlog
import aiohttp
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.models import Post, Comment, ScrapingStats, Checkpoint
from src.rate_limiter import RateLimiter, ExponentialBackoff
from src.proxy_pool import ProxyPool
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
        self.proxy_pool = ProxyPool(settings.PROXY_LIST) if settings.USE_PROXY else None
        self.current_proxy: Optional[str] = None
        
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
        # Don't start browser automatically - it will be started if needed
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser or self.context:
            await self.close()
    
    async def start(self):
        """Start browser and context."""
        playwright = await async_playwright().start()
        
        # Get proxy if enabled
        if self.proxy_pool:
            self.current_proxy = self.proxy_pool.get_proxy(random_selection=settings.PROXY_ROTATION)
            if self.current_proxy:
                logger.info("using_proxy", proxy=self.proxy_pool._mask_proxy(self.current_proxy))
        
        self.browser = await playwright.chromium.launch(
            headless=settings.HEADLESS,
            proxy={"server": self.current_proxy} if self.current_proxy else None
        )
        self.context = await self.browser.new_context(
            viewport={
                "width": settings.VIEWPORT_WIDTH,
                "height": settings.VIEWPORT_HEIGHT
            },
            user_agent=settings.UA_MOBILE,
            locale="zh-CN"
        )
        logger.info("browser_started", with_proxy=bool(self.current_proxy))
    
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
    
    async def scrape_list_page(self, url: str = None, max_pages: int = 50) -> List[Post]:
        """Scrape posts from list page with scrolling."""
        url = url or settings.TARGET_ROOT
        posts = []
        seen_post_ids = set()
        
        try:
            page = await self.context.new_page()
            
            await self.rate_limiter.acquire()
            
            response = await page.goto(url, wait_until="networkidle")
            if not response or response.status != 200:
                self.stats.add_http_status(response.status if response else 0)
                logger.error("list_page_failed", url=url, status=response.status if response else None)
                return posts
            
            self.stats.add_http_status(200)
            
            # Scroll and collect posts multiple times
            empty_scroll_count = 0
            max_empty_scrolls = 10
            scroll_count = 0
            
            while scroll_count < max_pages and empty_scroll_count < max_empty_scrolls:
                # Extract posts from current page state
                html = await page.content()
                preloaded = self._extract_preloaded_state(html)
                
                posts_found_this_scroll = 0
                
                if preloaded and "data" in preloaded:
                    data = preloaded["data"]
                    if "data" in data and "data" in data["data"]:
                        posts_data = data["data"]["data"]
                        
                        for post_data in posts_data:
                            post_id = post_data.get("id")
                            if post_id and post_id not in seen_post_ids:
                                try:
                                    post = Post.from_api_response(post_data, url)
                                    posts.append(post)
                                    seen_post_ids.add(post_id)
                                    self.stats.total_posts += 1
                                    self.stats.total_comments += len(post.comments)
                                    posts_found_this_scroll += 1
                                    
                                    logger.info("post_parsed", post_id=post.post_id, comments=len(post.comments), total=len(posts))
                                except Exception as e:
                                    logger.error("post_parse_error", error=str(e), post_id=post_id)
                                    self.stats.errors += 1
                
                if posts_found_this_scroll == 0:
                    empty_scroll_count += 1
                    logger.info("scroll_no_new_posts", empty_count=empty_scroll_count, total_posts=len(posts))
                else:
                    empty_scroll_count = 0
                
                # Scroll down to trigger loading more content
                await self.rate_limiter.acquire()
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)  # Wait for content to load
                
                scroll_count += 1
                
                if scroll_count % 5 == 0:
                    logger.info("scroll_progress", scrolls=scroll_count, posts=len(posts))
            
            logger.info("scroll_complete", total_scrolls=scroll_count, total_posts=len(posts))
            
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
    
    async def scrape_full(self, max_pages: int = 500, max_posts: int = None, stop_date: datetime = None, start_page: int = None) -> List[Post]:
        """Scrape all available posts using API."""
        # If start_page not specified, calculate from existing data
        existing_posts = self.checkpoint.total_posts_scraped
        if start_page is None:
            # Estimate start page based on existing posts
            # Each page has ~10 posts, so if we have 5000 posts, we've done ~500 pages
            estimated_page = (existing_posts // 10) + 1
            start_page = estimated_page
            logger.info("auto_start_page", existing_posts=existing_posts, estimated_page=estimated_page)
        
        # Adjust max_posts if we already have some posts
        # If user wants 30000 total and we have 5000, we only need to scrape 25000 more
        remaining_posts = None
        if max_posts and existing_posts > 0:
            remaining_posts = max_posts - existing_posts
            if remaining_posts <= 0:
                logger.info("target_posts_already_reached", existing=existing_posts, target=max_posts)
                return []
            logger.info("adjusted_max_posts", existing=existing_posts, target=max_posts, remaining=remaining_posts)
        
        logger.info("full_scrape_start", start_page=start_page, max_pages=max_pages, max_posts=remaining_posts, stop_date=stop_date)
        
        # Use API scraping instead of browser-based scraping (much faster)
        # Calculate actual max_pages: if we start at page 500 and want to do 3000 more, we need to go to page 3500
        actual_max_pages = max_pages if start_page == 1 else (start_page + max_pages - 1)
        posts = await self.scrape_via_api(start_page=start_page, max_pages=actual_max_pages, per_page=10,
                                          max_posts=remaining_posts, stop_date=stop_date)
        
        self.checkpoint.last_run_time = datetime.now()
        if posts:
            max_post = max(posts, key=lambda p: p.post_id)
            self.checkpoint.last_post_id = max_post.post_id
            self.checkpoint.last_post_time = max_post.publish_time
        self.checkpoint.total_posts_scraped += len(posts)
        self._save_checkpoint()
        
        return posts
    
    async def scrape_via_api(self, start_page: int = 1, max_pages: int = 100, per_page: int = 10, 
                            max_posts: int = None, stop_date: datetime = None) -> List[Post]:
        """
        Scrape posts using API directly (faster and more reliable).
        
        Args:
            start_page: Starting page number
            max_pages: Maximum number of pages to scrape
            per_page: Posts per page
            max_posts: Stop when reaching this many posts (optional)
            stop_date: Stop when reaching posts before this date (optional)
        
        Returns:
            List of Post objects
        """
        from src.date_utils import parse_chinese_date
        
        posts = []
        seen_post_ids = set()
        api_url = "https://api.ydl.com/api/ask/list-old"
        
        headers = {
            "User-Agent": settings.UA_MOBILE,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://m.ydl.com/ask",
            "Origin": "https://m.ydl.com"
        }
        
        logger.info("api_scrape_start", start_page=start_page, max_pages=max_pages, per_page=per_page,
                   max_posts=max_posts, stop_date=stop_date)
        
        async with aiohttp.ClientSession() as session:
            for page_num in range(start_page, start_page + max_pages):
                await self.rate_limiter.acquire()
                
                params = {
                    "page": page_num,
                    "perPageRows": per_page,
                    "tab": 1
                }
                
                try:
                    async with session.get(api_url, params=params, headers=headers) as response:
                        if response.status != 200:
                            self.stats.add_http_status(response.status)
                            logger.warning("api_request_failed", page=page_num, status=response.status)
                            
                            if response.status == 429:  # Too many requests
                                logger.warning("rate_limited", waiting=60)
                                await asyncio.sleep(60)
                                continue
                            
                            break
                        
                        self.stats.add_http_status(200)
                        
                        data = await response.json()
                        
                        if data.get("code") != "200":
                            logger.warning("api_error", page=page_num, code=data.get("code"), msg=data.get("msg"))
                            break
                        
                        posts_data = data.get("data", {}).get("data", [])
                        
                        if not posts_data:
                            logger.info("no_more_posts", page=page_num)
                            break
                        
                        page_post_count = 0
                        should_stop = False
                        
                        for post_data in posts_data:
                            post_id = post_data.get("id")
                            if post_id and post_id not in seen_post_ids:
                                try:
                                    post = Post.from_api_response(post_data, f"{api_url}?page={page_num}")
                                    
                                    # Check stop conditions
                                    if stop_date:
                                        post_date = parse_chinese_date(post.publish_time)
                                        if post_date and post_date < stop_date:
                                            logger.info("stop_condition_met_date", 
                                                       post_date=post_date, 
                                                       stop_date=stop_date,
                                                       total_posts=len(posts))
                                            should_stop = True
                                            break
                                    
                                    posts.append(post)
                                    seen_post_ids.add(post_id)
                                    self.stats.total_posts += 1
                                    self.stats.total_comments += len(post.comments)
                                    page_post_count += 1
                                    
                                    # Check max posts limit
                                    if max_posts and len(posts) >= max_posts:
                                        logger.info("stop_condition_met_count", 
                                                   total_posts=len(posts),
                                                   max_posts=max_posts)
                                        should_stop = True
                                        break
                                        
                                except Exception as e:
                                    logger.error("post_parse_error", error=str(e), post_id=post_id)
                                    self.stats.errors += 1
                        
                        logger.info("page_scraped", page=page_num, posts_this_page=page_post_count, total_posts=len(posts))
                        
                        # Stop if condition met
                        if should_stop:
                            break
                        
                        # Log progress every 10 pages
                        if page_num % 10 == 0:
                            logger.info("scrape_progress", page=page_num, total_posts=len(posts))
                        
                except Exception as e:
                    logger.error("api_request_error", page=page_num, error=str(e))
                    self.stats.errors += 1
                    continue
        
        logger.info("api_scrape_complete", total_pages=page_num - start_page + 1, total_posts=len(posts))
        return posts
    
    def get_stats(self) -> ScrapingStats:
        """Get scraping statistics."""
        self.stats.end_time = datetime.now()
        return self.stats

