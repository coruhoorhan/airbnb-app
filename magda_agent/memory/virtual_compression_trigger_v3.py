"""
MemGPT Virtual Context Compression Trigger V3.

Inspired by MemGPT virtual context trends: Implements a dedicated subagent trigger
responsible for evaluating dialogue history token volume and periodically initiating
context compression when threshold limits are reached.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CompressionTriggerResult:
    """Represents the outcome of a compression trigger evaluation."""

    triggered: bool
    initial_tokens: int
    threshold_tokens: int
    max_tokens: int
    final_tokens: int
    tokens_saved: int
    compressed_history: List[Any]
    execution_time_ms: float = 0.0
    trigger_id: str = field(default_factory=lambda: f"trig_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VirtualContextCompressionTriggerV3:
    """
    Subagent trigger that monitors ongoing conversational dialogue history,
    detects when token capacity crosses warning thresholds, and delegates
    context compression to compression engines or subagents.
    """

    def __init__(
        self,
        max_context_tokens: int = 4000,
        trigger_threshold_ratio: float = 0.80,
        compressor: Optional[Any] = None,
        compress_fn: Optional[Callable[[List[Any], Dict[str, Any]], Coroutine[Any, Any, List[Any]]]] = None,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.trigger_threshold_ratio = trigger_threshold_ratio
        self.compressor = compressor
        self.compress_fn = compress_fn
        self.metrics = {
            "evaluations_count": 0,
            "triggers_count": 0,
            "total_tokens_saved": 0,
            "last_trigger_time": None,
        }

    @property
    def threshold_tokens(self) -> int:
        """Returns the token count threshold that initiates compression."""
        return int(self.max_context_tokens * self.trigger_threshold_ratio)

    def estimate_tokens(self, item: Any) -> int:
        """Estimates token length using word-count heuristic factor."""
        if isinstance(item, dict):
            text = item.get("content") or item.get("text") or item.get("message") or str(item)
        elif hasattr(item, "content"):
            text = getattr(item, "content")
        else:
            text = str(item)

        words = len(text.split())
        return max(1, int(words * 1.3))

    def calculate_total_tokens(self, dialogue_history: List[Any]) -> int:
        """Calculates aggregate estimated token volume of dialogue history."""
        return sum(self.estimate_tokens(msg) for msg in dialogue_history)

    def should_compress(self, dialogue_history: List[Any]) -> Tuple[bool, int, int]:
        """
        Evaluates whether current dialogue token count meets or exceeds compression threshold.
        Returns (should_compress, current_tokens, threshold_tokens).
        """
        current_tokens = self.calculate_total_tokens(dialogue_history)
        threshold = self.threshold_tokens
        return (current_tokens >= threshold, current_tokens, threshold)

    async def _execute_compression(
        self,
        dialogue_history: List[Any],
        context_metadata: Dict[str, Any],
    ) -> List[Any]:
        """Dispatches compression to the registered compressor engine, subagent, or callback."""
        # 1. Custom compress_fn
        if self.compress_fn:
            try:
                res = self.compress_fn(dialogue_history, context_metadata)
                if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                    return await res
                return res
            except Exception as e:
                logger.error(f"Custom compress_fn failed: {e}")

        # 2. Compressor object (e.g. VirtualContextCompressionPluginV4 or ContextEngine)
        if self.compressor:
            try:
                if hasattr(self.compressor, "compact_context"):
                    res = self.compressor.compact_context(
                        dialogue_history,
                        target_max_tokens=int(self.max_context_tokens * 0.5),
                    )
                    if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                        return await res
                    return res
                elif hasattr(self.compressor, "compact"):
                    res = self.compressor.compact(
                        dialogue_history,
                        metadata=context_metadata,
                    )
                    if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                        return await res
                    return res
            except Exception as e:
                logger.error(f"Compressor object execution failed: {e}")

        # 3. Default fallback heuristic compression
        if len(dialogue_history) <= 2:
            return list(dialogue_history)

        split_idx = len(dialogue_history) // 2
        older_half = dialogue_history[:split_idx]
        recent_half = dialogue_history[split_idx:]

        snippets = []
        for it in older_half:
            c = it.get("content") if isinstance(it, dict) else str(it)
            short = " ".join(c.split()[:4])
            snippets.append(short)

        summary_entry = {
            "id": f"summary_{uuid.uuid4().hex[:6]}",
            "content": f"[Periodic Dialogue Summary ({len(older_half)} turns)]: " + "; ".join(snippets[:3]),
            "is_summary": True,
            "timestamp": time.time(),
        }

        return [summary_entry] + recent_half

    async def evaluate_and_trigger(
        self,
        dialogue_history: List[Any],
        context_metadata: Optional[Dict[str, Any]] = None,
    ) -> CompressionTriggerResult:
        """
        Evaluates dialogue history and triggers compression if threshold is crossed.
        """
        self.metrics["evaluations_count"] += 1
        context_metadata = context_metadata or {}
        start_time = time.perf_counter()

        needs_compress, current_tokens, threshold = self.should_compress(dialogue_history)

        if not needs_compress:
            duration = (time.perf_counter() - start_time) * 1000.0
            return CompressionTriggerResult(
                triggered=False,
                initial_tokens=current_tokens,
                threshold_tokens=threshold,
                max_tokens=self.max_context_tokens,
                final_tokens=current_tokens,
                tokens_saved=0,
                compressed_history=list(dialogue_history),
                execution_time_ms=duration,
            )

        logger.info(
            f"Compression triggered: Dialogue size {current_tokens} exceeded threshold {threshold} "
            f"({self.trigger_threshold_ratio * 100:.0f}% of {self.max_context_tokens})"
        )

        compressed = await self._execute_compression(dialogue_history, context_metadata)
        final_tokens = self.calculate_total_tokens(compressed)
        tokens_saved = max(0, current_tokens - final_tokens)
        duration = (time.perf_counter() - start_time) * 1000.0

        self.metrics["triggers_count"] += 1
        self.metrics["total_tokens_saved"] += tokens_saved
        self.metrics["last_trigger_time"] = time.time()

        return CompressionTriggerResult(
            triggered=True,
            initial_tokens=current_tokens,
            threshold_tokens=threshold,
            max_tokens=self.max_context_tokens,
            final_tokens=final_tokens,
            tokens_saved=tokens_saved,
            compressed_history=compressed,
            execution_time_ms=duration,
        )

    def evaluate_and_trigger_sync(
        self,
        dialogue_history: List[Any],
        context_metadata: Optional[Dict[str, Any]] = None,
    ) -> CompressionTriggerResult:
        """Synchronous wrapper for trigger evaluation."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.evaluate_and_trigger(dialogue_history, context_metadata)
                    )
                )
                return future.result()
        else:
            return asyncio.run(self.evaluate_and_trigger(dialogue_history, context_metadata))
