"""
Virtual Context Compression V4 Plugin.

Inspired by MemGPT context management trends: A Context Engine plugin implementing
selective context compression and dynamic memory paging from working memory
to episodic memory to maintain strict token budget constraints.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class VirtualContextCompressionPluginV4:
    """
    Context Engine plugin that monitors context token limits,
    selectively compresses low-importance or older memory entries,
    and pages compressed memory records to episodic storage.
    """

    def __init__(
        self,
        max_tokens: int = 3500,
        importance_threshold: float = 0.5,
        compression_ratio: float = 0.4,
        llm_client: Optional[Any] = None,
        working_memory: Optional[Any] = None,
        episodic_memory: Optional[Any] = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.importance_threshold = importance_threshold
        self.compression_ratio = compression_ratio
        self.llm_client = llm_client
        self.working_memory = working_memory
        self.episodic_memory = episodic_memory
        self.config: Dict[str, Any] = {}
        self.metrics = {
            "compaction_runs": 0,
            "items_compressed": 0,
            "items_paged_out": 0,
            "tokens_saved": 0,
        }

    def estimate_tokens(self, item: Any) -> int:
        """Estimates token length using standard word count factor."""
        if isinstance(item, dict):
            text = item.get("content") or item.get("text") or str(item)
        elif hasattr(item, "content"):
            text = getattr(item, "content")
        else:
            text = str(item)
        words = len(text.split())
        return max(1, int(words * 1.3))

    def _get_item_importance(self, item: Any) -> float:
        """Extracts importance score from memory item (0.0 to 1.0)."""
        if isinstance(item, dict):
            return float(item.get("importance", item.get("score", 0.5)))
        elif hasattr(item, "importance"):
            return float(getattr(item, "importance", 0.5))
        return 0.5

    def _get_item_id(self, item: Any, default_idx: int) -> str:
        if isinstance(item, dict):
            return item.get("id") or item.get("entry_id") or f"entry_{default_idx}"
        elif hasattr(item, "id"):
            return getattr(item, "id")
        return f"entry_{default_idx}"

    async def _summarize_items(self, items: List[Any]) -> str:
        """Compresses a list of items using LLM or rule-based extractive summary."""
        texts = []
        for it in items:
            if isinstance(it, dict):
                texts.append(it.get("content") or it.get("text") or str(it))
            elif hasattr(it, "content"):
                texts.append(getattr(it, "content"))
            else:
                texts.append(str(it))

        raw_content = "\n".join(texts)

        if self.llm_client and hasattr(self.llm_client, "generate"):
            prompt = (
                "Synthesize and compress the following historical conversational context into "
                "a concise, dense factual summary preserving all core facts, decisions, and constraints:\n\n"
                f"{raw_content}\n\n"
                "Compressed Context Summary:"
            )
            try:
                res = self.llm_client.generate(prompt)
                if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, str) and len(res.strip()) > 0:
                    return f"[Compressed History]: {res.strip()}"
            except Exception as e:
                logger.warning(f"LLM compression generation failed: {e}. Falling back to rule-based compression.")

        # Fallback extractive rule-based concise summary
        short_lines = []
        for t in texts:
            clean = t.strip().replace("\n", " ")
            shortened = " ".join(clean.split()[:3])
            if shortened not in short_lines:
                short_lines.append(shortened)

        return f"[Summary ({len(items)} items)]: " + "; ".join(short_lines[:3])

    async def compact_context(
        self,
        context_items: List[Any],
        target_max_tokens: Optional[int] = None,
        user_id: int = 1,
    ) -> List[Any]:
        """
        Evaluates context token volume and performs virtual context compression
        and episodic paging when exceeding limits.
        """
        limit = target_max_tokens if target_max_tokens is not None else self.max_tokens
        self.metrics["compaction_runs"] += 1

        total_tokens = sum(self.estimate_tokens(it) for it in context_items)
        if total_tokens <= limit or not context_items:
            return context_items

        tokens_to_free = total_tokens - limit
        logger.info(f"Context size {total_tokens} exceeds max {limit}. Compressing {tokens_to_free} tokens.")

        # 1. Partition items into high-importance (keep) and low-importance (candidates for compression)
        high_importance: List[Any] = []
        candidates_for_compression: List[Any] = []

        for it in context_items:
            imp = self._get_item_importance(it)
            if imp >= self.importance_threshold:
                high_importance.append(it)
            else:
                candidates_for_compression.append(it)

        # If not enough low importance candidates, take older items from high_importance
        if len(candidates_for_compression) < 2 and len(context_items) > 2:
            split_point = len(context_items) // 2
            candidates_for_compression = context_items[:split_point]
            high_importance = context_items[split_point:]

        # 2. Compress the candidate items
        compressed_summary_text = await self._summarize_items(candidates_for_compression)
        compressed_entry = {
            "id": f"comp_{uuid.uuid4().hex[:8]}",
            "content": compressed_summary_text,
            "importance": 0.8,
            "is_compressed_summary": True,
            "source_items_count": len(candidates_for_compression),
            "timestamp": time.time(),
        }

        # 3. Page out candidate items to episodic memory and remove from working memory
        if self.episodic_memory:
            for item in candidates_for_compression:
                try:
                    c = item.get("content") if isinstance(item, dict) else str(item)
                    if hasattr(self.episodic_memory, "add_event"):
                        res = self.episodic_memory.add_event(user_id=user_id, event=c)
                        if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                            await res
                    elif hasattr(self.episodic_memory, "store"):
                        res = self.episodic_memory.store(c)
                        if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                            await res
                except Exception as e:
                    logger.warning(f"Failed to page event to episodic memory: {e}")

        if self.working_memory:
            for idx, item in enumerate(candidates_for_compression):
                item_id = self._get_item_id(item, idx)
                try:
                    if hasattr(self.working_memory, "remove"):
                        res = self.working_memory.remove(item_id, user_id=user_id)
                        if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                            await res
                except Exception as e:
                    logger.warning(f"Failed to remove item {item_id} from working memory: {e}")

        self.metrics["items_compressed"] += len(candidates_for_compression)
        self.metrics["items_paged_out"] += len(candidates_for_compression)

        orig_cand_tokens = sum(self.estimate_tokens(it) for it in candidates_for_compression)
        new_summary_tokens = self.estimate_tokens(compressed_entry)
        saved = max(0, orig_cand_tokens - new_summary_tokens)
        self.metrics["tokens_saved"] += saved

        # 4. Resulting context is the compressed summary followed by the preserved high-importance items
        new_context = [compressed_entry] + high_importance
        return new_context

    # -------------------------------------------------------------------------
    # ContextPlugin Protocol Implementation
    # -------------------------------------------------------------------------
    async def bootstrap(self, config: Dict[str, Any]) -> None:
        self.config = config
        if "max_tokens" in config:
            self.max_tokens = config["max_tokens"]
        if "importance_threshold" in config:
            self.importance_threshold = config["importance_threshold"]
        if "working_memory" in config:
            self.working_memory = config["working_memory"]
        if "episodic_memory" in config:
            self.episodic_memory = config["episodic_memory"]
        if "llm_client" in config:
            self.llm_client = config["llm_client"]
        logger.info("VirtualContextCompressionPluginV4 bootstrapped.")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        lines = []
        for it in context_items:
            if isinstance(it, dict):
                lines.append(it.get("content") or str(it))
            elif hasattr(it, "content"):
                lines.append(getattr(it, "content"))
            else:
                lines.append(str(it))
        return "\n".join(lines)

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        return await self.compact_context(context_items)

    def before_retrieval(self, query: str, user_id: int) -> str:
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        pass
