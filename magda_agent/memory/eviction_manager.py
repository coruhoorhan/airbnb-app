import logging
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin
from magda_agent.memory.working import WorkingMemory, MemoryEntry
from magda_agent.memory.episodic import EpisodicMemory

class LettaVirtualContextEvictionManager(ContextPlugin):
    """
    Virtual Context component inside Context Engine to handle long conversational memory
    pagination by summarizing and paging working memory into episodic memory blocks.
    Inspired by MemGPT/Letta standard.
    """

    def __init__(self, max_tokens: int = 4000, llm: Optional[Any] = None) -> None:
        """
        Initializes the LettaVirtualContextEvictionManager.

        Args:
            max_tokens: The maximum number of tokens allowed in working memory.
            llm: LLM client for summarization.
        """
        self.config: Dict[str, Any] = {}
        self.working_memory: Optional[WorkingMemory] = None
        self.episodic_memory: Optional[EpisodicMemory] = None
        self.max_tokens = max_tokens
        self.llm = llm
        logging.debug(f"Initialized LettaVirtualContextEvictionManager with max_tokens={max_tokens}")

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
        if "llm" in config:
            self.llm = config["llm"]
        logging.info("LettaVirtualContextEvictionManager bootstrapped with config.")

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

    async def summarize_and_page_out(self, user_id: int) -> None:
        """
        Summarizes the oldest half of working memory and pages it into episodic memory.
        """
        if not self.working_memory or not self.episodic_memory:
            return

        entries = self.working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        count_to_remove = max(1, len(entries) // 2)
        to_remove = entries[:count_to_remove]

        combined_text = "\n".join([f"- {entry.content}" for entry in to_remove])

        summary_text = combined_text
        if self.llm:
            try:
                prompt = f"Summarize the following conversation context block concisely, preserving key facts and details:\n{combined_text}"
                summary_text = await self.llm.chat_completion([
                    {"role": "system", "content": "You summarize context blocks."},
                    {"role": "user", "content": prompt}
                ], temperature=0.3)
                summary_text = summary_text.strip()
            except Exception as e:
                logging.error(f"Failed to summarize context block: {e}")

        metadata = {
            "paged_out_explicitly": True,
            "summarized": True,
            "original_items": len(to_remove)
        }

        if to_remove:
            metadata["importance"] = sum(e.importance for e in to_remove) / len(to_remove)

        self.episodic_memory.store_event(
            text=summary_text,
            metadata=metadata,
            user_id=user_id
        )

        logging.debug(f"Paged out {len(to_remove)} entries into summary for user {user_id}")

        for entry in to_remove:
            self.working_memory.remove(entry.id, user_id=user_id)

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """
        Async hook invoked before limits are hit.
        Checks if working memory size exceeds limits and paginates if necessary.
        """
        user_id = metadata.get("user_id", -1)
        if not self.working_memory or not self.episodic_memory:
            return context_items

        entries = self.working_memory.get_entries(user_id=user_id)
        current_tokens = self.get_token_length(entries)

        if current_tokens > self.max_tokens:
            logging.info(f"EvictionManager: Working memory context length ({current_tokens} tokens) exceeds limit ({self.max_tokens} tokens). Paginating out...")
            while self.get_token_length(self.working_memory.get_entries(user_id=user_id)) > self.max_tokens and len(self.working_memory.get_entries(user_id=user_id)) > 0:
                await self.summarize_and_page_out(user_id)

        # Return the updated items
        return self.working_memory.get_entries(user_id=user_id)
