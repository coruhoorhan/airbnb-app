"""
Token Compressor V2 for Claude Code Subagents.

This module provides a token compressor that aggressively summarizes working memory
before delegating context to newly spawned parallel subagents, mitigating token limit
exhaustion. Inspired by Claude Agent SDK (June 2026).
"""

from typing import Callable, Union, List

class TokenCompressorV2:
    """
    Evaluates working memory against a token threshold and compresses it using an LLM.
    """

    def __init__(self, summarizer: Callable[[str], str], token_threshold: int = 4000):
        """
        Initialize the TokenCompressorV2.

        Args:
            summarizer: A callable (like an LLM client or mock) that accepts a string context
                        and returns a summarized version.
            token_threshold: The maximum number of tokens allowed before compression triggers.
        """
        self._summarizer = summarizer
        self.token_threshold = token_threshold

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a given text.
        This uses a rudimentary approximation (1 token ~= 4 characters).

        Args:
            text: The text to estimate.

        Returns:
            An approximate token count.
        """
        return len(text) // 4

    def compress(self, context: Union[str, List[str]]) -> str:
        """
        Evaluate and compress the context if it exceeds the token threshold.

        Args:
            context: The working memory context, either as a single string or a list of strings.

        Returns:
            The original context (joined if a list) if under the limit, or a compressed summary.
        """
        if isinstance(context, list):
            context_str = "\n".join(context)
        else:
            context_str = str(context)

        estimated_tokens = self._estimate_tokens(context_str)
        if estimated_tokens <= self.token_threshold:
            return context_str

        # Delegate summary generation to the LLM (summarizer)
        summary = self._summarizer(context_str)
        return summary
