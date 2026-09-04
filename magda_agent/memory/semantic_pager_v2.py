"""
MemGPT Semantic Cluster Virtual Context Pager v2.

Inspired by MemGPT/Letta patterns and Context Compression trends:
A Context Engine plugin that applies local embeddings clustering on episodic
memories, automatically evicting or summarizing entire redundant thematic
clusters to maintain token constraints.
"""

import asyncio
import hashlib
import json
import logging
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class ClusterCompactionStrategy(str, Enum):
    SUMMARIZE_CLUSTER = "summarize_cluster"
    EVICT_REDUNDANT = "evict_redundant"
    COMPACT_CENTROID = "compact_centroid"


@dataclass
class SemanticCluster:
    """Represents a thematic cluster of semantically related episodic memories."""

    cluster_id: str
    topic: str
    centroid: List[float]
    members: List[Dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    redundancy_score: float = 0.0  # 0.0 to 1.0 (higher = more homogeneous/redundant)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


def default_local_embed(text: str, dim: int = 64) -> List[float]:
    """
    Deterministic local feature hashing embedding generator used as default
    when external embedding models are not supplied.
    """
    words = [w.lower() for w in text.split() if w.isalnum()]
    if not words:
        words = [text.lower()]

    vec = [0.0] * dim
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        index = h % dim
        sign = 1.0 if (h % 2 == 0) else -1.0
        vec[index] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class MemGPTSemanticClusterPagerV2:
    """
    Context Engine plugin that discovers thematic clusters across episodic memories
    and compacts or evicts redundant clusters when context token limits are reached.
    """

    def __init__(
        self,
        max_tokens: int = 3000,
        similarity_threshold: float = 0.75,
        compaction_strategy: ClusterCompactionStrategy = ClusterCompactionStrategy.SUMMARIZE_CLUSTER,
        embedding_fn: Optional[Callable[[str], Union[List[float], Coroutine[Any, Any, List[float]]]]] = None,
        summarize_fn: Optional[Callable[[List[Dict[str, Any]]], str]] = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold
        self.compaction_strategy = compaction_strategy
        self.embedding_fn = embedding_fn
        self.summarize_fn = summarize_fn
        self.config: Dict[str, Any] = {}
        self.metrics = {
            "clusters_identified": 0,
            "clusters_evicted": 0,
            "tokens_saved": 0,
            "compact_runs": 0,
        }

    async def _get_embedding(self, text: str) -> List[float]:
        """Extracts embedding vector for text using custom or fallback local embedder."""
        if self.embedding_fn:
            try:
                res = self.embedding_fn(text)
                if asyncio.iscoroutine(res):
                    return await res
                return res
            except Exception as e:
                logger.warning(f"Embedding function failed: {e}. Falling back to local hash embedder.")

        return default_local_embed(text)

    def estimate_tokens(self, item: Any) -> int:
        """Estimates token count of a memory entry or dictionary."""
        if isinstance(item, dict):
            text = item.get("content") or item.get("text") or str(item)
        else:
            text = str(item)
        words = len(text.split())
        return max(1, int(words * 1.3))

    async def cluster_memories(
        self,
        memories: List[Dict[str, Any]],
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCluster]:
        """
        Clusters memory records based on embedding cosine similarity.
        """
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        if not memories:
            return []

        # 1. Generate embeddings for all memories
        embedded_items: List[Tuple[Dict[str, Any], List[float], int]] = []
        for mem in memories:
            text = mem.get("content") or mem.get("text") or str(mem)
            vec = await self._get_embedding(text)
            toks = self.estimate_tokens(mem)
            embedded_items.append((mem, vec, toks))

        # 2. Leader-follower centroid clustering
        clusters: List[SemanticCluster] = []

        for mem, vec, toks in embedded_items:
            best_cluster: Optional[SemanticCluster] = None
            best_sim = -1.0

            for cluster in clusters:
                sim = cosine_similarity(vec, cluster.centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_cluster = cluster

            if best_cluster is not None and best_sim >= threshold:
                # Add to existing cluster and update centroid
                best_cluster.members.append(mem)
                best_cluster.total_tokens += toks
                n = len(best_cluster.members)
                # Incremental centroid update
                best_cluster.centroid = [
                    (old_c * (n - 1) + new_v) / n
                    for old_c, new_v in zip(best_cluster.centroid, vec)
                ]
            else:
                # Create new cluster
                topic_snippet = (mem.get("content") or mem.get("text") or "topic")[:30]
                new_cluster = SemanticCluster(
                    cluster_id=f"clust_{uuid.uuid4().hex[:8]}",
                    topic=f"Theme: {topic_snippet}",
                    centroid=list(vec),
                    members=[mem],
                    total_tokens=toks,
                    redundancy_score=1.0,
                )
                clusters.append(new_cluster)

        # 3. Compute redundancy scores for clusters
        for cl in clusters:
            if len(cl.members) <= 1:
                cl.redundancy_score = 0.0
            else:
                sims = []
                for m in cl.members:
                    t = m.get("content") or m.get("text") or str(m)
                    v = default_local_embed(t)
                    sims.append(cosine_similarity(v, cl.centroid))
                cl.redundancy_score = sum(sims) / len(sims) if sims else 0.0

        self.metrics["clusters_identified"] += len(clusters)
        return clusters

    def _summarize_cluster_members(self, cluster: SemanticCluster) -> str:
        """Generates a concise thematic summary from a cluster of memories."""
        if self.summarize_fn:
            try:
                return self.summarize_fn(cluster.members)
            except Exception as e:
                logger.warning(f"Custom summarize_fn failed: {e}. Using rule-based fallback.")

        # Default rule-based concise summarizer
        texts = [m.get("content") or m.get("text") or str(m) for m in cluster.members]
        unique_snippets = []
        for t in texts:
            clean = t.strip().replace("\n", " ")
            shortened = " ".join(clean.split()[:4])
            if shortened not in unique_snippets:
                unique_snippets.append(shortened)

        combined_preview = "; ".join(unique_snippets[:3])
        return f"[Cluster Summary ({len(cluster.members)} events)]: {combined_preview}..."

    async def compact_context(
        self,
        context_items: List[Any],
        target_max_tokens: Optional[int] = None,
    ) -> List[Any]:
        """
        Main compaction logic: Identifies thematic clusters and evicts/summarizes
        redundant clusters until the total context size is within target_max_tokens.
        """
        limit = target_max_tokens if target_max_tokens is not None else self.max_tokens
        self.metrics["compact_runs"] += 1

        # Normalize context items to list of dicts
        normalized_memories: List[Dict[str, Any]] = []
        for idx, item in enumerate(context_items):
            if isinstance(item, dict):
                normalized_memories.append(dict(item))
            else:
                normalized_memories.append({"id": f"item_{idx}", "content": str(item)})

        total_tokens = sum(self.estimate_tokens(m) for m in normalized_memories)
        if total_tokens <= limit:
            return context_items

        tokens_to_save = total_tokens - limit
        logger.info(f"Context exceeds limit ({total_tokens} > {limit}). Compacting {tokens_to_save} tokens.")

        # 1. Cluster memories
        clusters = await self.cluster_memories(normalized_memories)

        # 2. Sort clusters by redundancy and size (evict/compress most redundant & largest clusters first)
        redundant_clusters = sorted(
            [c for c in clusters if len(c.members) > 1],
            key=lambda c: (c.redundancy_score, c.total_tokens),
            reverse=True,
        )

        compacted_output: List[Any] = []
        compacted_cluster_ids: Set[str] = set()
        saved_so_far = 0

        for cl in redundant_clusters:
            if saved_so_far >= tokens_to_save:
                break

            compacted_cluster_ids.add(cl.cluster_id)
            self.metrics["clusters_evicted"] += 1

            if self.compaction_strategy == ClusterCompactionStrategy.SUMMARIZE_CLUSTER:
                summary_text = self._summarize_cluster_members(cl)
                summary_record = {
                    "id": f"summary_{cl.cluster_id}",
                    "content": summary_text,
                    "is_summary": True,
                    "synthesized_from_count": len(cl.members),
                    "cluster_id": cl.cluster_id,
                }
                compacted_output.append(summary_record)
                summary_tokens = self.estimate_tokens(summary_record)
                tokens_freed = max(0, cl.total_tokens - summary_tokens)
                saved_so_far += tokens_freed

            elif self.compaction_strategy == ClusterCompactionStrategy.EVICT_REDUNDANT:
                # Retain only the most recent/representative member
                newest = cl.members[-1]
                compacted_output.append(newest)
                tokens_freed = max(0, cl.total_tokens - self.estimate_tokens(newest))
                saved_so_far += tokens_freed

            elif self.compaction_strategy == ClusterCompactionStrategy.COMPACT_CENTROID:
                centroid_record = {
                    "id": f"centroid_{cl.cluster_id}",
                    "content": f"[Thematic Index: {cl.topic}]",
                    "cluster_id": cl.cluster_id,
                }
                compacted_output.append(centroid_record)
                saved_so_far += max(0, cl.total_tokens - self.estimate_tokens(centroid_record))

        # 3. Add back all members of untouched clusters (and singleton clusters)
        for cl in clusters:
            if cl.cluster_id not in compacted_cluster_ids:
                compacted_output.extend(cl.members)

        self.metrics["tokens_saved"] += saved_so_far
        return compacted_output

    # -------------------------------------------------------------------------
    # ContextPlugin Protocol Implementation
    # -------------------------------------------------------------------------
    async def bootstrap(self, config: Dict[str, Any]) -> None:
        self.config = config
        if "max_tokens" in config:
            self.max_tokens = config["max_tokens"]
        if "similarity_threshold" in config:
            self.similarity_threshold = config["similarity_threshold"]
        logger.info("MemGPTSemanticClusterPagerV2 bootstrapped successfully.")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        lines = []
        for item in context_items:
            if isinstance(item, dict):
                lines.append(item.get("content") or str(item))
            else:
                lines.append(str(item))
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
