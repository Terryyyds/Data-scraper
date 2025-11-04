"""Data models for posts and comments."""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, HttpUrl
import hashlib
import json


class MediaAttachment(BaseModel):
    """Media attachment in a post."""
    type: Literal["image", "audio", "video"]
    url: str
    thumbnail_url: Optional[str] = None


class Comment(BaseModel):
    """Comment model."""
    # Required fields
    comment_id: Optional[int] = Field(None, description="评论ID")
    username: str = Field(..., description="评论用户昵称")
    avatar_url: Optional[str] = Field(None, description="评论头像链接")
    user_type: Optional[int] = Field(None, description="身份标签(1=倾诉师/解答师等)")
    user_type_label: Optional[str] = Field(None, description="身份标签文本")
    comment_time: str = Field(..., description="评论时间")
    comment_content: str = Field(..., description="评论内容")
    like_count: int = Field(0, description="点赞/赞同数")
    reply_count: int = Field(0, description="该评论的回复数量")
    reply_to_username: Optional[str] = Field(None, description="被回复的目标用户名")
    reply_type: Literal["post", "comment"] = Field("post", description="回复类型")
    
    # Optional fields
    uid: Optional[int] = Field(None, description="评论用户ID")
    gender: Optional[int] = Field(None, description="性别")
    doctor_id: Optional[int] = Field(None, description="医生/咨询师ID")
    is_zan: Optional[int] = Field(None, description="当前用户是否点赞")
    ip_province: Optional[str] = Field(None, description="IP省份")
    
    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.now, description="抓取时间")
    source_url: str = Field(..., description="来源URL")


class Post(BaseModel):
    """Post model."""
    # Required fields
    post_id: int = Field(..., description="帖子唯一ID")
    username: str = Field(..., description="用户名")
    avatar_url: Optional[str] = Field(None, description="用户头像链接")
    publish_time: str = Field(..., description="发表时间")
    content: str = Field(..., description="帖子内容")
    view_count: int = Field(0, description="阅读数")
    warm_count: int = Field(0, description="温暖数")
    visit_count: int = Field(0, description="看见数")
    topic_title: Optional[str] = Field(None, description="心球名称/话题")
    post_url: str = Field(..., description="原帖链接")
    
    # Optional fields
    uid: Optional[int] = Field(None, description="用户ID")
    gender: Optional[int] = Field(None, description="性别")
    is_anonymous: bool = Field(False, description="是否匿名")
    ask_tag: Optional[str] = Field(None, description="帖子标签")
    topic_id: Optional[int] = Field(None, description="话题ID")
    reply_counter: int = Field(0, description="评论总数")
    is_recommended: Optional[int] = Field(None, description="是否推荐/精选")
    is_hot: Optional[int] = Field(None, description="是否热门")
    is_top: Optional[int] = Field(None, description="是否置顶")
    platform: Optional[str] = Field(None, description="发布平台")
    ip_province: Optional[str] = Field(None, description="IP省份")
    
    # Media attachments
    small_attachments: List[MediaAttachment] = Field(default_factory=list, description="小图附件")
    big_attachments: List[MediaAttachment] = Field(default_factory=list, description="大图附件")
    
    # Comments
    comments: List[Comment] = Field(default_factory=list, description="评论列表")
    
    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.now, description="抓取时间")
    last_updated: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    raw_data: Optional[dict] = Field(None, description="原始响应数据")
    
    def get_unique_id(self) -> str:
        """Generate unique ID based on post_id and content."""
        content_str = f"{self.post_id}_{self.content[:100]}_{self.publish_time}"
        return hashlib.sha1(content_str.encode()).hexdigest()
    
    def to_json(self, include_raw: bool = False) -> str:
        """Convert to JSON string."""
        data = self.model_dump(exclude={"raw_data"} if not include_raw else set())
        return json.dumps(data, ensure_ascii=False, default=str)
    
    @classmethod
    def from_api_response(cls, data: dict, source_url: str) -> "Post":
        """Create Post from API response data."""
        # Parse media attachments
        small_attachments = []
        for att in data.get("smallAttach", []):
            if isinstance(att, str):
                small_attachments.append(MediaAttachment(type="image", url=att))
        
        big_attachments = []
        for att in data.get("bigAttach", []):
            if isinstance(att, str):
                big_attachments.append(MediaAttachment(type="image", url=att))
        
        # Parse comments
        comments = []
        for comment_data in data.get("comments", []):
            comment = Comment(
                comment_id=comment_data.get("id"),
                username=comment_data.get("name", ""),
                avatar_url=comment_data.get("userHead"),
                user_type=comment_data.get("userType") or comment_data.get("user_type"),
                user_type_label="倾诉师/解答师" if comment_data.get("userType") == 1 else "普通用户",
                comment_time=comment_data.get("answerCreateTime") or comment_data.get("time_str", ""),
                comment_content=comment_data.get("content", ""),
                like_count=comment_data.get("zan", 0),
                reply_count=0,  # Not directly available
                reply_to_username=comment_data.get("toName") or comment_data.get("to_name"),
                reply_type="comment" if comment_data.get("toName") else "post",
                uid=comment_data.get("uid"),
                gender=comment_data.get("gender"),
                doctor_id=comment_data.get("doctorId") or comment_data.get("doctor_id"),
                is_zan=comment_data.get("isZan"),
                ip_province=comment_data.get("ipProvince"),
                source_url=source_url
            )
            comments.append(comment)
        
        return cls(
            post_id=data.get("id"),
            username=data.get("name", "匿名"),
            avatar_url=data.get("avatar") or data.get("header"),
            publish_time=data.get("timeStr") or data.get("time_str", ""),
            content=data.get("content", ""),
            view_count=data.get("hits", 0),
            warm_count=data.get("zanCount", 0),
            visit_count=data.get("visitCount", 0),
            topic_title=data.get("topicTitle"),
            post_url=f"https://m.ydl.com/ask/detail/{data.get('id')}",
            uid=data.get("uid"),
            gender=data.get("gender"),
            is_anonymous=data.get("uid") == 0,
            ask_tag=data.get("askTag"),
            topic_id=data.get("topicId"),
            reply_counter=data.get("replyCounter", 0),
            is_recommended=data.get("isTop"),
            is_hot=data.get("isHot"),
            is_top=data.get("isTop"),
            platform=data.get("from"),
            ip_province=data.get("ip"),
            small_attachments=small_attachments,
            big_attachments=big_attachments,
            comments=comments,
            raw_data=data,
            source_url=source_url
        )


class ScrapingStats(BaseModel):
    """Scraping statistics."""
    total_posts: int = 0
    total_comments: int = 0
    new_posts: int = 0
    updated_posts: int = 0
    errors: int = 0
    empty_pages: int = 0
    retries: int = 0
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    http_status_codes: dict = Field(default_factory=dict)
    
    def add_http_status(self, code: int):
        """Add HTTP status code to statistics."""
        self.http_status_codes[str(code)] = self.http_status_codes.get(str(code), 0) + 1
    
    def get_duration(self) -> float:
        """Get duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.total_posts + self.errors
        return (self.total_posts / total * 100) if total > 0 else 0.0


class Checkpoint(BaseModel):
    """Checkpoint for incremental updates."""
    last_post_id: Optional[int] = None
    last_post_time: Optional[str] = None
    last_run_time: datetime = Field(default_factory=datetime.now)
    total_posts_scraped: int = 0
    cursor: Optional[str] = None  # For pagination cursor if available

