import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from magda_agent.scheduler.cron_scheduler_v2 import CronSchedulerV2

logger = logging.getLogger(__name__)

class HermesDailyReporterV1:
    """
    A daily report generator and scheduler inspired by Hermes Agent.
    Aggregates agent activities and schedules a daily summary broadcast.
    """

    def __init__(self, scheduler: CronSchedulerV2) -> None:
        """
        Initialize the HermesDailyReporterV1.

        Args:
            scheduler: The CronSchedulerV2 instance to schedule the daily task on.
        """
        self.scheduler = scheduler
        self.activities: List[Dict[str, Any]] = []

    def record_activity(self, activity_type: str, details: str) -> None:
        """
        Record an agent activity to be included in the daily report.

        Args:
            activity_type: The type of activity (e.g., 'tool_call', 'user_reply').
            details: Details about the activity.
        """
        self.activities.append({
            "timestamp": datetime.now().isoformat(),
            "type": activity_type,
            "details": details
        })

    def generate_report(self) -> str:
        """
        Generate a summary report based on recorded activities.

        Returns:
            str: The formatted summary report.
        """
        report_lines = ["Daily Agent Report:"]
        if not self.activities:
            report_lines.append("- No activities recorded today.")
        else:
            for act in self.activities:
                report_lines.append(f"- [{act['timestamp']}] {act['type']}: {act['details']}")

        # Clear activities after report generation
        self.activities.clear()
        return "\n".join(report_lines)

    async def _broadcast_report(self) -> None:
        """
        Internal async task that generates and 'broadcasts' the daily report.
        """
        report = self.generate_report()
        logger.info(f"Broadcasting Daily Report:\n{report}")
        # In a real scenario, this would send a message to a channel (Telegram, Discord, etc.)
        # For now, we simulate broadcasting by yielding to the event loop.
        await asyncio.sleep(0)

    def register_cron(self, cron_expr: str = "0 0 * * *") -> None:
        """
        Register the daily report broadcast task with the cron scheduler.

        Args:
            cron_expr: The cron expression defining when to run the task. Defaults to daily at midnight.
        """
        self.scheduler.add_task("hermes_daily_report", cron_expr, self._broadcast_report)
        logger.info(f"Registered daily report task with cron: {cron_expr}")
