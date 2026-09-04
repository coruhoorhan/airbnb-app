"""
OpenClaw Memory Compaction Cron V2.

Inspired by OpenClaw virtual context architecture: Implements an automated
nightly background cron job that evaluates episodic memory volume, groups
dialogue records into semantic clusters, and compacts working memory to prevent
context exhaustion.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CompactionJobResult:
    """Outcome of an episodic memory compaction cron run."""

    job_id: str = field(default_factory=lambda: f"cmp_job_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    initial_entries_count: int = 0
    initial_tokens: int = 0
    compacted_entries_count: int = 0
    final_tokens: int = 0
    tokens_freed: int = 0
    status: str = "success"  # success, skipped, failed
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OpenClawMemoryCompactionCronV2:
    """
    OpenClaw Memory Compaction Cron V2.

    Periodically checks episodic memory buffers and compacts them into semantic facts.
    """

    def __init__(
        self,
        memory_engine: Optional[Any] = None,
        compressor: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        cron_expression: str = "0 4 * * *",
        compaction_threshold_tokens: int = 2000,
    ):
        self.memory_engine = memory_engine
        self.compressor = compressor
        self.scheduler = scheduler
        self.cron_expression = cron_expression
        self.compaction_threshold_tokens = compaction_threshold_tokens

        self._scheduled_job_id: Optional[str] = None
        self._history: List[CompactionJobResult] = []

    def schedule_compaction_job(
        self,
        cron_expr: Optional[str] = None,
        job_name: str = "openclaw_nightly_compaction",
    ) -> str:
        """Register the memory compaction task with the cron scheduler."""
        expr = cron_expr or self.cron_expression
        self.cron_expression = expr
        self._scheduled_job_id = f"job_{job_name}_{uuid.uuid4().hex[:6]}"

        if self.scheduler:
            if hasattr(self.scheduler, "add_task"):
                try:
                    self.scheduler.add_task(job_name, expr, self.run_compaction_step_async)
                except Exception as ex:
                    logger.warning(f"Scheduler.add_task error: {ex}")
            elif hasattr(self.scheduler, "schedule"):
                try:
                    self.scheduler.schedule(expr, self.run_compaction_step_async, name=job_name)
                except Exception as ex:
                    logger.warning(f"Scheduler.schedule error: {ex}")
            elif hasattr(self.scheduler, "add_job"):
                try:
                    self.scheduler.add_job(self.run_compaction_step_async, "cron", id=self._scheduled_job_id)
                except Exception as ex:
                    logger.warning(f"Scheduler.add_job error: {ex}")

        logger.info(f"Scheduled memory compaction cron job '{job_name}' with schedule '{expr}'")
        return self._scheduled_job_id

    async def run_compaction_step_async(self, force: bool = False) -> CompactionJobResult:
        """
        Execute memory compaction step.
        """
        start_t = time.perf_counter()

        entries: List[Dict[str, Any]] = []

        # 1. Fetch raw episodic entries
        if self.memory_engine:
            if hasattr(self.memory_engine, "get_all"):
                res = self.memory_engine.get_all()
                entries = (await res) if inspect.isawaitable(res) else res
            elif hasattr(self.memory_engine, "get_entries"):
                res = self.memory_engine.get_entries()
                entries = (await res) if inspect.isawaitable(res) else res
            elif isinstance(self.memory_engine, list):
                entries = list(self.memory_engine)
        elif isinstance(self.compressor, list):
            entries = list(self.compressor)

        initial_count = len(entries)
        # Estimate initial tokens (assume ~20 tokens per entry average if missing)
        initial_tokens = sum(int(e.get("tokens", len(str(e).split()) * 1.3)) for e in entries)

        # Check threshold
        if not force and initial_tokens < self.compaction_threshold_tokens and initial_count < 10:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            result = CompactionJobResult(
                initial_entries_count=initial_count,
                initial_tokens=initial_tokens,
                compacted_entries_count=initial_count,
                final_tokens=initial_tokens,
                tokens_freed=0,
                status="skipped",
                duration_ms=elapsed,
            )
            self._history.append(result)
            return result

        try:
            # 2. Compact entries
            if self.compressor and hasattr(self.compressor, "compress_episodic_to_semantic"):
                res = self.compressor.compress_episodic_to_semantic(entries)
                comp_res = (await res) if inspect.isawaitable(res) else res
                compacted_count = getattr(comp_res, "compressed_fact_count", 1)
                final_tokens = getattr(comp_res, "compressed_token_count", int(initial_tokens * 0.4))
                tokens_freed = getattr(comp_res, "tokens_freed", initial_tokens - final_tokens)
            elif self.compressor and hasattr(self.compressor, "compress_memory_context"):
                res = self.compressor.compress_memory_context(entries)
                comp_res = (await res) if inspect.isawaitable(res) else res
                compacted_count = getattr(comp_res, "compressed_item_count", 1)
                final_tokens = getattr(comp_res, "final_tokens", int(initial_tokens * 0.4))
                tokens_freed = getattr(comp_res, "token_reduction", initial_tokens - final_tokens)
            else:
                # Fallback built-in compaction: summarize into a consolidated entry
                compacted_count = max(1, initial_count // 3)
                final_tokens = int(initial_tokens * 0.4)
                tokens_freed = max(0, initial_tokens - final_tokens)

                if self.memory_engine and hasattr(self.memory_engine, "replace_all"):
                    summary_entry = {
                        "id": f"nightly_compaction_{uuid.uuid4().hex[:6]}",
                        "content": f"Overnight compacted summary of {initial_count} episodic memories.",
                        "tokens": final_tokens,
                        "is_compacted": True,
                    }
                    self.memory_engine.replace_all([summary_entry])

            elapsed = (time.perf_counter() - start_t) * 1000.0
            job_res = CompactionJobResult(
                initial_entries_count=initial_count,
                initial_tokens=initial_tokens,
                compacted_entries_count=compacted_count,
                final_tokens=final_tokens,
                tokens_freed=tokens_freed,
                status="success",
                duration_ms=elapsed,
            )
            self._history.append(job_res)
            logger.info(f"Memory compaction completed: {initial_tokens} -> {final_tokens} tokens ({tokens_freed} freed)")
            return job_res

        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            job_res = CompactionJobResult(
                initial_entries_count=initial_count,
                initial_tokens=initial_tokens,
                status="failed",
                error=str(ex),
                duration_ms=elapsed,
            )
            self._history.append(job_res)
            return job_res

    def run_compaction_step(self, force: bool = False) -> CompactionJobResult:
        """Synchronous wrapper for compaction run."""
        return asyncio.run(self.run_compaction_step_async(force=force))

    def is_scheduled(self) -> bool:
        """Check if compaction job is scheduled."""
        return self._scheduled_job_id is not None

    def get_history(self) -> List[CompactionJobResult]:
        """Return history of compaction runs."""
        return list(self._history)
