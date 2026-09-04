"""
Claude Subagent Token Context Optimizer V2.

This module provides a token compression stage directly prior to subagent spawning.
Inspired by Claude Agent SDK context compression trends (June 2026).
"""

from typing import Callable, List, Optional, Awaitable, Union
import asyncio

class ClaudeTokenContextOptimizerV2:
    """
    Optimizes and compresses token context for subagents before spawning.
    """

    def __init__(
        self,
        summarizer: Callable[[str], Union[str, Awaitable[str]]],
        max_tokens: int = 8000
    ):
        """
        Initialize the ClaudeTokenContextOptimizerV2.

        Args:
            summarizer: A callable (sync or async) that takes a text string and returns a summarized string.
            max_tokens: The maximum allowable tokens for the context before compression is triggered.
        """
        self.summarizer = summarizer
        self.max_tokens = max_tokens

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a string.
        Approximates 1 token per 4 characters.

        Args:
            text: The text to evaluate.

        Returns:
            The estimated token count.
        """
        return len(text) // 4

    async def optimize_context(self, context_entries: List[str]) -> List[str]:
        """
        Optimizes a list of context entries so their total token count is under max_tokens.
        Compresses the oldest entries (beginning of the list) if necessary.

        Args:
            context_entries: A list of string memory/context entries.

        Returns:
            An optimized list of context entries that fits within max_tokens.
        """
        if not context_entries:
            return []

        total_tokens = sum(self._estimate_tokens(entry) for entry in context_entries)

        if total_tokens <= self.max_tokens:
            return list(context_entries)

        optimized = list(context_entries)

        # Iteratively compress from the oldest (index 0) until we are under the limit
        for i in range(len(optimized)):
            current_total = sum(self._estimate_tokens(entry) for entry in optimized)
            if current_total <= self.max_tokens:
                break

            original_text = optimized[i]

            # Use the summarizer
            result = self.summarizer(original_text)
            if asyncio.iscoroutine(result):
                compressed_text = await result
            else:
                compressed_text = result # type: ignore

            optimized[i] = f"[Compressed Summary] {compressed_text}"

        return optimized
