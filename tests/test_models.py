"""Test data models."""
import pytest
from src.models import Post, Comment, MediaAttachment


def test_post_from_api_response(sample_post_data):
    """Test Post creation from API response."""
    post = Post.from_api_response(sample_post_data, "https://m.ydl.com/ask")
    
    # Check required fields
    assert post.post_id == 970141
    assert post.username == "赤橙黄绿青蓝紫！"
    assert post.content == "真正厉害的人，从不分享过去的痛苦。"
    assert post.publish_time == "今天 14:51"
    assert post.view_count == 3
    assert post.warm_count == 1
    assert post.visit_count == 3
    assert post.post_url == "https://m.ydl.com/ask/detail/970141"
    
    # Check optional fields
    assert post.uid == 15427050
    assert post.gender == 2
    assert post.is_anonymous is False
    assert post.reply_counter == 1
    
    # Check comments
    assert len(post.comments) == 1
    comment = post.comments[0]
    assert comment.username == "暖暖"
    assert comment.comment_id == 4831707
    assert comment.user_type == 1
    assert comment.reply_type == "post"


def test_anonymous_post(sample_anonymous_post):
    """Test anonymous post parsing."""
    post = Post.from_api_response(sample_anonymous_post, "https://m.ydl.com/ask")
    
    assert post.username == "匿名"
    assert post.uid == 0
    assert post.is_anonymous is True


def test_post_with_nested_replies(sample_post_with_reply):
    """Test post with nested reply structure."""
    post = Post.from_api_response(sample_post_with_reply, "https://m.ydl.com/ask")
    
    assert post.post_id == 970135
    assert len(post.comments) == 2
    
    # Check reply to another user
    reply_comment = post.comments[0]
    assert reply_comment.reply_to_username == "豁达的瑞灵"
    assert reply_comment.reply_type == "comment"
    
    # Check direct reply
    direct_reply = post.comments[1]
    assert direct_reply.reply_to_username == "暖暖"


def test_post_unique_id():
    """Test unique ID generation."""
    post_data = {
        "id": 123,
        "content": "Test content",
        "timeStr": "2025-01-01",
        "name": "Test",
        "comments": [],
        "smallAttach": [],
        "bigAttach": []
    }
    
    post1 = Post.from_api_response(post_data, "http://test.com")
    post2 = Post.from_api_response(post_data, "http://test.com")
    
    # Same data should generate same ID
    assert post1.get_unique_id() == post2.get_unique_id()
    
    # Different content should generate different ID
    post_data["content"] = "Different content"
    post3 = Post.from_api_response(post_data, "http://test.com")
    assert post1.get_unique_id() != post3.get_unique_id()


def test_post_to_json():
    """Test JSON serialization."""
    post_data = {
        "id": 123,
        "content": "Test content",
        "timeStr": "2025-01-01",
        "name": "Test",
        "comments": [],
        "smallAttach": [],
        "bigAttach": []
    }
    
    post = Post.from_api_response(post_data, "http://test.com")
    json_str = post.to_json()
    
    assert isinstance(json_str, str)
    assert "Test content" in json_str
    assert post.post_id == 123


def test_comment_required_fields():
    """Test Comment model validation."""
    comment = Comment(
        username="测试用户",
        comment_time="2025-01-01",
        comment_content="测试评论",
        source_url="http://test.com"
    )
    
    assert comment.username == "测试用户"
    assert comment.like_count == 0
    assert comment.reply_count == 0
    assert comment.reply_type == "post"


def test_media_attachment():
    """Test MediaAttachment model."""
    attachment = MediaAttachment(
        type="image",
        url="http://example.com/image.jpg",
        thumbnail_url="http://example.com/thumb.jpg"
    )
    
    assert attachment.type == "image"
    assert attachment.url == "http://example.com/image.jpg"


def test_post_with_media_attachments():
    """Test post with media attachments."""
    post_data = {
        "id": 123,
        "content": "Post with images",
        "timeStr": "2025-01-01",
        "name": "Test",
        "comments": [],
        "smallAttach": ["http://example.com/small1.jpg", "http://example.com/small2.jpg"],
        "bigAttach": ["http://example.com/big1.jpg"]
    }
    
    post = Post.from_api_response(post_data, "http://test.com")
    
    assert len(post.small_attachments) == 2
    assert len(post.big_attachments) == 1
    assert all(a.type == "image" for a in post.small_attachments)


def test_missing_optional_fields():
    """Test handling of missing optional fields."""
    minimal_data = {
        "id": 999,
        "content": "Minimal post",
        "timeStr": "2025-01-01",
        "comments": [],
        "smallAttach": [],
        "bigAttach": []
    }
    
    post = Post.from_api_response(minimal_data, "http://test.com")
    
    assert post.post_id == 999
    assert post.username == "匿名"  # Default for missing name
    assert post.uid is None
    assert post.topic_title is None
    assert post.ask_tag is None

