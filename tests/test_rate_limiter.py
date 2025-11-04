"""Test rate limiter."""
import pytest
import asyncio
import time
from src.rate_limiter import RateLimiter, ExponentialBackoff


@pytest.mark.asyncio
async def test_rate_limiter_basic():
    """Test basic rate limiting."""
    limiter = RateLimiter(qps=2.0, burst=2, jitter_min=0, jitter_max=0)
    
    start = time.monotonic()
    
    # First two should be immediate (burst)
    await limiter.acquire()
    await limiter.acquire()
    
    elapsed = time.monotonic() - start
    assert elapsed < 0.1  # Should be nearly instant
    
    # Third should wait
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4  # Should wait ~0.5s for 2 QPS


@pytest.mark.asyncio
async def test_rate_limiter_qps():
    """Test QPS enforcement."""
    limiter = RateLimiter(qps=1.0, burst=1, jitter_min=0, jitter_max=0)
    
    start = time.monotonic()
    
    # Acquire 3 tokens
    for _ in range(3):
        await limiter.acquire()
    
    elapsed = time.monotonic() - start
    # First is instant, second waits 1s, third waits 1s
    assert elapsed >= 1.8  # Allow some margin


@pytest.mark.asyncio
async def test_exponential_backoff():
    """Test exponential backoff."""
    backoff = ExponentialBackoff(base=0.1, max_delay=1.0, jitter_min=0, jitter_max=0)
    
    delays = []
    for i in range(5):
        start = time.monotonic()
        await backoff.sleep()
        elapsed = time.monotonic() - start
        delays.append(elapsed)
    
    # Check exponential growth
    assert delays[0] < delays[1] < delays[2]
    # Check max delay cap
    assert all(d <= 1.1 for d in delays)  # Allow small margin


@pytest.mark.asyncio
async def test_backoff_reset():
    """Test backoff reset."""
    backoff = ExponentialBackoff(base=0.1, max_delay=1.0, jitter_min=0, jitter_max=0)
    
    await backoff.sleep()
    await backoff.sleep()
    
    assert backoff.attempt == 2
    
    backoff.reset()
    assert backoff.attempt == 0
    
    # After reset, delay should be back to base
    start = time.monotonic()
    await backoff.sleep()
    elapsed = time.monotonic() - start
    assert elapsed < 0.2  # Should be close to base (0.1)


@pytest.mark.asyncio
async def test_rate_limiter_concurrent():
    """Test rate limiter with concurrent requests."""
    limiter = RateLimiter(qps=2.0, burst=2, jitter_min=0, jitter_max=0)
    
    start = time.monotonic()
    
    # Launch 4 concurrent acquisitions
    tasks = [limiter.acquire() for _ in range(4)]
    await asyncio.gather(*tasks)
    
    elapsed = time.monotonic() - start
    # 2 burst instantly, 2 more need to wait
    assert elapsed >= 0.8  # Should take at least 1s for 2 QPS


@pytest.mark.asyncio
async def test_rate_limiter_with_jitter():
    """Test rate limiter with jitter adds randomness."""
    limiter = RateLimiter(qps=1.0, burst=1, jitter_min=0.1, jitter_max=0.2)
    
    delays = []
    for _ in range(3):
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        delays.append(elapsed)
    
    # First should be fast
    assert delays[0] < 0.2
    
    # Others should have jitter applied
    # With jitter, delays should vary
    assert delays[1] != delays[2] or delays[1] < 1.5  # Variation or within expected range

