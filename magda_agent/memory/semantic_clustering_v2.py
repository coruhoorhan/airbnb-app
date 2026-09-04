"""
Context Engine Semantic Clustering Hook V2.

Inspired by MemGPT and Letta virtual context patterns: Implements an advanced
context engine lifecycle hook that clusters related episodic memory entries
semantically using tag hierarchies and metadata, compressing working context
to maximize token reduction while preserving crucial details.
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
class MemoryItem:
    """Represents an individual episodic memory entry."""

    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:8]}")
    content: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            id=str(data.get("id") or data.get("memory_id") or f"mem_{uuid.uuid4().hex[:8]}"),
            content=str(data.get("content") or data.get("text") or ""),
            tags=list(data.get("tags") or []),
            timestamp=float(data.get("timestamp", time.time())),
            tokens=int(data.get("tokens") or data.get("token_count") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class SemanticTagCluster:
    """A semantic cluster formed by memories sharing common tags or thematic concepts."""

    cluster_id: str = field(default_factory=lambda: f"cluster_{uuid.uuid4().hex[:8]}")
    primary_tag: str = "general"
    secondary_tags: List[str] = field(default_factory=list)
    items: List[MemoryItem] = field(default_factory=list)
    total_tokens: int = 0
    compressed_summary: Optional[str] = None
    compressed_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "primary_tag": self.primary_tag,
            "secondary_tags": self.secondary_tags,
            "item_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "total_tokens": self.total_tokens,
            "compressed_summary": self.compressed_summary,
            "compressed_tokens": self.compressed_tokens,
        }


@dataclass
class ContextEngineClusteringResult:
    """Outcome of executing the semantic clustering hook over memory context."""

    initial_item_count: int
    initial_tokens: int
    compressed_item_count: int
    final_tokens: int
    token_reduction: int
    clusters_created: List[SemanticTagCluster] = field(default_factory=list)
    compressed_entries: List[Dict[str, Any]] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_item_count": self.initial_item_count,
            "initial_tokens": self.initial_tokens,
            "compressed_item_count": self.compressed_item_count,
            "final_tokens": self.final_tokens,
            "token_reduction": self.token_reduction,
            "clusters_created": [c.to_dict() for c in self.clusters_created],
            "execution_time_ms": self.execution_time_ms,
        }


class ContextEngineSemanticClusteringHookV2:
    """
    Context Engine Semantic Clustering Hook V2.

    Clusters episodic memories by semantic tags and conceptual affinities,
    compressing multi-entry clusters into consolidated semantic memory nodes.
    """

    def __init__(
        self,
        min_cluster_size: int = 2,
        default_tag: str = "general",
        custom_summarizer: Optional[Callable[[str, List[MemoryItem]], str]] = None,
    ):
        self.min_cluster_size = max(1, min_cluster_size)
        self.default_tag = default_tag
        self.custom_summarizer = custom_summarizer
        self._history: List[ContextEngineClusteringResult] = []

    def estimate_tokens(self, text: str) -> int:
        """Estimate token volume via word count heuristic."""
        words = len(text.strip().split())
        return max(1, int(words * 1.3))

    def _normalize_item(self, item: Union[MemoryItem, Dict[str, Any]]) -> MemoryItem:
        if isinstance(item, MemoryItem):
            if item.tokens <= 0 and item.content:
                item.tokens = self.estimate_tokens(item.content)
            return item
        norm = MemoryItem.from_dict(item)
        if norm.tokens <= 0 and norm.content:
            norm.tokens = self.estimate_tokens(norm.content)
        return norm

    def cluster_by_semantic_tags(
        self,
        memories: List[Union[MemoryItem, Dict[str, Any]]],
    ) -> Dict[str, SemanticTagCluster]:
        """
        Group memories into semantic tag clusters based on primary and secondary tags.
        """
        norm_items = [self._normalize_item(m) for m in memories]
        clusters: Dict[str, SemanticTagCluster] = {}

        for item in norm_items:
            # Determine primary tag
            if item.tags:
                primary_tag = item.tags[0].strip().lower()
                secondary_tags = [t.strip().lower() for t in item.tags[1:]]
            else:
                primary_tag = self.default_tag
                secondary_tags = []

            if primary_tag not in clusters:
                clusters[primary_tag] = SemanticTagCluster(
                    primary_tag=primary_tag,
                    secondary_tags=list(set(secondary_tags)),
                    items=[],
                    total_tokens=0,
                )

            cluster = clusters[primary_tag]
            cluster.items.append(item)
            cluster.total_tokens += item.tokens
            for st in secondary_tags:
                if st not in cluster.secondary_tags:
                    cluster.secondary_tags.append(st)

        return clusters

    def _summarize_cluster(
        self,
        cluster: SemanticTagCluster,
    ) -> Tuple[str, int]:
        """
        Generate consolidated summary for a cluster.
        """
        if self.custom_summarizer:
            summary = self.custom_summarizer(cluster.primary_tag, cluster.items)
            return summary, self.estimate_tokens(summary)

        # Built-in structured summarization
        statements = []
        for it in cluster.items:
            # Extract key statements / bullets
            clean_lines = [l.strip() for l in it.content.split("\n") if l.strip()]
            for line in clean_lines:
                if line not in statements:
                    statements.append(line)

        summary_text = (
            f"Semantic Cluster [{cluster.primary_tag.upper()}]: "
            f"{'; '.join(statements[:5])}"
        )
        if len(statements) > 5:
            summary_text += f" (+{len(statements) - 5} additional points consolidated)"

        tokens = self.estimate_tokens(summary_text)
        return summary_text, tokens

    def compress_memory_context(
        self,
        memories: List[Union[MemoryItem, Dict[str, Any]]],
    ) -> ContextEngineClusteringResult:
        """
        Synchronously cluster and compress memories, producing reduced token context.
        """
        start_t = time.perf_counter()
        if not memories:
            return ContextEngineClusteringResult(
                initial_item_count=0,
                initial_tokens=0,
                compressed_item_count=0,
                final_tokens=0,
                token_reduction=0,
                clusters_created=[],
                compressed_entries=[],
                execution_time_ms=0.0,
            )

        norm_memories = [self._normalize_item(m) for m in memories]
        initial_tokens = sum(m.tokens for m in norm_memories)

        clusters = self.cluster_by_semantic_tags(norm_memories)
        compressed_entries: List[Dict[str, Any]] = []
        created_clusters: List[SemanticTagCluster] = []

        for primary_tag, cluster in clusters.items():
            # If cluster meets minimum threshold, compress it
            if len(cluster.items) >= self.min_cluster_size:
                summary, comp_tokens = self._summarize_cluster(cluster)
                cluster.compressed_summary = summary
                cluster.compressed_tokens = comp_tokens
                created_clusters.append(cluster)

                compressed_entries.append({
                    "id": f"cluster_{cluster.cluster_id}",
                    "content": summary,
                    "tags": [primary_tag] + cluster.secondary_tags,
                    "is_cluster_summary": True,
                    "source_memory_ids": [it.id for it in cluster.items],
                    "tokens": comp_tokens,
                })
            else:
                # Keep singletons as-is
                for single in cluster.items:
                    compressed_entries.append(single.to_dict())
                created_clusters.append(cluster)

        final_tokens = sum(int(e.get("tokens", 0)) for e in compressed_entries)
        token_reduction = max(0, initial_tokens - final_tokens)
        elapsed = (time.perf_counter() - start_t) * 1000.0

        res = ContextEngineClusteringResult(
            initial_item_count=len(norm_memories),
            initial_tokens=initial_tokens,
            compressed_item_count=len(compressed_entries),
            final_tokens=final_tokens,
            token_reduction=token_reduction,
            clusters_created=created_clusters,
            compressed_entries=compressed_entries,
            execution_time_ms=elapsed,
        )
        self._history.append(res)
        return res

    def execute_hook(
        self,
        memory_store: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ContextEngineClusteringResult:
        """
        Execute hook against memory store object or list.
        """
        # Extract items
        if isinstance(memory_store, list):
            items = list(memory_store)
            res = self.compress_memory_context(items)
            # Update list in place if possible
            memory_store.clear()
            memory_store.extend(res.compressed_entries)
            return res

        if hasattr(memory_store, "get_all"):
            raw_items = memory_store.get_all()
            res = self.compress_memory_context(raw_items)
            if hasattr(memory_store, "replace_all"):
                memory_store.replace_all(res.compressed_entries)
            elif hasattr(memory_store, "clear") and hasattr(memory_store, "add_many"):
                memory_store.clear()
                memory_store.add_many(res.compressed_entries)
            return res

        if hasattr(memory_store, "get_entries"):
            raw_items = memory_store.get_entries()
            res = self.compress_memory_context(raw_items)
            if hasattr(memory_store, "set_entries"):
                memory_store.set_entries(res.compressed_entries)
            return res

        if isinstance(memory_store, dict) and "memories" in memory_store:
            raw_items = memory_store["memories"]
            res = self.compress_memory_context(raw_items)
            memory_store["memories"] = res.compressed_entries
            return res

        raise ValueError(f"Unsupported memory_store type '{type(memory_store).__name__}'")

    async def execute_hook_async(
        self,
        memory_store: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ContextEngineClusteringResult:
        """Async execution wrapper."""
        return self.execute_hook(memory_store, context)
