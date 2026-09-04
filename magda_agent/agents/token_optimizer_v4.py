"""
Token Optimizer V4 for Claude Agent Subagents.

This module provides a token optimizer to aggressively summarize working memory
before delegating context to newly spawned subagents, preventing token limit
exhaustion in parallel runs.
"""

from typing import Callable


class TokenOptimizerV4:
    """
    Optimizes payload tokens for subagent context delegation.
    """

    def __init__(self, summarizer: Callable[[str], str]):
        """
        Initialize the optimizer.

        Args:
            summarizer: A callable that accepts a string context and returns a
                        summarized version of it.
        """
        self._summarizer = summarizer

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a given text.
        This is a rudimentary approximation (1 token ~= 4 characters).

        Args:
            text: The text to estimate.

        Returns:
            An approximate token count.
        """
        return len(text) // 4

    def optimize(self, context: str, token_limit: int) -> str:
        """
        Optimize the context to fit within the given token limit.

        If the context exceeds the token limit, it is compressed using the
        provided summarizer function.

        Args:
            context: The original working memory context.
            token_limit: The maximum allowed tokens before compression triggers.

        Returns:
            The original context if within limits, or a compressed version.
        """
        estimated_tokens = self._estimate_tokens(context)
        if estimated_tokens <= token_limit:
            return context

        return self._summarizer(context)
