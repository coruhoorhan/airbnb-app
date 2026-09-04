import asyncio
import logging
from typing import Callable, Any, Optional, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

class CronScheduler:
    """
    A scheduler for periodic background tasks like daily reports and nightly backups.
    Wraps APScheduler's AsyncIOScheduler.
    """
    def __init__(self) -> None:
        """
        Initializes the CronScheduler with an AsyncIOScheduler instance.
        """
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    def start(self) -> None:
        """
        Starts the scheduler if it is not already running.
        """
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("CronScheduler started.")
        else:
            logger.warning("CronScheduler is already running.")

    def stop(self) -> None:
        """
        Stops the scheduler if it is running.
        """
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("CronScheduler stopped.")
        else:
            logger.warning("CronScheduler is not running.")

    def add_task(
        self,
        func: Callable[..., Any],
        cron_expression: str,
        job_id: str,
        kwargs: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Adds a scheduled task to the scheduler using a cron expression.

        Args:
            func: The asynchronous function to execute.
            cron_expression: A standard cron expression (e.g., "0 0 * * *" for daily at midnight).
                             APScheduler uses specific fields, so we use CronTrigger.from_crontab.
            job_id: A unique identifier for the job.
            kwargs: Optional keyword arguments to pass to the function.
        """
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                kwargs=kwargs or {},
                replace_existing=True
            )
            logger.info(f"Task '{job_id}' added with cron expression '{cron_expression}'.")
        except ValueError as e:
            logger.error(f"Failed to add task '{job_id}' due to invalid cron expression: {e}")
            raise
