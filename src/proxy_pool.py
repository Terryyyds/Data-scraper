"""Proxy pool manager for rotating proxies."""
import random
import structlog
from typing import List, Optional
from pathlib import Path

logger = structlog.get_logger()


class ProxyPool:
    """Manages a pool of proxy servers for rotation."""
    
    def __init__(self, proxy_list: str = None):
        """
        Initialize proxy pool.
        
        Args:
            proxy_list: Comma-separated proxy URLs or path to file with proxies
        """
        self.proxies: List[str] = []
        self.current_index = 0
        self.failed_proxies = set()
        
        if proxy_list:
            self._load_proxies(proxy_list)
    
    def _load_proxies(self, proxy_list: str):
        """Load proxies from string or file."""
        # Check if it's a file path
        if Path(proxy_list).exists():
            with open(proxy_list, 'r') as f:
                proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        else:
            # Treat as comma-separated list
            proxies = [p.strip() for p in proxy_list.split(',') if p.strip()]
        
        self.proxies = proxies
        logger.info("proxies_loaded", count=len(self.proxies))
    
    def get_proxy(self, random_selection: bool = False) -> Optional[str]:
        """
        Get next proxy from pool.
        
        Args:
            random_selection: If True, select random proxy instead of round-robin
        
        Returns:
            Proxy URL or None if no proxies available
        """
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        if not available_proxies:
            logger.warning("no_proxies_available", total=len(self.proxies), failed=len(self.failed_proxies))
            return None
        
        if random_selection:
            proxy = random.choice(available_proxies)
        else:
            # Round-robin
            proxy = available_proxies[self.current_index % len(available_proxies)]
            self.current_index += 1
        
        logger.debug("proxy_selected", proxy=self._mask_proxy(proxy))
        return proxy
    
    def mark_proxy_failed(self, proxy: str):
        """Mark a proxy as failed."""
        self.failed_proxies.add(proxy)
        logger.warning("proxy_marked_failed", proxy=self._mask_proxy(proxy), failed_count=len(self.failed_proxies))
    
    def reset_failed_proxies(self):
        """Reset failed proxies list."""
        logger.info("proxies_reset", count=len(self.failed_proxies))
        self.failed_proxies.clear()
    
    def _mask_proxy(self, proxy: str) -> str:
        """Mask proxy credentials for logging."""
        if '@' in proxy:
            # Format: http://user:pass@host:port
            parts = proxy.split('@')
            return f"***@{parts[-1]}"
        return proxy
    
    def add_proxy(self, proxy: str):
        """Add a single proxy to the pool."""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            logger.info("proxy_added", proxy=self._mask_proxy(proxy), total=len(self.proxies))
    
    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        return {
            "total_proxies": len(self.proxies),
            "failed_proxies": len(self.failed_proxies),
            "available_proxies": len(self.proxies) - len(self.failed_proxies)
        }


# Free proxy fetcher (optional enhancement)
def fetch_free_proxies() -> List[str]:
    """
    Fetch free proxies from public sources.
    
    Note: Free proxies are often unreliable. Consider using paid proxy services
    for production use.
    
    Returns:
        List of proxy URLs
    """
    proxies = []
    
    # Example free proxy sources (you can add more)
    # WARNING: These may not work reliably
    
    # You can integrate with services like:
    # - https://www.proxy-list.download/
    # - https://free-proxy-list.net/
    # - https://www.proxyscrape.com/
    
    # For now, return empty list
    # In production, you should use paid proxy services like:
    # - Bright Data (formerly Luminati)
    # - Oxylabs
    # - Smartproxy
    # - ScraperAPI
    
    logger.info("free_proxies_fetched", count=len(proxies))
    return proxies

