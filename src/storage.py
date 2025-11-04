"""Data storage and deduplication."""
import json
import hashlib
from pathlib import Path
from typing import List, Set, Optional
from datetime import datetime
import structlog
import aiofiles

from src.models import Post

logger = structlog.get_logger()


class DataStore:
    """Storage manager for scraped data."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize data store."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir = self.data_dir / "posts"
        self.posts_dir.mkdir(exist_ok=True)
        self.raw_dir = self.data_dir / "raw"
        self.raw_dir.mkdir(exist_ok=True)
        self.seen_ids: Set[str] = set()
        self._load_seen_ids()
    
    def _load_seen_ids(self):
        """Load previously seen post IDs."""
        seen_file = self.data_dir / "seen_ids.txt"
        if seen_file.exists():
            self.seen_ids = set(seen_file.read_text().splitlines())
            logger.info("loaded_seen_ids", count=len(self.seen_ids))
    
    def _save_seen_ids(self):
        """Save seen post IDs."""
        seen_file = self.data_dir / "seen_ids.txt"
        seen_file.write_text("\n".join(sorted(self.seen_ids)))
    
    def is_duplicate(self, post: Post) -> bool:
        """Check if post is duplicate."""
        unique_id = post.get_unique_id()
        return unique_id in self.seen_ids
    
    def mark_seen(self, post: Post):
        """Mark post as seen."""
        unique_id = post.get_unique_id()
        self.seen_ids.add(unique_id)
    
    async def save_post(self, post: Post, include_raw: bool = True) -> Path:
        """Save post to disk."""
        # Check for duplicates
        if self.is_duplicate(post):
            logger.debug("duplicate_post_skipped", post_id=post.post_id)
            return None
        
        # Save as JSON
        filename = f"{post.post_id}_{post.get_unique_id()[:8]}.json"
        filepath = self.posts_dir / filename
        
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(post.to_json(include_raw=include_raw))
        
        # Save raw data separately
        if include_raw and post.raw_data:
            raw_filepath = self.raw_dir / f"{post.post_id}_raw.json"
            async with aiofiles.open(raw_filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(post.raw_data, ensure_ascii=False, indent=2))
        
        self.mark_seen(post)
        logger.info("post_saved", post_id=post.post_id, filepath=str(filepath))
        
        return filepath
    
    async def save_posts_batch(self, posts: List[Post], include_raw: bool = True) -> List[Path]:
        """Save multiple posts."""
        saved_files = []
        
        for post in posts:
            filepath = await self.save_post(post, include_raw=include_raw)
            if filepath:
                saved_files.append(filepath)
        
        # Update seen IDs file
        self._save_seen_ids()
        
        logger.info("batch_saved", count=len(saved_files), duplicates=len(posts) - len(saved_files))
        
        return saved_files
    
    def get_all_posts(self) -> List[Path]:
        """Get all saved post files."""
        return sorted(self.posts_dir.glob("*.json"))
    
    async def load_post(self, filepath: Path) -> Optional[Post]:
        """Load post from file."""
        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                return Post(**data)
        except Exception as e:
            logger.error("post_load_failed", filepath=str(filepath), error=str(e))
            return None
    
    def create_dataset_export(self, output_file: str = "dataset.jsonl"):
        """Export all posts as JSONL dataset."""
        output_path = self.data_dir / output_file
        posts = self.get_all_posts()
        
        with open(output_path, 'w', encoding='utf-8') as out:
            for post_file in posts:
                try:
                    post_data = json.loads(post_file.read_text(encoding='utf-8'))
                    out.write(json.dumps(post_data, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.error("export_error", file=str(post_file), error=str(e))
        
        logger.info("dataset_exported", output=str(output_path), posts=len(posts))
        return output_path
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        posts = self.get_all_posts()
        total_size = sum(p.stat().st_size for p in posts)
        
        return {
            "total_posts": len(posts),
            "unique_ids": len(self.seen_ids),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "posts_dir": str(self.posts_dir),
            "raw_dir": str(self.raw_dir)
        }

