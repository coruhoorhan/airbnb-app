import logging
from typing import List, Optional, Any

from magda_agent.memory.working import MemoryEntry
from magda_agent.memory.context_selective_retrieval_v3 import ContextSelectiveRetrievalV3

class ClaudeContextCompressorV7:
    """
    Claude SDK inspired context compressor V7.
    Enhances context compression algorithms with selective retrieval V3 based on semantic clustering.
    It can selectively retrieve related semantic context to cluster memory before compression.
    """

    def __init__(self, llm_client: Optional[Any] = None, retriever: Optional[ContextSelectiveRetrievalV3] = None) -> None:
        """
        Initializes the V7 context compressor.

        Args:
            llm_client: Optional LLM client to use for smart summarization.
            retriever: Optional ContextSelectiveRetrievalV3 instance for intelligent semantic pruning.
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
        # With Selective Retrieval V3, we want to first prune our entries so that we only summarize
        # the most relevant semantic context if limit exceeds.
        pruned_entries = entries
        retrieved_contexts = False

        if self.retriever:
            try:
                # Use ContextSelectiveRetrievalV3 to prune the context before summarization
                # Subtract some buffer for the summary prompt overhead if needed, here we just use token_limit
                pruned_entries = await self.retriever.prune_context(entries, max_tokens=token_limit, query=semantic_query)
                retrieved_contexts = True
            except Exception as e:
                logging.error(f"Failed to prune semantic context during compression: {e}")

        # Calculate base working memory content
        working_text = "\n".join(e.content for e in pruned_entries)
        combined_text = working_text

        char_limit = token_limit * 4
        compressed_text = combined_text

        # 3. Compress using LLM or Truncate
        if len(combined_text) > char_limit and self.llm:
            try:
                logging.info(f"Compressing {len(pruned_entries)} entries with semantic context.")
                prompt = (
                    f"You are a memory context compressor. Output only the summarized text. "
                    f"Summarize the following memory context, maintaining key facts and semantic relationships "
                    f"within {token_limit} tokens.\n\n{combined_text}"
                )
                compressed_text = await self.llm.generate(prompt, temperature=0.2)
                compressed_text = compressed_text.strip()
            except Exception as e:
                logging.error(f"Compression failed: {e}")
                compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"
        elif len(combined_text) > char_limit:
            compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"

        # Calculate average importance and gather unique tags
        if pruned_entries:
            avg_importance = sum(e.importance for e in pruned_entries) / len(pruned_entries)
        else:
            avg_importance = 0.5

        all_tags = set()
        for e in pruned_entries:
            if e.tags:
                all_tags.update(e.tags)

        # Append a tag to indicate it was enriched if context was added
        if retrieved_contexts and semantic_query:
            all_tags.add("semantic-enriched")

        return MemoryEntry(
            content=compressed_text,
            importance=avg_importance,
            emotional_state=entries[0].emotional_state,
            tags=list(all_tags),
            user_id=user_id
        )
