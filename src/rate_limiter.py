"""Rate limiter with jitter and backoff."""
import asyncio
import random
import time
from typing import Optional
import structlog

logger = structlog.get_logger()


class RateLimiter:
    """Token bucket rate limiter with jitter."""
    
    def __init__(
        self,
        qps: float = 0.5,
        burst: int = 2,
        jitter_min: float = 0.1,
        jitter_max: float = 0.3
    ):
        """
        Initialize rate limiter.
        
        Args:
            qps: Queries per second
            burst: Max burst size
            jitter_min: Minimum jitter ratio
            jitter_max: Maximum jitter ratio
        """
        self.qps = qps
        self.burst = burst
        self.jitter_min = jitter_min
        self.jitter_max = jitter_max
        self.tokens = burst
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire token, waiting if necessary."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.qps)
            self.last_update = now
            
            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.qps
                # Add jitter
                jitter = random.uniform(self.jitter_min, self.jitter_max)
                wait_time = wait_time * (1 + jitter)
                
                logger.debug("rate_limit_wait", wait_time=wait_time)
                await asyncio.sleep(wait_time)
                
                self.tokens = 0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1
                
                # Add small jitter even when tokens available
                jitter_sleep = random.uniform(0, 0.1)
                await asyncio.sleep(jitter_sleep)


class ExponentialBackoff:
    """Exponential backoff with jitter."""
    
    def __init__(
        self,
        base: float = 1.0,
        max_delay: float = 60.0,
        jitter_min: float = 0.1,
        jitter_max: float = 0.3
    ):
        """
        Initialize backoff.
        
        Args:
            base: Base delay in seconds
            max_delay: Maximum delay in seconds
            jitter_min: Minimum jitter ratio
            jitter_max: Maximum jitter ratio
        """
        self.base = base
        self.max_delay = max_delay
        self.jitter_min = jitter_min
        self.jitter_max = jitter_max
        self.attempt = 0
        
    def get_delay(self) -> float:
        """Get delay for current attempt."""
        delay = min(self.base * (2 ** self.attempt), self.max_delay)
        jitter = random.uniform(self.jitter_min, self.jitter_max)
        return delay * (1 + jitter)
    
    async def sleep(self):
        """Sleep for backoff duration."""
        delay = self.get_delay()
        logger.info("exponential_backoff", attempt=self.attempt, delay=delay)
        await asyncio.sleep(delay)
        self.attempt += 1
    
    def reset(self):
        """Reset backoff counter."""
        self.attempt = 0

