import logging
import asyncio
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin
from magda_agent.memory.working import WorkingMemory, MemoryEntry
from magda_agent.memory.episodic import EpisodicMemory

class VirtualContextPaginationPlugin(ContextPlugin):
    """
    Virtual Context component inside Context Engine to handle long conversational memory
    pagination by splitting it into pages of working memory and episodic memory.
    """

    def __init__(self, max_tokens: int = 4000) -> None:
        """
        Initializes the VirtualContextPaginationPlugin.

        Args:
            max_tokens: The maximum number of tokens allowed in working memory.
        """
        self.config: Dict[str, Any] = {}
        self.working_memory: Optional[WorkingMemory] = None
        self.episodic_memory: Optional[EpisodicMemory] = None
        self.max_tokens = max_tokens
        logging.debug(f"Initialized VirtualContextPaginationPlugin with max_tokens={max_tokens}")

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """
        Bootstrap lifecycle hook. Initializes plugin state from config.

        Args:
            config: Configuration dictionary injected by ContextEngine.
        """
        self.config = config
        self.working_memory = config.get("working_memory")
        self.episodic_memory = config.get("episodic_memory")
        if "max_tokens" in config:
            self.max_tokens = config["max_tokens"]
        logging.info("VirtualContextPaginationPlugin bootstrapped with config.")

    def get_token_length(self, entries: List[MemoryEntry]) -> int:
        """
        Calculates a heuristic token length for the given memory entries.

        Args:
            entries: A list of MemoryEntry objects.

        Returns:
            The estimated token count.
        """
        total_words = sum(len(e.content.split()) for e in entries)
        return int(total_words * 1.3)

    def page_out_oldest(self, user_id: int) -> None:
        """
        Pages out the oldest half of working memory to episodic memory.
        """
        if not self.working_memory or not self.episodic_memory:
            return

        entries = self.working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        count_to_remove = max(1, len(entries) // 2)
        to_remove = entries[:count_to_remove]

        for entry in to_remove:
            metadata = {
                "paged_out_explicitly": True,
                "importance": entry.importance,
                "pad_p": entry.emotional_state.pleasure,
                "pad_a": entry.emotional_state.arousal,
                "pad_d": entry.emotional_state.dominance
            }
            if entry.tags:
                metadata["tags"] = ",".join(entry.tags)

            self.episodic_memory.store_event(
                text=entry.content,
                metadata=metadata,
                user_id=user_id
            )
            logging.debug(f"Paged out memory entry {entry.id} for user {user_id}")
            self.working_memory.remove(entry.id, user_id=user_id)

    def before_retrieval(self, query: str, user_id: int) -> str:
        """
        Synchronous hook before context retrieval.
        Checks if working memory size exceeds limits and paginates if necessary.

        Args:
            query: The original search query.
            user_id: ID of the user requesting context.

        Returns:
            The original query.
        """
        if not self.working_memory or not self.episodic_memory:
            return query

        entries = self.working_memory.get_entries(user_id=user_id)
        current_tokens = self.get_token_length(entries)

        if current_tokens > self.max_tokens:
            logging.info(f"VirtualContextPaginationPlugin: Working memory context length ({current_tokens} tokens) exceeds limit ({self.max_tokens} tokens). Paginating out...")
            # Iteratively page out oldest entries until the total token count is within max_tokens
            while self.get_token_length(self.working_memory.get_entries(user_id=user_id)) > self.max_tokens and len(self.working_memory.get_entries(user_id=user_id)) > 0:
                self.page_out_oldest(user_id)

        return query
