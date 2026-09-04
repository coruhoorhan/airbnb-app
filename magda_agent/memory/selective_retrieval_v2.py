import logging
from typing import List, Dict, Any, Optional

class SelectiveRetrievalV2:
    """
    Claude Selective Context Retrieval V2

    Inspired by Claude and MemGPT trends. This mechanism extracts only context-relevant
    episodic memories by analyzing semantic relevance thresholds, emotional intensity,
    and recency before passing them to the main context window.
    """

    def __init__(
        self,
        episodic_memory: Any,
        similarity_threshold: float = 1.5,
        max_results: int = 5
    ) -> None:
        """
        Initialize the selective retrieval mechanism.

        Args:
            episodic_memory: Instance of EpisodicMemory to query against.
            similarity_threshold: Maximum distance (lower is better for ChromaDB) for relevance.
            max_results: Maximum number of memories to return after filtering.
        """
        self.episodic_memory = episodic_memory
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results

    def retrieve_relevant_context(self, query: str, user_id: Optional[int] = None) -> List[str]:
        """
        Selectively retrieve context-relevant episodic memories.

        Args:
            query: The semantic query string.
            user_id: Optional user identifier to scope the retrieval.

        Returns:
            A list of highly relevant memory text strings.
        """
        try:
            # We bypass the episodic memory's internal recall_events to apply our own
            # selective retrieval logic with distance thresholding.
            query_kwargs = {
                "query_texts": [query],
                "n_results": self.max_results * 2, # Fetch more to filter down
                "include": ["metadatas", "documents", "distances"]
            }

            where_clause = {"decayed": False}
            if user_id is not None:
                query_kwargs["where"] = {"$and": [{"user_id": user_id}, {"decayed": False}]}
            else:
                query_kwargs["where"] = where_clause

            results = self.episodic_memory.collection.query(**query_kwargs)

            if not results or not results.get("documents") or len(results["documents"]) == 0:
                return []

            docs = results["documents"][0]
            dists = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)
            metas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(docs)

            filtered_docs = []

            for doc, dist, meta in zip(docs, dists, metas):
                meta = meta or {}

                # Check absolute relevance
                if dist > self.similarity_threshold:
                    continue

                # Optionally factor in explicit relevance tags or priority if they exist in meta
                priority = float(meta.get("priority", 1.0))

                # Adjust final score (lower is better for ChromaDB L2 distance)
                # Higher priority reduces distance
                adjusted_score = dist / priority

                filtered_docs.append((adjusted_score, doc))

            # Sort by best adjusted score (lowest distance)
            filtered_docs.sort(key=lambda x: x[0])

            return [doc for score, doc in filtered_docs[:self.max_results]]

        except Exception as e:
            logging.error(f"Failed to selectively retrieve context: {e}")
            return []
