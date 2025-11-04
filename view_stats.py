#!/usr/bin/env python3
"""Quick data statistics viewer."""
import json
from datetime import datetime
from collections import Counter
from src.date_utils import parse_chinese_date

def main():
    """Display data statistics."""
    # Read dataset
    print("📊 Loading data...")
    with open('data/dataset.jsonl', 'r') as f:
        posts = [json.loads(line) for line in f]
    
    print(f"\n{'='*60}")
    print("📈 壹点灵数据统计报告")
    print(f"{'='*60}\n")
    
    # Basic stats
    print("📝 基本统计:")
    print(f"  总帖子数: {len(posts):,}")
    print(f"  总评论数: {sum(p['reply_counter'] for p in posts):,}")
    print(f"  平均评论数: {sum(p['reply_counter'] for p in posts) / len(posts):.2f}")
    print(f"  总浏览量: {sum(p.get('view_count', 0) for p in posts):,}")
    print(f"  平均浏览量: {sum(p.get('view_count', 0) for p in posts) / len(posts):.1f}")
    
    # Date range
    print("\n📅 日期范围:")
    dates = [parse_chinese_date(p['publish_time']) for p in posts]
    valid_dates = [d for d in dates if d is not None]
    if valid_dates:
        print(f"  最早日期: {min(valid_dates).strftime('%Y-%m-%d %H:%M')}")
        print(f"  最新日期: {max(valid_dates).strftime('%Y-%m-%d %H:%M')}")
        print(f"  时间跨度: {(max(valid_dates) - min(valid_dates)).days} 天")
    
    # Top posts by comments
    print("\n💬 评论最多的帖子 (Top 10):")
    top_posts = sorted(posts, key=lambda p: p['reply_counter'], reverse=True)[:10]
    for i, post in enumerate(top_posts, 1):
        print(f"  {i}. ID={post['post_id']}, 评论={post['reply_counter']}, 时间={post['publish_time']}")
        content_preview = post['content'][:50].replace('\n', ' ')
        print(f"     内容: {content_preview}...")
    
    # Top posts by views
    print("\n👀 浏览最多的帖子 (Top 10):")
    top_views = sorted(posts, key=lambda p: p.get('view_count', 0), reverse=True)[:10]
    for i, post in enumerate(top_views, 1):
        print(f"  {i}. ID={post['post_id']}, 浏览={post.get('view_count', 0)}, 评论={post['reply_counter']}")
        content_preview = post['content'][:50].replace('\n', ' ')
        print(f"     内容: {content_preview}...")
    
    # Gender distribution
    print("\n👥 性别分布:")
    genders = Counter(p.get('gender', 0) for p in posts)
    gender_map = {0: '未知', 1: '女', 2: '男'}
    for gender, count in genders.most_common():
        pct = count / len(posts) * 100
        print(f"  {gender_map.get(gender, '其他')}: {count:,} ({pct:.1f}%)")
    
    # Anonymous posts
    anon_count = sum(1 for p in posts if p.get('is_anonymous', False))
    print(f"\n🕵️  匿名帖子: {anon_count:,} ({anon_count/len(posts)*100:.1f}%)")
    
    # Posts by month
    print("\n📆 每月帖子数:")
    month_counter = Counter()
    for date in valid_dates:
        month_key = date.strftime('%Y-%m')
        month_counter[month_key] += 1
    
    for month, count in sorted(month_counter.items()):
        bar = '█' * (count // 50)
        print(f"  {month}: {count:4d} {bar}")
    
    # Topic distribution
    print("\n🏷️  主题分布 (Top 10):")
    topics = Counter(p.get('topic_title', '无') for p in posts if p.get('topic_title'))
    for topic, count in topics.most_common(10):
        pct = count / len(posts) * 100
        print(f"  {topic}: {count} ({pct:.1f}%)")
    
    print(f"\n{'='*60}")
    print("✅ 统计完成！")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

