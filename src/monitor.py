"""Monitoring and alerting system."""
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import structlog
import aiohttp

from src.models import ScrapingStats

logger = structlog.get_logger()


class Monitor:
    """Monitor scraping metrics and send alerts."""
    
    def __init__(self, alert_sink: Optional[str] = None):
        """
        Initialize monitor.
        
        Args:
            alert_sink: Webhook URL for alerts (Slack, Discord, etc.)
        """
        self.alert_sink = alert_sink
        self.metrics_history = []
    
    def record_metrics(self, stats: ScrapingStats):
        """Record metrics snapshot."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "total_posts": stats.total_posts,
            "total_comments": stats.total_comments,
            "new_posts": stats.new_posts,
            "errors": stats.errors,
            "empty_pages": stats.empty_pages,
            "retries": stats.retries,
            "duration_seconds": stats.get_duration(),
            "success_rate": stats.get_success_rate(),
            "http_status_codes": stats.http_status_codes
        }
        
        self.metrics_history.append(metrics)
        logger.info("metrics_recorded", **metrics)
        
        return metrics
    
    async def send_alert(self, message: str, severity: str = "info", context: Dict[str, Any] = None):
        """
        Send alert to configured sink.
        
        Args:
            message: Alert message
            severity: info, warning, error, critical
            context: Additional context data
        """
        if not self.alert_sink:
            logger.warning("alert_sink_not_configured", message=message)
            return
        
        alert = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "message": message,
            "context": context or {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Format for Slack
                if "slack.com" in self.alert_sink:
                    payload = self._format_slack_message(alert)
                else:
                    payload = alert
                
                async with session.post(
                    self.alert_sink,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("alert_sent", message=message, severity=severity)
                    else:
                        logger.error("alert_send_failed", status=response.status)
        except Exception as e:
            logger.error("alert_send_error", error=str(e))
    
    def _format_slack_message(self, alert: Dict) -> Dict:
        """Format alert as Slack message."""
        emoji_map = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":x:",
            "critical": ":fire:"
        }
        
        emoji = emoji_map.get(alert["severity"], ":bell:")
        
        text = f"{emoji} *{alert['severity'].upper()}*: {alert['message']}"
        
        fields = []
        if alert.get("context"):
            for key, value in alert["context"].items():
                fields.append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        return {
            "text": text,
            "attachments": [{
                "fields": fields,
                "ts": int(datetime.now().timestamp())
            }] if fields else []
        }
    
    async def check_health(self, stats: ScrapingStats) -> Dict[str, Any]:
        """
        Check scraping health and send alerts if needed.
        
        Returns:
            Health status dict
        """
        health = {
            "status": "healthy",
            "issues": []
        }
        
        # Check success rate
        success_rate = stats.get_success_rate()
        if success_rate < 50:
            health["status"] = "critical"
            health["issues"].append(f"Success rate too low: {success_rate:.1f}%")
            await self.send_alert(
                f"Success rate dropped to {success_rate:.1f}%",
                severity="critical",
                context={"success_rate": success_rate, "errors": stats.errors}
            )
        elif success_rate < 80:
            health["status"] = "warning"
            health["issues"].append(f"Success rate degraded: {success_rate:.1f}%")
            await self.send_alert(
                f"Success rate at {success_rate:.1f}%",
                severity="warning",
                context={"success_rate": success_rate}
            )
        
        # Check error rate
        error_rate = stats.errors / max(stats.total_posts + stats.errors, 1) * 100
        if error_rate > 10:
            if health["status"] == "healthy":
                health["status"] = "warning"
            health["issues"].append(f"High error rate: {error_rate:.1f}%")
        
        # Check empty pages
        if stats.empty_pages > 5:
            if health["status"] == "healthy":
                health["status"] = "warning"
            health["issues"].append(f"Many empty pages: {stats.empty_pages}")
            await self.send_alert(
                f"Encountered {stats.empty_pages} empty pages",
                severity="warning",
                context={"empty_pages": stats.empty_pages}
            )
        
        # Check HTTP status codes
        if "403" in stats.http_status_codes or "429" in stats.http_status_codes:
            health["status"] = "critical"
            health["issues"].append("Rate limiting or access denied detected")
            await self.send_alert(
                "Access restricted - possible rate limiting or blocking",
                severity="critical",
                context={"http_codes": stats.http_status_codes}
            )
        
        logger.info("health_check", **health)
        
        return health
    
    def generate_report(self, stats: ScrapingStats) -> str:
        """Generate text report of scraping session."""
        duration = stats.get_duration()
        success_rate = stats.get_success_rate()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              壹点灵 (YDL) Scraping Report                    ║
╚══════════════════════════════════════════════════════════════╝

⏱️  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)

📊 Posts & Comments:
   • Total Posts:     {stats.total_posts}
   • New Posts:       {stats.new_posts}
   • Updated Posts:   {stats.updated_posts}
   • Total Comments:  {stats.total_comments}
   • Avg Comments:    {stats.total_comments / max(stats.total_posts, 1):.1f} per post

✅ Success Metrics:
   • Success Rate:    {success_rate:.1f}%
   • Errors:          {stats.errors}
   • Retries:         {stats.retries}
   • Empty Pages:     {stats.empty_pages}

🌐 HTTP Status Codes:
"""
        for code, count in sorted(stats.http_status_codes.items()):
            report += f"   • {code}: {count}\n"
        
        # Performance
        if duration > 0:
            posts_per_min = stats.total_posts / (duration / 60)
            report += f"\n⚡ Performance:\n"
            report += f"   • Posts/minute:    {posts_per_min:.1f}\n"
        
        report += "\n" + "═" * 64 + "\n"
        
        return report
    
    def save_metrics(self, filepath: str = "logs/metrics.jsonl"):
        """Save metrics history to file."""
        from pathlib import Path
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'a', encoding='utf-8') as f:
            for metrics in self.metrics_history:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        
        logger.info("metrics_saved", filepath=filepath, count=len(self.metrics_history))
        self.metrics_history.clear()

