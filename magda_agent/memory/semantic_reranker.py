import logging
import math
import re
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin

def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r'\w+', text.lower())

def compute_cosine_similarity(text1: str, text2: str) -> float:
    """
    Computes a localized lexical cosine similarity based on word frequencies.
    Highly deterministic and self-contained.
    """
    words1 = tokenize(text1)
    words2 = tokenize(text2)
    if not words1 or not words2:
        return 0.0

    # Calculate term frequencies
    freq1: Dict[str, int] = {}
    freq2: Dict[str, int] = {}
    for w in words1:
        freq1[w] = freq1.get(w, 0) + 1
    for w in words2:
        freq2[w] = freq2.get(w, 0) + 1

    # Dot product
    all_words = set(freq1.keys()).union(freq2.keys())
    dot_product = sum(freq1.get(w, 0) * freq2.get(w, 0) for w in all_words)

    # Vector magnitudes
    mag1 = math.sqrt(sum(val**2 for val in freq1.values()))
    mag2 = math.sqrt(sum(val**2 for val in freq2.values()))

    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0

    return dot_product / (mag1 * mag2)


class SemanticRerankerPlugin(ContextPlugin):
    """
    Context Engine Live Semantic Re-ranker Plugin.
    Dynamically prioritizes/re-ranks retrieved Episodic Memory entries
    using localized embeddings (lexical/semantic similarity) before Planner retrieval.
    """

    def __init__(self, similarity_fn=None) -> None:
        self.similarity_fn = similarity_fn or compute_cosine_similarity

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if config and "similarity_fn" in config:
            self.similarity_fn = config["similarity_fn"]
        logging.debug("SemanticRerankerPlugin initialized successfully.")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process incoming content before it is stored or used."""
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Assemble the context string from retrieved items."""
        return "\n".join([self._get_entry_text(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact context when limits are reached."""
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """Called before context is retrieved. Can modify the query."""
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Sort the retrieved context entries dynamically based on semantic similarity to the query.
        """
        if not context or not query:
            return context

        scored_context = []
        for entry in context:
            text = self._get_entry_text(entry)
            score = self.similarity_fn(query, text)
            scored_context.append((score, entry))

        # Re-rank context based on similarity score (descending)
        scored_context.sort(key=lambda x: x[0], reverse=True)
        return [entry for score, entry in scored_context]

    def before_write(self, context: Any, user_id: int) -> Any:
        """Called before context is written."""
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Called after context is written."""
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Called when the overall context is updated."""
        pass

    def _get_entry_text(self, entry: Any) -> str:
        """Helper to extract text/content safely from varying entry structures."""
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return entry.get("text") or entry.get("content") or ""
        for attr in ["text", "content"]:
            if hasattr(entry, attr):
                val = getattr(entry, attr)
                if isinstance(val, str):
                    return val
        return str(entry)
