import asyncio
import logging
from typing import Optional

from magda_agent.scheduler.cron_scheduler_v2 import CronSchedulerV2

logger = logging.getLogger(__name__)


class NightlyBackupManagerV4:
    """
    Manages cron nightly backups.
    Inspired by Hermes Agent scheduled operations.
    """

    def __init__(self, scheduler: CronSchedulerV2) -> None:
        """
        Initialize the NightlyBackupManagerV4.

        Args:
            scheduler: The CronSchedulerV2 instance to schedule the nightly task on.
        """
        self.scheduler = scheduler
        self._backup_task_name = "nightly_backup_v4"
        self._cron_expression = "0 2 * * *"  # Run at 2:00 AM every day

    def schedule_backup(self) -> None:
        """
        Schedules the nightly backup using the provided cron scheduler.
        """
        self.scheduler.add_task(
            name=self._backup_task_name,
            cron_expr=self._cron_expression,
            func=self.perform_backup
        )
        logger.info(f"Scheduled {self._backup_task_name} with cron {self._cron_expression}")

    async def perform_backup(self) -> None:
        """
        Performs the actual backup logic.
        """
        logger.info("Starting nightly backup v4...")
        # Simulate backup work
        await asyncio.sleep(0.1)
        logger.info("Completed nightly backup v4 successfully.")
