"""
MemGPT Virtual Context Semantic Compressor V5.

Inspired by MemGPT virtual context architecture: Implements an asynchronous
background compressor that periodically processes older episodic dialogue/interaction
chunks into clustered semantic facts and conceptual summaries to free working memory space.
"""

import asyncio
import inspect
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class EpisodicChunk:
    """Represents a raw episodic memory or conversation chunk."""

    chunk_id: str = field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:8]}")
    content: str = ""
    source: str = "agent"  # user, agent, tool, system
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicChunk":
        return cls(
            chunk_id=data.get("chunk_id") or f"chunk_{uuid.uuid4().hex[:8]}",
            content=data.get("content", ""),
            source=data.get("source", "agent"),
            timestamp=float(data.get("timestamp", time.time())),
            token_count=int(data.get("token_count", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SemanticFact:
    """Represents an extracted, concise semantic fact distilled from episodic memories."""

    fact_id: str = field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    topic_cluster: str = "general"
    fact_statement: str = ""
    confidence: float = 0.95
    source_chunk_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticCluster:
    """A cluster of semantic facts sharing a common thematic domain."""

    cluster_id: str = field(default_factory=lambda: f"cluster_{uuid.uuid4().hex[:8]}")
    topic: str = "general"
    summary: str = ""
    facts: List[SemanticFact] = field(default_factory=list)
    compressed_token_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "topic": self.topic,
            "summary": self.summary,
            "facts": [f.to_dict() for f in self.facts],
            "compressed_token_count": self.compressed_token_count,
        }


@dataclass
class VirtualContextCompressionResult:
    """Outcome of converting episodic chunks into semantic clusters."""

    original_chunk_count: int
    original_token_count: int
    compressed_fact_count: int
    compressed_token_count: int
    tokens_freed: int
    clusters: List[SemanticCluster] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_chunk_count": self.original_chunk_count,
            "original_token_count": self.original_token_count,
            "compressed_fact_count": self.compressed_fact_count,
            "compressed_token_count": self.compressed_token_count,
            "tokens_freed": self.tokens_freed,
            "clusters": [c.to_dict() for c in self.clusters],
            "execution_time_ms": self.execution_time_ms,
        }


class MemGPTVirtualContextSemanticCompressorV5:
    """
    MemGPT Virtual Context Semantic Compressor V5.

    Continuously ingests episodic memory items. When working memory exceeds thresholds,
    or on explicit compression invocation, groups episodic items into semantic clusters
    and distills durable semantic facts.
    """

    TOPIC_KEYWORDS = {
        "user_profile": ["preference", "name", "email", "likes", "dislikes", "location", "timezone", "role"],
        "architecture": ["pattern", "module", "refactor", "database", "api", "microservice", "pipeline", "schema"],
        "task_progress": ["completed", "todo", "failed", "verified", "passed", "fixed", "implemented", "milestone"],
        "safety_policy": ["security", "taint", "guardrail", "policy", "sanitization", "sandbox", "audit"],
        "technical_stack": ["python", "docker", "fastapi", "git", "linux", "chromadb", "sqlite", "redis"],
    }

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        working_memory_limit_tokens: int = 4000,
        compression_threshold_ratio: float = 0.8,
        min_chunks_for_compression: int = 2,
    ):
        self.llm_client = llm_client
        self.working_memory_limit_tokens = working_memory_limit_tokens
        self.compression_threshold_ratio = compression_threshold_ratio
        self.min_chunks_for_compression = min_chunks_for_compression

        self._episodic_buffer: List[EpisodicChunk] = []
        self._semantic_facts: List[SemanticFact] = []
        self._clusters: Dict[str, SemanticCluster] = {}
        self._background_task: Optional[asyncio.Task] = None
        self._is_running = False

    def estimate_tokens(self, text: str) -> int:
        """Estimate token length using word count heuristic."""
        words = len(text.strip().split())
        return max(1, int(words * 1.3))

    def add_episodic_chunk(
        self,
        content: str,
        source: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EpisodicChunk:
        """Add an interaction chunk to the episodic working buffer."""
        tokens = self.estimate_tokens(content)
        chunk = EpisodicChunk(
            content=content,
            source=source,
            timestamp=time.time(),
            token_count=tokens,
            metadata=metadata or {},
        )
        self._episodic_buffer.append(chunk)
        return chunk

    def get_working_memory_tokens(self) -> int:
        """Calculate total tokens currently stored in episodic working buffer."""
        return sum(c.token_count for c in self._episodic_buffer)

    def should_compress(self) -> bool:
        """Determine if episodic memory volume warrants compression."""
        total_tokens = self.get_working_memory_tokens()
        threshold = int(self.working_memory_limit_tokens * self.compression_threshold_ratio)
        return (
            len(self._episodic_buffer) >= self.min_chunks_for_compression
            and total_tokens >= threshold
        )

    def _classify_chunk_topic(self, content: str) -> str:
        """Classify episodic content into semantic topic clusters."""
        content_lower = content.lower()
        topic_scores: Dict[str, int] = {}

        for topic, keywords in self.TOPIC_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > 0:
                topic_scores[topic] = matches

        if not topic_scores:
            return "general"

        return max(topic_scores.items(), key=lambda x: x[1])[0]

    def cluster_episodic_chunks(
        self,
        chunks: List[EpisodicChunk],
    ) -> Dict[str, List[EpisodicChunk]]:
        """Group raw episodic chunks into thematic clusters."""
        clustered: Dict[str, List[EpisodicChunk]] = {}
        for chunk in chunks:
            topic = chunk.metadata.get("topic") or self._classify_chunk_topic(chunk.content)
            if topic not in clustered:
                clustered[topic] = []
            clustered[topic].append(chunk)
        return clustered

    async def _extract_facts_from_cluster_async(
        self,
        topic: str,
        chunks: List[EpisodicChunk],
    ) -> Tuple[List[SemanticFact], str]:
        """Extract durable semantic facts from a cluster of episodic chunks."""
        chunk_ids = [c.chunk_id for c in chunks]
        combined_text = "\n".join(f"- [{c.source}] {c.content}" for c in chunks)

        if self.llm_client:
            prompt = (
                f"You are a semantic memory compressor. Analyze the following episodic interaction chunks "
                f"on the topic '{topic}' and distill key facts into a JSON array of strings.\n\n"
                f"Chunks:\n{combined_text}\n\n"
                f"Respond with JSON format: {{\"summary\": \"...\", \"facts\": [\"fact 1\", \"fact 2\"]}}"
            )
            try:
                if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                    llm_out = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "generate"):
                    llm_out = self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                    llm_out = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                else:
                    llm_out = ""

                # Parse JSON
                match = re.search(r"\{.*\}", llm_out, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    summary = parsed.get("summary", f"Summary of {topic}")
                    raw_facts = parsed.get("facts", [])
                    facts = [
                        SemanticFact(
                            topic_cluster=topic,
                            fact_statement=f,
                            confidence=0.95,
                            source_chunk_ids=chunk_ids,
                            tags=[topic],
                        )
                        for f in raw_facts if isinstance(f, str) and f.strip()
                    ]
                    if facts:
                        return facts, summary
            except Exception as e:
                logger.warning(f"LLM fact extraction failed: {e}. Falling back to heuristic extraction.")

        # Heuristic fallback
        facts = []
        for c in chunks:
            lines = [l.strip() for l in c.content.split("\n") if l.strip()]
            for line in lines:
                facts.append(
                    SemanticFact(
                        topic_cluster=topic,
                        fact_statement=line,
                        confidence=0.85,
                        source_chunk_ids=[c.chunk_id],
                        tags=[topic],
                    )
                )

        summary = f"Aggregated {len(facts)} semantic facts regarding {topic}."
        return facts, summary

    async def compress_episodic_to_semantic(
        self,
        chunks: Optional[List[EpisodicChunk]] = None,
    ) -> VirtualContextCompressionResult:
        """
        Compress episodic memory chunks into semantic facts and clusters.
        """
        start_t = time.perf_counter()
        target_chunks = list(chunks if chunks is not None else self._episodic_buffer)

        if not target_chunks:
            return VirtualContextCompressionResult(
                original_chunk_count=0,
                original_token_count=0,
                compressed_fact_count=0,
                compressed_token_count=0,
                tokens_freed=0,
                clusters=[],
                execution_time_ms=0.0,
            )

        original_tokens = sum(c.token_count for c in target_chunks)
        clustered_chunks = self.cluster_episodic_chunks(target_chunks)

        new_clusters: List[SemanticCluster] = []
        all_new_facts: List[SemanticFact] = []

        for topic, topic_chunks in clustered_chunks.items():
            facts, summary = await self._extract_facts_from_cluster_async(topic, topic_chunks)
            cluster_tokens = self.estimate_tokens(summary) + sum(
                self.estimate_tokens(f.fact_statement) for f in facts
            )

            cluster = SemanticCluster(
                topic=topic,
                summary=summary,
                facts=facts,
                compressed_token_count=cluster_tokens,
            )

            new_clusters.append(cluster)
            all_new_facts.extend(facts)
            self._clusters[topic] = cluster

        self._semantic_facts.extend(all_new_facts)

        # Clear processed chunks from episodic buffer if compressing internal buffer
        if chunks is None:
            self._episodic_buffer.clear()

        compressed_tokens = sum(c.compressed_token_count for c in new_clusters)
        tokens_freed = max(0, original_tokens - compressed_tokens)
        elapsed = (time.perf_counter() - start_t) * 1000.0

        return VirtualContextCompressionResult(
            original_chunk_count=len(target_chunks),
            original_token_count=original_tokens,
            compressed_fact_count=len(all_new_facts),
            compressed_token_count=compressed_tokens,
            tokens_freed=tokens_freed,
            clusters=new_clusters,
            execution_time_ms=elapsed,
        )

    def compress_sync(
        self,
        chunks: Optional[List[EpisodicChunk]] = None,
    ) -> VirtualContextCompressionResult:
        """Synchronous wrapper for compression."""
        return asyncio.run(self.compress_episodic_to_semantic(chunks))

    def get_semantic_facts(self, topic: Optional[str] = None) -> List[SemanticFact]:
        """Retrieve stored semantic facts, optionally filtered by topic."""
        if topic:
            return [f for f in self._semantic_facts if f.topic_cluster.lower() == topic.lower()]
        return list(self._semantic_facts)

    def get_clusters(self) -> List[SemanticCluster]:
        """Retrieve all active semantic clusters."""
        return list(self._clusters.values())

    def get_compression_metrics(self) -> Dict[str, Any]:
        """Summary of current working buffer and semantic memory stats."""
        return {
            "episodic_buffer_chunk_count": len(self._episodic_buffer),
            "episodic_buffer_tokens": self.get_working_memory_tokens(),
            "working_memory_limit_tokens": self.working_memory_limit_tokens,
            "total_semantic_facts": len(self._semantic_facts),
            "total_clusters": len(self._clusters),
        }
