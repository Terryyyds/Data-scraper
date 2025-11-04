#!/usr/bin/env python3
"""Data analysis script for scraped YDL posts."""
import sys
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_dataset(dataset_path="data/dataset.jsonl"):
    """Load all posts from dataset."""
    posts = []
    
    dataset_file = Path(dataset_path)
    if not dataset_file.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        print("Run the scraper first: python main.py --mode full")
        return posts
    
    with open(dataset_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                posts.append(json.loads(line))
            except Exception as e:
                print(f"⚠️  Failed to parse line: {e}")
    
    return posts


def analyze_posts(posts):
    """Analyze post statistics."""
    if not posts:
        print("No posts to analyze")
        return
    
    print("=" * 70)
    print("📊 壹点灵数据分析报告")
    print("=" * 70)
    print()
    
    # Basic stats
    print("📈 基本统计")
    print(f"  • 总帖子数: {len(posts)}")
    
    total_comments = sum(len(p.get('comments', [])) for p in posts)
    print(f"  • 总评论数: {total_comments}")
    print(f"  • 平均评论数: {total_comments / len(posts):.1f}")
    
    total_views = sum(p.get('view_count', 0) for p in posts)
    print(f"  • 总阅读数: {total_views:,}")
    print(f"  • 平均阅读数: {total_views / len(posts):.0f}")
    
    print()
    
    # User stats
    print("👥 用户统计")
    usernames = [p.get('username', '未知') for p in posts]
    user_counts = Counter(usernames)
    
    anonymous_count = sum(1 for p in posts if p.get('is_anonymous', False))
    print(f"  • 独立用户: {len(user_counts)}")
    print(f"  • 匿名帖子: {anonymous_count} ({anonymous_count/len(posts)*100:.1f}%)")
    
    print(f"\n  Top 5 活跃用户:")
    for username, count in user_counts.most_common(5):
        print(f"    - {username}: {count} 帖子")
    
    print()
    
    # Topic stats
    print("🏷️  话题统计")
    topics = [p.get('topic_title', '') for p in posts if p.get('topic_title')]
    
    if topics:
        topic_counts = Counter(topics)
        print(f"  • 话题总数: {len(topic_counts)}")
        print(f"  • 带话题帖子: {len(topics)} ({len(topics)/len(posts)*100:.1f}%)")
        
        print(f"\n  热门话题:")
        for topic, count in topic_counts.most_common(5):
            print(f"    - {topic}: {count} 帖子")
    else:
        print("  • 无话题数据")
    
    print()
    
    # Content stats
    print("📝 内容统计")
    content_lengths = [len(p.get('content', '')) for p in posts]
    avg_length = sum(content_lengths) / len(content_lengths)
    
    print(f"  • 平均内容长度: {avg_length:.0f} 字符")
    print(f"  • 最短帖子: {min(content_lengths)} 字符")
    print(f"  • 最长帖子: {max(content_lengths)} 字符")
    
    print()
    
    # Engagement stats
    print("💬 互动统计")
    
    # Posts with most comments
    posts_by_comments = sorted(posts, key=lambda p: len(p.get('comments', [])), reverse=True)
    print(f"\n  评论最多的帖子:")
    for post in posts_by_comments[:3]:
        content_preview = post.get('content', '')[:40] + '...'
        print(f"    - [{post.get('post_id')}] {content_preview}")
        print(f"      评论: {len(post.get('comments', []))}, 阅读: {post.get('view_count', 0)}")
    
    # Posts with most views
    posts_by_views = sorted(posts, key=lambda p: p.get('view_count', 0), reverse=True)
    print(f"\n  阅读最多的帖子:")
    for post in posts_by_views[:3]:
        content_preview = post.get('content', '')[:40] + '...'
        print(f"    - [{post.get('post_id')}] {content_preview}")
        print(f"      阅读: {post.get('view_count', 0)}, 温暖: {post.get('warm_count', 0)}")
    
    print()
    
    # Comment analysis
    if total_comments > 0:
        print("💭 评论分析")
        
        # User types in comments
        comment_user_types = []
        for post in posts:
            for comment in post.get('comments', []):
                user_type = comment.get('user_type')
                if user_type == 1:
                    comment_user_types.append('咨询师')
                else:
                    comment_user_types.append('普通用户')
        
        type_counts = Counter(comment_user_types)
        print(f"  • 咨询师评论: {type_counts.get('咨询师', 0)}")
        print(f"  • 普通用户评论: {type_counts.get('普通用户', 0)}")
        
        # Reply types
        reply_types = []
        for post in posts:
            for comment in post.get('comments', []):
                reply_types.append(comment.get('reply_type', 'post'))
        
        reply_counts = Counter(reply_types)
        print(f"\n  • 回复主帖: {reply_counts.get('post', 0)}")
        print(f"  • 回复评论: {reply_counts.get('comment', 0)}")
    
    print()
    print("=" * 70)
    print("✅ 分析完成")
    print("=" * 70)


def export_summary(posts, output_file="data/summary.json"):
    """Export summary statistics to JSON."""
    if not posts:
        return
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_posts": len(posts),
        "total_comments": sum(len(p.get('comments', [])) for p in posts),
        "total_views": sum(p.get('view_count', 0) for p in posts),
        "unique_users": len(set(p.get('username', '') for p in posts)),
        "anonymous_posts": sum(1 for p in posts if p.get('is_anonymous', False)),
        "topics": len(set(p.get('topic_title', '') for p in posts if p.get('topic_title')))
    }
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 Summary exported to: {output_path}")


def main():
    """Main analysis function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze scraped YDL data")
    parser.add_argument(
        "--dataset",
        default="data/dataset.jsonl",
        help="Path to dataset file"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export summary to JSON"
    )
    
    args = parser.parse_args()
    
    # Load data
    print("Loading dataset...")
    posts = load_dataset(args.dataset)
    
    if not posts:
        return
    
    print(f"✅ Loaded {len(posts)} posts\n")
    
    # Analyze
    analyze_posts(posts)
    
    # Export summary
    if args.export:
        export_summary(posts)


if __name__ == "__main__":
    main()

