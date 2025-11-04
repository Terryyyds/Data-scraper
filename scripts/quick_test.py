#!/usr/bin/env python3
"""Quick test script to verify scraper setup."""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import Post, Comment
from src.rate_limiter import RateLimiter
from src.storage import DataStore


def test_models():
    """Test data models."""
    print("Testing models...")
    
    # Test post creation
    post_data = {
        "id": 123,
        "content": "Test content",
        "timeStr": "2025-01-01",
        "name": "TestUser",
        "comments": [],
        "smallAttach": [],
        "bigAttach": []
    }
    
    post = Post.from_api_response(post_data, "http://test.com")
    assert post.post_id == 123
    assert post.content == "Test content"
    assert post.username == "TestUser"
    
    # Test unique ID
    unique_id = post.get_unique_id()
    assert len(unique_id) == 40  # SHA1 hash
    
    print("✅ Models test passed!")


async def test_rate_limiter():
    """Test rate limiter."""
    print("\nTesting rate limiter...")
    
    limiter = RateLimiter(qps=2.0, burst=2, jitter_min=0, jitter_max=0)
    
    import time
    start = time.monotonic()
    
    # First two should be instant
    await limiter.acquire()
    await limiter.acquire()
    
    elapsed = time.monotonic() - start
    assert elapsed < 0.2
    
    print("✅ Rate limiter test passed!")


def test_storage():
    """Test storage."""
    print("\nTesting storage...")
    
    store = DataStore(data_dir="test_data")
    
    # Clean up test data
    import shutil
    if Path("test_data").exists():
        shutil.rmtree("test_data")
    
    # Test initialization
    assert store.posts_dir.exists()
    assert store.raw_dir.exists()
    
    # Clean up
    shutil.rmtree("test_data")
    
    print("✅ Storage test passed!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Quick Test Suite")
    print("=" * 60)
    
    try:
        test_models()
        await test_rate_limiter()
        test_storage()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

