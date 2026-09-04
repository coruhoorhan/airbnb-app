import logging
from typing import List, Optional, Any

from magda_agent.memory.working import MemoryEntry
from magda_agent.memory.selective_retrieval_v2 import SelectiveRetrievalV2


class ClaudeContextCompressorV6:
    """
    Claude SDK inspired context compressor V6.
    Enhances context compression algorithms with selective retrieval based on semantic clustering.
    It can selectively retrieve related semantic context to cluster memory before compression.
    """

    def __init__(self, llm_client: Optional[Any] = None, retriever: Optional[SelectiveRetrievalV2] = None) -> None:
        """
        Initializes the V6 context compressor.

        Args:
            llm_client: Optional LLM client to use for smart summarization.
            retriever: Optional SelectiveRetrievalV2 instance for fetching relevant episodic memory.
        """
        self.llm = llm_client
        self.retriever = retriever

    async def compress_entries(self, entries: List[MemoryEntry], token_limit: int = 2000, semantic_query: Optional[str] = None) -> MemoryEntry:
        """
        Compresses a list of memory entries into a single entry to fit within limits,
        optionally clustering with selectively retrieved relevant semantic context.

        Args:
            entries: A list of MemoryEntry objects to compress.
            token_limit: The maximum allowed tokens for the combined text.
            semantic_query: Optional query to fetch relevant background context for clustering.

        Returns:
            A new MemoryEntry object representing the compressed content and context.
        """
        if not entries:
            raise ValueError("No entries to compress")

        user_id = entries[0].user_id

        # 1. Base Working Memory Content
        working_text = "\n".join(e.content for e in entries)
        combined_text = working_text

        # 2. Selectively Retrieve Semantic Context if requested
        retrieved_contexts = []
        if semantic_query and self.retriever:
            try:
                retrieved_contexts = self.retriever.retrieve_relevant_context(semantic_query, user_id=user_id)
                if retrieved_contexts:
                    context_text = "\n".join(retrieved_contexts)
                    combined_text = f"Retrieved Semantic Context:\n{context_text}\n\nRecent Memory:\n{working_text}"
            except Exception as e:
                logging.error(f"Failed to retrieve semantic context during compression: {e}")

        char_limit = token_limit * 4
        compressed_text = combined_text

        # 3. Compress using LLM or Truncate
        if len(combined_text) > char_limit and self.llm:
            try:
                logging.info(f"Compressing {len(entries)} entries with semantic context.")
                prompt = (
                    f"Summarize the following memory context, maintaining key facts and semantic relationships "
                    f"within {token_limit} tokens. Integrate the retrieved background context if it relates to "
                    f"the recent memory.\n\n{combined_text}"
                )
                messages = [
                    {"role": "system", "content": "You are a memory context compressor. Output only the summarized text."},
                    {"role": "user", "content": prompt}
                ]
                compressed_text = await self.llm.chat_completion(messages, temperature=0.2)
                compressed_text = compressed_text.strip()
            except Exception as e:
                logging.error(f"Compression failed: {e}")
                compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"
        elif len(combined_text) > char_limit:
            compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"

        # Calculate average importance and gather unique tags
        avg_importance = sum(e.importance for e in entries) / len(entries)
        all_tags = set()
        for e in entries:
            if e.tags:
                all_tags.update(e.tags)

        # Append a tag to indicate it was enriched if context was added
        if retrieved_contexts:
            all_tags.add("semantic-enriched")

        return MemoryEntry(
            content=compressed_text,
            importance=avg_importance,
            emotional_state=entries[0].emotional_state,
            tags=list(all_tags),
            user_id=user_id
        )
