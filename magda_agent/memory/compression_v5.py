import logging
from typing import List, Optional, Any

from magda_agent.memory.working import MemoryEntry

class ClaudeContextCompressorV5:
    """
    Claude SDK inspired context compressor for enhancing context compression algorithms.
    Provides tools for selectively keeping recent context intact while aggressively
    compressing or truncating older context elements based on explicit token window limits.
    """
    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """
        Initializes the V5 context compressor.

        Args:
            llm_client: Optional LLM client to use for smart summarization.
        """
        self.llm = llm_client

    async def compress_entries(self, entries: List[MemoryEntry], token_limit: int = 2000) -> MemoryEntry:
        """
        Compresses a list of memory entries into a single entry to fit within limits.
        Inspired by Claude Agent SDK context window management.

        Args:
            entries: A list of MemoryEntry objects to compress.
            token_limit: The maximum allowed tokens for the combined text.

        Returns:
            A new MemoryEntry object representing the compressed content.
        """
        if not entries:
            raise ValueError("No entries to compress")

        # Sort entries by importance or use order as-is. We assume they are ordered by recency.
        combined_text = "\n".join(e.content for e in entries)
        char_limit = token_limit * 4
        compressed_text = combined_text

        if len(combined_text) > char_limit and self.llm:
            try:
                logging.info(f"Compressing {len(entries)} old working memory entries.")
                prompt = f"You compress memory context. Return only the summary text.\n\nSummarize the following text, maintaining key facts within {token_limit} tokens:\n\n{combined_text}"
                compressed_text = await self.llm.generate(prompt, temperature=0.2)
                compressed_text = compressed_text.strip()
            except Exception as e:
                logging.error(f"Compression failed: {e}")
                compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"
        elif len(combined_text) > char_limit:
            compressed_text = combined_text[:char_limit] + "... [TRUNCATED]"

        avg_importance = sum(e.importance for e in entries) / len(entries)
        first = entries[0]

        all_tags = set()
        for e in entries:
            if e.tags:
                all_tags.update(e.tags)

        return MemoryEntry(
            content=compressed_text,
            importance=avg_importance,
            emotional_state=first.emotional_state,
            tags=list(all_tags),
            user_id=first.user_id
        )

    async def compress_workflow(self, workflow_context: str, token_limit: int) -> str:
        """
        Compresses a long-running workflow context to fit within a specified token limit.
        Uses a heuristic of 4 characters per token if an exact tokenizer is unavailable.

        Args:
            workflow_context: The text of the workflow context.
            token_limit: The maximum allowed tokens.

        Returns:
            The original string if within limits, or a compressed summary.
        """
        char_limit = token_limit * 4
        if len(workflow_context) <= char_limit:
            return workflow_context

        if self.llm:
            try:
                logging.info(f"V5 Compressing workflow context exceeding {token_limit} tokens.")
                prompt = f"You compress workflow context. Return only the summary text.\n\nSummarize the following workflow context to fit within {token_limit} tokens, retaining critical state and paths:\n\n{workflow_context}"
                compressed_text = await self.llm.generate(prompt, temperature=0.2)
                return compressed_text.strip()
            except Exception as e:
                logging.error(f"V5 Workflow compression failed: {e}")
                return workflow_context[:char_limit] + "... [TRUNCATED]"
        else:
            logging.warning("No LLM available for V5 workflow compression, falling back to truncation.")
            return workflow_context[:char_limit] + "... [TRUNCATED]"
