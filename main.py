#!/usr/bin/env python3
"""Main CLI entry point for YDL scraper."""
import asyncio
import argparse
import sys
from pathlib import Path
import structlog

from src.scraper import YDLScraper
from src.storage import DataStore
from src.monitor import Monitor
from config.settings import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False
)

logger = structlog.get_logger()


async def main_scrape(mode: str = "full", export: bool = True, start_date: str = None, 
                     max_pages: int = 500, max_posts: int = None, stop_date: str = None):
    """
    Main scraping function.
    
    Args:
        mode: "full" for complete scrape, "incremental" for updates only
        export: Whether to export dataset at the end
        start_date: Filter posts from this date (YYYY-MM-DD format)
        max_pages: Maximum pages to scrape
        max_posts: Stop when reaching this many posts
        stop_date: Stop when reaching posts before this date (YYYY-MM-DD format)
    """
    from datetime import datetime
    from src.date_utils import filter_posts_by_date
    
    logger.info("scrape_started", mode=mode, target=settings.TARGET_ROOT, start_date=start_date, 
               max_pages=max_pages, max_posts=max_posts, stop_date=stop_date)
    
    # Parse start date (for filtering after scrape)
    filter_start_date = None
    if start_date:
        try:
            filter_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            logger.info("date_filter_enabled", start_date=filter_start_date)
        except ValueError:
            logger.error("invalid_start_date", start_date=start_date)
            return
    
    # Parse stop date (for stopping during scrape)
    stop_date_obj = None
    if stop_date:
        try:
            stop_date_obj = datetime.strptime(stop_date, "%Y-%m-%d")
            logger.info("stop_date_enabled", stop_date=stop_date_obj)
        except ValueError:
            logger.error("invalid_stop_date", stop_date=stop_date)
            return
    
    # Initialize components
    store = DataStore(data_dir=settings.DATA_DIR)
    monitor = Monitor(alert_sink=settings.ALERT_SINK)
    
    # Start scraping
    async with YDLScraper() as scraper:
        try:
            # Perform scraping
            if mode == "incremental":
                posts = await scraper.scrape_incremental()
            else:
                posts = await scraper.scrape_full(max_pages=max_pages, max_posts=max_posts, stop_date=stop_date_obj)
            
            logger.info("scrape_completed", posts_count=len(posts), posts_before_filter=len(posts))
            
            # Apply date filter if specified
            if filter_start_date and posts:
                posts_before = len(posts)
                posts = filter_posts_by_date(posts, filter_start_date)
                logger.info("date_filter_applied", 
                           before=posts_before, 
                           after=len(posts), 
                           filtered_out=posts_before - len(posts))
            
            logger.info("final_posts_count", posts_count=len(posts))
            
            # Save posts
            if posts:
                saved_files = await store.save_posts_batch(posts, include_raw=True)
                logger.info("posts_saved", count=len(saved_files))
            
            # Get statistics
            stats = scraper.get_stats()
            
            # Record metrics
            monitor.record_metrics(stats)
            
            # Health check
            health = await monitor.check_health(stats)
            
            # Generate and print report
            report = monitor.generate_report(stats)
            print(report)
            
            # Save metrics
            monitor.save_metrics()
            
            # Export dataset
            if export and posts:
                dataset_path = store.create_dataset_export()
                logger.info("dataset_exported", path=str(dataset_path))
            
            # Storage stats
            storage_stats = store.get_stats()
            logger.info("storage_stats", **storage_stats)
            
            # Send completion alert
            if monitor.alert_sink:
                await monitor.send_alert(
                    f"Scraping completed: {len(posts)} posts",
                    severity="info",
                    context={
                        "mode": mode,
                        "posts": len(posts),
                        "success_rate": f"{stats.get_success_rate():.1f}%"
                    }
                )
            
        except Exception as e:
            logger.error("scrape_failed", error=str(e), exc_info=True)
            
            # Send error alert
            if monitor.alert_sink:
                await monitor.send_alert(
                    f"Scraping failed: {str(e)}",
                    severity="critical",
                    context={"error": str(e)}
                )
            
            raise


def cli():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="壹点灵 (m.ydl.com/ask) 数据采集工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整抓取
  python main.py --mode full
  
  # 增量更新
  python main.py --mode incremental
  
  # 无头浏览器模式
  python main.py --headless
  
  # 自定义限速
  python main.py --qps 0.3 --burst 1
  
  # 导出数据集
  python main.py --export-only
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="抓取模式: full=完整抓取, incremental=增量更新"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无头浏览器模式"
    )
    
    parser.add_argument(
        "--qps",
        type=float,
        default=settings.QPS_LIMIT,
        help=f"每秒查询数限制 (默认: {settings.QPS_LIMIT})"
    )
    
    parser.add_argument(
        "--burst",
        type=int,
        default=settings.BURST,
        help=f"突发并发数 (默认: {settings.BURST})"
    )
    
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="不导出数据集"
    )
    
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="仅导出现有数据为数据集"
    )
    
    parser.add_argument(
        "--alert-sink",
        type=str,
        help="告警 Webhook URL (Slack/Discord/等)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default=settings.DATA_DIR,
        help=f"数据存储目录 (默认: {settings.DATA_DIR})"
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        help="起始日期过滤 (格式: YYYY-MM-DD, 例如: 2025-01-01)"
    )
    
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3000,
        help="最大抓取页数 (默认: 3000)"
    )
    
    parser.add_argument(
        "--max-posts",
        type=int,
        help="最大帖子数，达到后停止 (例如: 30000)"
    )
    
    parser.add_argument(
        "--stop-date",
        type=str,
        help="停止日期，遇到此日期之前的帖子时停止 (格式: YYYY-MM-DD, 例如: 2024-01-01)"
    )
    
    args = parser.parse_args()
    
    # Update settings
    settings.HEADLESS = args.headless
    settings.QPS_LIMIT = args.qps
    settings.BURST = args.burst
    settings.DATA_DIR = args.data_dir
    if args.alert_sink:
        settings.ALERT_SINK = args.alert_sink
    
    # Export only mode
    if args.export_only:
        logger.info("export_only_mode")
        store = DataStore(data_dir=settings.DATA_DIR)
        dataset_path = store.create_dataset_export()
        storage_stats = store.get_stats()
        logger.info("export_complete", path=str(dataset_path), **storage_stats)
        return
    
    # Run scraping
    try:
        asyncio.run(main_scrape(
            mode=args.mode,
            export=not args.no_export,
            start_date=args.start_date,
            max_pages=args.max_pages,
            max_posts=args.max_posts,
            stop_date=args.stop_date
        ))
    except KeyboardInterrupt:
        logger.info("scrape_interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error("scrape_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

