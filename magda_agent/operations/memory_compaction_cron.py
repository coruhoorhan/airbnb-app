import asyncio
import logging
from typing import Any

from magda_agent.operations.cron_v3 import HermesCronSchedulerV3
from magda_agent.memory.compaction import MemoryCompactor

logger = logging.getLogger(__name__)

def schedule_memory_compaction(scheduler: HermesCronSchedulerV3, compactor: MemoryCompactor, cron_expr: str = "0 3 * * *") -> None:
    """
    Schedules an overnight job to automatically compact episodic and working memory.

    Args:
        scheduler: The instance of HermesCronSchedulerV3 used to schedule the job.
        compactor: The MemoryCompactor instance that performs the actual compaction.
        cron_expr: The cron expression defining when the compaction runs (defaults to 3:00 AM daily).
    """

    async def compaction_job() -> None:
        """The async wrapper job that executes memory compaction."""
        logger.info("Starting scheduled memory compaction job.")
        try:
            # We run it in a thread if it is synchronous, but MemoryCompactor.compact_memory is synchronous
            # so we just call it. However, it's generally best to use asyncio.to_thread for long synchronous ops.
            await asyncio.to_thread(compactor.compact_memory)
            logger.info("Successfully completed scheduled memory compaction job.")
        except Exception as e:
            logger.error(f"Failed scheduled memory compaction job: {e}")

    # Schedule the background task in HermesCronSchedulerV3
    scheduler.schedule(cron_expr, compaction_job, name="memory_compaction")
    logger.info(f"Scheduled memory compaction with cron expression: {cron_expr}")
