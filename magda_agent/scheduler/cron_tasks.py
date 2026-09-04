import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Any, Coroutine, Dict, List, Optional
from croniter import croniter

from magda_agent.scheduler.cron import CronScheduler

logger = logging.getLogger(__name__)


class CronTaskManager:
    """
    Manager for Hermes-inspired periodic background tasks (e.g. log cleanup,
    daily summaries, status reports) built on CronScheduler.
    """

    def __init__(
        self,
        scheduler: Optional[CronScheduler] = None,
        result_callback: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None,
    ):
        """
        Initializes the CronTaskManager.

        Args:
            scheduler: Optional CronScheduler instance. If None, a new CronScheduler is created.
            result_callback: Optional async callback for task results.
        """
        self.scheduler = scheduler or CronScheduler(result_callback=result_callback)
        if result_callback and self.scheduler.result_callback is None:
            self.scheduler.result_callback = result_callback

    def register_task(
        self,
        name: str,
        cron_expr: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Registers a generic periodic background task.
        """
        self.scheduler.schedule(cron_expr, func, name=name, *args, **kwargs)

    def register_log_cleanup(
        self,
        name: str,
        log_dir: str | Path,
        max_age_days: int = 7,
        cron_expr: str = "0 2 * * *",
    ) -> None:
        """
        Registers a background job that cleans up log files older than max_age_days.
        """
        async def log_cleanup_task() -> Dict[str, Any]:
            path = Path(log_dir)
            if not path.exists() or not path.is_dir():
                logger.warning(f"Log cleanup path {log_dir} does not exist or is not a directory.")
                return {"status": "skipped", "reason": "directory_not_found", "cleaned_count": 0}

            now_sec = time.time()
            cutoff = now_sec - (max_age_days * 86400)
            cleaned_count = 0

            for entry in path.glob("*.log"):
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    try:
                        entry.unlink()
                        cleaned_count += 1
                        logger.info(f"Cleaned up old log file: {entry}")
                    except Exception as e:
                        logger.error(f"Failed to delete {entry}: {e}")

            return {"status": "success", "cleaned_count": cleaned_count, "log_dir": str(log_dir)}

        self.register_task(name, cron_expr, log_cleanup_task)

    def register_daily_summary(
        self,
        name: str,
        summary_generator: Callable[[], Coroutine[Any, Any, str | Dict[str, Any]]],
        cron_expr: str = "0 8 * * *",
    ) -> None:
        """
        Registers a daily summary generation background task.
        """
        async def summary_task() -> Dict[str, Any]:
            try:
                res = await summary_generator()
                return {"status": "success", "summary": res, "timestamp": datetime.now().isoformat()}
            except Exception as e:
                logger.error(f"Error executing daily summary task {name}: {e}")
                return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

        self.register_task(name, cron_expr, summary_task)

    def register_status_report(
        self,
        name: str,
        report_generator: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
        cron_expr: str = "*/30 * * * *",
    ) -> None:
        """
        Registers a periodic status report background task.
        """
        async def status_report_task() -> Dict[str, Any]:
            try:
                report = await report_generator()
                return {"status": "success", "report": report, "timestamp": datetime.now().isoformat()}
            except Exception as e:
                logger.error(f"Error executing status report task {name}: {e}")
                return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

        self.register_task(name, cron_expr, status_report_task)

    def remove_task(self, name: str) -> bool:
        """
        Removes a registered background task by name.
        """
        initial_count = len(self.scheduler.jobs)
        self.scheduler.jobs = [j for j in self.scheduler.jobs if j["name"] != name]
        return len(self.scheduler.jobs) < initial_count

    def get_tasks(self) -> List[Dict[str, Any]]:
        """
        Returns list of registered jobs and their metadata.
        """
        return [
            {
                "name": job["name"],
                "cron_expr": job["cron_expr"],
                "next_run": job["next_run"],
            }
            for job in self.scheduler.jobs
        ]

    async def tick(self, current_time: Optional[datetime] = None) -> List[Any]:
        """
        Evaluates scheduled jobs against current_time (or now) and executes any due jobs.
        Useful for testing without real-time sleep loops.

        Returns list of results returned from executed jobs.
        """
        now = current_time or self.scheduler._get_now()
        results = []

        for job in self.scheduler.jobs:
            if now >= job["next_run"]:
                func = job["func"]
                try:
                    res = await func(*job["args"], **job["kwargs"])
                    if self.scheduler.result_callback and res is not None:
                        await self.scheduler.result_callback(res)
                    results.append({"name": job["name"], "result": res})
                except Exception as e:
                    logger.error(f"Error during tick execution of job {job['name']}: {e}")
                    results.append({"name": job["name"], "error": str(e)})
                job["next_run"] = job["iterator"].get_next(datetime)

        return results

    async def start(self) -> None:
        """Starts the underlying scheduler loop."""
        await self.scheduler.start()

    async def stop(self) -> None:
        """Stops the underlying scheduler loop."""
        await self.scheduler.stop()
