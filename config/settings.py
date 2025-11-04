"""Configuration settings for the scraper."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Target
    TARGET_ROOT: str = "https://m.ydl.com/ask"
    BASE_URL: str = "https://m.ydl.com"
    
    # Time range
    START_RANGE: Optional[str] = None  # e.g., "2025-01-01"
    
    # User Agent
    UA_MOBILE: str = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
    
    # Rate limiting
    QPS_LIMIT: float = 0.5  # Queries per second
    BURST: int = 2  # Max concurrent requests
    RETRY: int = 3  # Retry attempts
    BACKOFF_BASE: float = 1.0  # Base backoff in seconds
    BACKOFF_MAX: float = 60.0  # Max backoff in seconds
    JITTER_MIN: float = 0.1  # 10% jitter
    JITTER_MAX: float = 0.3  # 30% jitter
    
    # Scrolling
    SCROLL_STEP: int = 1500  # Pixels to scroll
    SCROLL_MAX_EMPTY: int = 8  # Max empty scrolls before stopping
    
    # Storage
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    CHECKPOINT_FILE: str = "data/checkpoint.json"
    
    # Monitoring
    ALERT_SINK: Optional[str] = None  # Slack webhook or similar
    
    # Playwright
    HEADLESS: bool = True
    VIEWPORT_WIDTH: int = 375
    VIEWPORT_HEIGHT: int = 812
    
    # Proxy settings
    USE_PROXY: bool = False
    PROXY_LIST: str = ""  # Comma-separated proxy list or file path
    PROXY_ROTATION: bool = True  # Rotate proxies
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

