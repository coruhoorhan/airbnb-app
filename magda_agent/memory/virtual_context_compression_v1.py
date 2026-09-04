import logging
from typing import List, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.emotions.engine import PADState
from magda_agent.memory.working import MemoryEntry


class OpenClawVirtualContextCompressionHook:
    """
    A compression subagent hook inspired by MemGPT/Letta patterns (June 2026).
    Intercepts long subagent working memory states and applies selective summarization
    if the context length exceeds the configured token threshold.
    """

    def __init__(self, llm: LLMClient, token_threshold: int = 2000) -> None:
        """
        Initialize the compression hook.

        Args:
            llm: An LLMClient instance for summarization.
            token_threshold: Maximum estimated token length before compression triggers.
        """
        self.llm = llm
        self.token_threshold = token_threshold

    def _get_token_length(self, entries: List[MemoryEntry]) -> int:
        """
        Calculate an estimated token length for a list of MemoryEntry items.
        Assumes ~1.3 tokens per word.

        Args:
            entries: A list of MemoryEntry instances.

        Returns:
            The estimated token count.
        """
        total_words = sum(len(e.content.split()) for e in entries)
        return int(total_words * 1.3)

    async def compress(self, context_entries: List[MemoryEntry]) -> List[MemoryEntry]:
        """
        Checks the total token count of the context. If it exceeds the threshold,
        compresses the older half of the entries using the LLM and replaces them
        with a single summarized MemoryEntry.

        Args:
            context_entries: The current list of working memory entries.

        Returns:
            A new list of memory entries, potentially with the older half compressed.
        """
        if not context_entries:
            return context_entries

        current_tokens = self._get_token_length(context_entries)
        if current_tokens <= self.token_threshold:
            return context_entries

        logging.info(f"Virtual context exceeds threshold ({current_tokens} > {self.token_threshold}). Compressing...")

        # Select the oldest half for compression
        half_idx = max(1, len(context_entries) // 2)
        to_compress = context_entries[:half_idx]
        to_keep = context_entries[half_idx:]

        combined_text = "\n".join(e.content for e in to_compress)

        if self.llm:
            prompt = [
                {"role": "system", "content": "You are a context compression engine. Summarize these memory entries concisely to save tokens while preserving critical facts."},
                {"role": "user", "content": combined_text}
            ]
            try:
                summary_content = await self.llm.chat_completion(prompt)
            except Exception as e:
                logging.error(f"Failed to summarize context: {e}")
                summary_content = f"Summary of {len(to_compress)} items: {combined_text[:100]}..."
        else:
            summary_content = f"Summary of {len(to_compress)} items: {combined_text[:100]}..."

        # Calculate average importance and emotional state from the compressed chunk
        avg_importance = sum(e.importance for e in to_compress) / len(to_compress)

        valid_emotions = [e.emotional_state for e in to_compress if e.emotional_state]
        if valid_emotions:
            avg_p = sum(s.pleasure for s in valid_emotions) / len(valid_emotions)
            avg_a = sum(s.arousal for s in valid_emotions) / len(valid_emotions)
            avg_d = sum(s.dominance for s in valid_emotions) / len(valid_emotions)
            avg_state = PADState(avg_p, avg_a, avg_d)
        else:
            avg_state = PADState(0.0, 0.0, 0.0)

        user_id = to_compress[0].user_id

        summary_entry = MemoryEntry(
            content=summary_content,
            importance=avg_importance,
            emotional_state=avg_state,
            user_id=user_id
        )

        return [summary_entry] + to_keep
