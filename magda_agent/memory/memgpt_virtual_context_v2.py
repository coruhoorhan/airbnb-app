"""
Module containing the MemGPTVirtualContextManagerV2 implementation.
"""

from typing import List


class MemGPTVirtualContextManagerV2:
    """
    A context manager inspired by MemGPT that manages a virtual context window.

    It transparently swaps out the oldest active memories into an episodic
    storage list when the added memories exceed the configured max_tokens.
    """

    def __init__(self, max_tokens: int = 1000) -> None:
        """
        Initializes the context manager.

        Args:
            max_tokens: The maximum number of tokens allowed in the active context.
        """
        self.max_tokens = max_tokens
        self.active_context: List[str] = []
        self.episodic_memory: List[str] = []

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimates the number of tokens in a string.
        Uses a simple mock approximation: len(text) // 4.

        Args:
            text: The text to estimate tokens for.

        Returns:
            The estimated token count.
        """
        # Ensure it returns at least 1 for non-empty strings if len < 4
        return max(1, len(text) // 4) if text else 0

    def _get_active_tokens(self) -> int:
        """
        Calculates the total tokens currently in the active context.

        Returns:
            The total estimated token count of active memories.
        """
        return sum(self._estimate_tokens(memory) for memory in self.active_context)

    def add_memory(self, memory: str) -> None:
        """
        Adds a memory to the active context.
        If adding the memory causes the active context to exceed max_tokens,
        older memories are swapped out to episodic memory.

        Args:
            memory: The memory string to add.
        """
        self.active_context.append(memory)

        while self._get_active_tokens() > self.max_tokens and len(self.active_context) > 1:
            # Swap out the oldest memory (first element) to episodic memory
            oldest_memory = self.active_context.pop(0)
            self.episodic_memory.append(oldest_memory)

    def get_active_context(self) -> List[str]:
        """
        Returns the current active context memories.

        Returns:
            A list of active memory strings.
        """
        return self.active_context.copy()

    def get_episodic_memory(self) -> List[str]:
        """
        Returns the swapped-out episodic memories.

        Returns:
            A list of episodic memory strings.
        """
        return self.episodic_memory.copy()
