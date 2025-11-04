"""Test scraper functionality."""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.scraper import YDLScraper
from src.models import Post, Checkpoint


@pytest.mark.asyncio
async def test_scraper_initialization():
    """Test scraper initialization."""
    scraper = YDLScraper()
    
    assert scraper.rate_limiter is not None
    assert scraper.stats is not None
    assert scraper.checkpoint is not None
    assert scraper.browser is None
    assert scraper.context is None


def test_checkpoint_load_empty():
    """Test loading checkpoint when file doesn't exist."""
    with patch('pathlib.Path.exists', return_value=False):
        scraper = YDLScraper()
        checkpoint = scraper.checkpoint
        
        assert checkpoint.last_post_id is None
        assert checkpoint.total_posts_scraped == 0


def test_checkpoint_load_existing():
    """Test loading existing checkpoint."""
    checkpoint_data = {
        "last_post_id": 970141,
        "last_post_time": "2025-01-01",
        "last_run_time": "2025-01-01T00:00:00",
        "total_posts_scraped": 100,
        "cursor": None
    }
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value=json.dumps(checkpoint_data)):
        scraper = YDLScraper()
        checkpoint = scraper.checkpoint
        
        assert checkpoint.last_post_id == 970141
        assert checkpoint.total_posts_scraped == 100


def test_checkpoint_save():
    """Test saving checkpoint."""
    scraper = YDLScraper()
    scraper.checkpoint.last_post_id = 999
    scraper.checkpoint.total_posts_scraped = 50
    
    with patch('pathlib.Path.write_text') as mock_write, \
         patch('pathlib.Path.mkdir'):
        scraper._save_checkpoint()
        
        # Verify write was called
        assert mock_write.called
        written_data = mock_write.call_args[0][0]
        data = json.loads(written_data)
        assert data["last_post_id"] == 999
        assert data["total_posts_scraped"] == 50


def test_extract_preloaded_state():
    """Test extraction of preloaded state from HTML."""
    scraper = YDLScraper()
    
    html = '''
    <script>
    window.$G = {
        "env": "9",
        "preloadedState": {
            "data": {
                "code": "200",
                "data": {
                    "data": [
                        {"id": 123, "content": "test"}
                    ]
                }
            }
        }
    };
    </script>
    '''
    
    state = scraper._extract_preloaded_state(html)
    
    assert state is not None
    assert "data" in state
    assert state["data"]["code"] == "200"


def test_extract_preloaded_state_invalid():
    """Test extraction with invalid HTML."""
    scraper = YDLScraper()
    
    html = '<html><body>No preloaded state</body></html>'
    
    state = scraper._extract_preloaded_state(html)
    
    assert state is None


@pytest.mark.asyncio
async def test_scrape_list_page_empty(sample_empty_page):
    """Test scraping empty list page."""
    scraper = YDLScraper()
    
    # Mock browser and page
    mock_page = AsyncMock()
    mock_response = Mock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    
    html_content = f'''
    <script>
    window.$G = {{
        "preloadedState": {json.dumps(sample_empty_page)}
    }};
    </script>
    '''
    mock_page.content = AsyncMock(return_value=html_content)
    mock_page.close = AsyncMock()
    
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    scraper.context = mock_context
    
    posts = await scraper.scrape_list_page()
    
    assert len(posts) == 0
    assert scraper.stats.add_http_status(200)


@pytest.mark.asyncio
async def test_scrape_list_page_with_posts(sample_post_data):
    """Test scraping list page with posts."""
    scraper = YDLScraper()
    
    mock_page = AsyncMock()
    mock_response = Mock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    
    api_response = {
        "data": {
            "code": "200",
            "data": {
                "data": [sample_post_data]
            }
        }
    }
    
    html_content = f'''
    <script>
    window.$G = {{
        "preloadedState": {json.dumps(api_response)}
    }};
    </script>
    '''
    mock_page.content = AsyncMock(return_value=html_content)
    mock_page.close = AsyncMock()
    
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    scraper.context = mock_context
    
    posts = await scraper.scrape_list_page()
    
    assert len(posts) == 1
    assert posts[0].post_id == 970141
    assert scraper.stats.total_posts == 1
    assert scraper.stats.total_comments == 1


@pytest.mark.asyncio
async def test_scrape_incremental_filter():
    """Test incremental scraping with filtering."""
    scraper = YDLScraper()
    scraper.checkpoint.last_post_id = 100
    
    # Mock scrape_list_page to return posts
    posts = [
        Post(
            post_id=99,
            username="User1",
            publish_time="2025-01-01",
            content="Old post",
            post_url="http://test.com/99"
        ),
        Post(
            post_id=101,
            username="User2",
            publish_time="2025-01-02",
            content="New post",
            post_url="http://test.com/101"
        )
    ]
    
    with patch.object(scraper, 'scrape_list_page', return_value=posts), \
         patch.object(scraper, '_save_checkpoint'):
        new_posts = await scraper.scrape_incremental()
    
    # Should only return post with ID > 100
    assert len(new_posts) == 1
    assert new_posts[0].post_id == 101


@pytest.mark.asyncio
async def test_stats_tracking():
    """Test statistics tracking."""
    scraper = YDLScraper()
    
    scraper.stats.total_posts = 10
    scraper.stats.total_comments = 25
    scraper.stats.errors = 2
    scraper.stats.add_http_status(200)
    scraper.stats.add_http_status(200)
    scraper.stats.add_http_status(404)
    
    stats = scraper.get_stats()
    
    assert stats.total_posts == 10
    assert stats.total_comments == 25
    assert stats.errors == 2
    assert stats.http_status_codes["200"] == 2
    assert stats.http_status_codes["404"] == 1
    assert stats.get_success_rate() > 0


def test_stats_success_rate():
    """Test success rate calculation."""
    scraper = YDLScraper()
    
    scraper.stats.total_posts = 8
    scraper.stats.errors = 2
    
    rate = scraper.stats.get_success_rate()
    assert rate == 80.0
    
    # Test with no data
    scraper2 = YDLScraper()
    rate2 = scraper2.stats.get_success_rate()
    assert rate2 == 0.0

