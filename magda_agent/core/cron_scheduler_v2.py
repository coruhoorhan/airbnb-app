import asyncio
import logging
from datetime import datetime
from typing import Callable, Coroutine, Dict, Any

from croniter import croniter

logger = logging.getLogger(__name__)


class CronSchedulerV2:
    """
    A background loop scheduler for executing cron-like tasks.
    Inspired by Hermes Agent scheduled operations.
    """

    def __init__(self) -> None:
        """Initialize the CronSchedulerV2."""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._sleep_task: asyncio.Task | None = None

    def add_task(self, name: str, cron_expr: str, func: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """
        Add a task to be scheduled.

        Args:
            name: A unique identifier for the task.
            cron_expr: A cron expression string (e.g., "* * * * *").
            func: An async callable to execute.
        """
        if not croniter.is_valid(cron_expr):
            raise ValueError(f"Invalid cron expression: {cron_expr}")

        self.tasks[name] = {
            "cron_expr": cron_expr,
            "func": func,
            "next_run": croniter(cron_expr, datetime.now()).get_next(datetime)
        }
        logger.info(f"Added scheduled task: {name} with cron {cron_expr}")

        # Wake up the loop if a task is added and it might need to run sooner
        if self._running and self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()

    async def _loop(self) -> None:
        """The main background loop that waits and executes tasks."""
        while self._running:
            now = datetime.now()

            # Find tasks that are ready to run
            to_run = []
            for name, task_info in self.tasks.items():
                if now >= task_info["next_run"]:
                    to_run.append((name, task_info))

            # Execute ready tasks concurrently
            if to_run:
                for name, task_info in to_run:
                    logger.info(f"Executing scheduled task: {name}")
                    try:
                        asyncio.create_task(task_info["func"]())
                    except Exception as e:
                        logger.error(f"Failed to start task {name}: {e}", exc_info=True)

                    # Schedule next run
                    task_info["next_run"] = croniter(task_info["cron_expr"], datetime.now()).get_next(datetime)

            # Calculate sleep time until the next earliest task
            if self.tasks:
                next_runs = [t["next_run"] for t in self.tasks.values()]
                earliest_next_run = min(next_runs)
                now = datetime.now()
                sleep_seconds = (earliest_next_run - now).total_seconds()
                if sleep_seconds < 0:
                    sleep_seconds = 0
            else:
                sleep_seconds = 3600  # Default sleep if no tasks

            # Sleep until next task or cancelled
            if sleep_seconds > 0 and self._running:
                try:
                    self._sleep_task = asyncio.create_task(asyncio.sleep(sleep_seconds))
                    await self._sleep_task
                except asyncio.CancelledError:
                    pass
            elif self._running:
                # Yield control to event loop to avoid infinite synchronous loop
                await asyncio.sleep(0.01)

    def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            return

        self._running = True

        # Reset next run times
        now = datetime.now()
        for task_info in self.tasks.values():
            task_info["next_run"] = croniter(task_info["cron_expr"], now).get_next(datetime)

        self._task = asyncio.create_task(self._loop())
        logger.info("CronSchedulerV2 started.")

    async def stop(self) -> None:
        """Stop the background scheduler loop gracefully."""
        self._running = False
        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()

        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("CronSchedulerV2 stopped.")
