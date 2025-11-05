"""Date parsing utilities for Chinese relative dates."""
from datetime import datetime, timedelta
import re
from typing import Optional
import structlog

logger = structlog.get_logger()


def parse_chinese_date(date_str: str, reference_date: datetime = None) -> Optional[datetime]:
    """
    Parse Chinese relative date strings to datetime.
    
    Supported formats:
    - "今天 12:34" (today HH:MM)
    - "昨天 14:32" (yesterday HH:MM)
    - "前天 10:20" (day before yesterday HH:MM)
    - "10-31 20:56" (MM-DD HH:MM, current year)
    - "2025-01-01 12:00" (YYYY-MM-DD HH:MM)
    - "1小时前" (1 hour ago)
    - "3天前" (3 days ago)
    
    Args:
        date_str: Chinese date string
        reference_date: Reference date for relative dates (default: now)
    
    Returns:
        datetime object or None if parsing fails
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    date_str = date_str.strip()
    
    try:
        # Format: "今天 12:34"
        if date_str.startswith("今天"):
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_str)
            if time_match:
                hour, minute = int(time_match.group(1)), int(time_match.group(2))
                return reference_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Format: "昨天 14:32"
        elif date_str.startswith("昨天"):
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_str)
            if time_match:
                hour, minute = int(time_match.group(1)), int(time_match.group(2))
                yesterday = reference_date - timedelta(days=1)
                return yesterday.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Format: "前天 10:20"
        elif date_str.startswith("前天"):
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_str)
            if time_match:
                hour, minute = int(time_match.group(1)), int(time_match.group(2))
                day_before = reference_date - timedelta(days=2)
                return day_before.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Format: "24-12-20 09:45" (YY-MM-DD HH:MM) - 2-digit year
        elif re.match(r'^\d{2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}', date_str):
            parts = date_str.split()
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00"
            
            date_parts = date_part.split('-')
            if len(date_parts) == 3:
                year_2digit, month, day = map(int, date_parts)
                hour, minute = map(int, time_part.split(':'))
                
                # Convert 2-digit year to 4-digit (assume 20xx for 00-99)
                if year_2digit < 100:
                    year = 2000 + year_2digit
                else:
                    year = year_2digit
                
                return datetime(year, month, day, hour, minute)
        
        # Format: "10-31 20:56" (MM-DD HH:MM)
        elif re.match(r'^\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}', date_str):
            parts = date_str.split()
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00"
            
            month, day = map(int, date_part.split('-'))
            hour, minute = map(int, time_part.split(':'))
            
            # Assume current year, but if month is greater than current month, use previous year
            year = reference_date.year
            if month > reference_date.month:
                year -= 1
            
            return datetime(year, month, day, hour, minute)
        
        # Format: "2025-01-01 12:00" (YYYY-MM-DD HH:MM)
        elif re.match(r'^\d{4}-\d{1,2}-\d{1,2}', date_str):
            # Try different formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        
        # Format: "N小时前", "N分钟前", "N天前"
        relative_match = re.search(r'(\d+)(小时|分钟|天|周|月)前', date_str)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            
            if unit == "分钟":
                return reference_date - timedelta(minutes=amount)
            elif unit == "小时":
                return reference_date - timedelta(hours=amount)
            elif unit == "天":
                return reference_date - timedelta(days=amount)
            elif unit == "周":
                return reference_date - timedelta(weeks=amount)
            elif unit == "月":
                return reference_date - timedelta(days=amount * 30)  # Approximate
        
        logger.warning("date_parse_failed", date_str=date_str)
        return None
        
    except Exception as e:
        logger.error("date_parse_error", date_str=date_str, error=str(e))
        return None


def is_date_in_range(date_obj: Optional[datetime], start_date: datetime, end_date: datetime = None) -> bool:
    """
    Check if a date is within a specified range.
    
    Args:
        date_obj: Date to check
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive, default: now)
    
    Returns:
        True if date is in range, False otherwise
    """
    if date_obj is None:
        return False
    
    if end_date is None:
        end_date = datetime.now()
    
    return start_date <= date_obj <= end_date


def filter_posts_by_date(posts: list, start_date: datetime, end_date: datetime = None) -> list:
    """
    Filter posts by publication date.
    
    Args:
        posts: List of Post objects
        start_date: Start date (inclusive)
        end_date: End date (inclusive, default: now)
    
    Returns:
        Filtered list of posts
    """
    filtered = []
    
    for post in posts:
        post_date = parse_chinese_date(post.publish_time)
        if is_date_in_range(post_date, start_date, end_date):
            filtered.append(post)
    
    return filtered

