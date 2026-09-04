import logging
from typing import TYPE_CHECKING, List, Optional
from magda_agent.llm_client import LLMClient
from magda_agent.emotions.engine import PADState
from magda_agent.memory.working import MemoryEntry

if TYPE_CHECKING:
    from magda_agent.memory.working import WorkingMemory
    from magda_agent.memory.episodic import EpisodicMemory

class VirtualContextManagerV4:
    """
    VirtualContextManagerV4 implements selective memory compression and dynamic context paging
    from WorkingMemory to EpisodicMemory based on context size limits, importance thresholds,
    and semantic relevance, inspired by Claude and MemGPT patterns.
    """
    def __init__(
        self,
        llm_client: Optional['LLMClient'] = None,
        default_max_tokens: int = 4000,
        default_importance_threshold: float = 0.5
    ) -> None:
        """
        Initializes VirtualContextManagerV4.

        Args:
            llm_client: Optional LLMClient for semantic summarization during compression.
            default_max_tokens: Default maximum token threshold for working memory context.
            default_importance_threshold: Default importance threshold for selective paging.
        """
        self.llm_client = llm_client
        self.default_max_tokens = default_max_tokens
        self.default_importance_threshold = default_importance_threshold

    def get_token_length(self, entries: List['MemoryEntry']) -> int:
        """
        Calculates a heuristic token length for the provided memory entries.

        Args:
            entries: List of MemoryEntry objects.

        Returns:
            Estimated total token count.
        """
        total_words = sum(len(e.content.split()) for e in entries)
        return int(total_words * 1.3)

    async def compress_context(self, entries: List['MemoryEntry']) -> 'MemoryEntry':
        """
        Compresses multiple memory entries into a single summarized MemoryEntry.

        Args:
            entries: A list of MemoryEntry objects to compress.

        Returns:
            A new MemoryEntry containing summarized content.

        Raises:
            ValueError: If entries list is empty.
        """
        if not entries:
            raise ValueError("No entries to compress")

        combined_text = "\n".join(e.content for e in entries)

        if self.llm_client:
            prompt = [
                {"role": "system", "content": "Summarize these memory entries concisely into a clear unified memory context."},
                {"role": "user", "content": combined_text}
            ]
            summary = await self.llm_client.chat_completion(prompt)
        else:
            summary = f"Summary of {len(entries)} items: {combined_text[:50]}..."

        user_id = entries[0].user_id
        avg_importance = sum(e.importance for e in entries) / len(entries)

        # Average emotional state calculations
        p_states = [e.emotional_state.pleasure for e in entries if e.emotional_state]
        a_states = [e.emotional_state.arousal for e in entries if e.emotional_state]
        d_states = [e.emotional_state.dominance for e in entries if e.emotional_state]

        avg_p = sum(p_states) / len(p_states) if p_states else 0.0
        avg_a = sum(a_states) / len(a_states) if a_states else 0.0
        avg_d = sum(d_states) / len(d_states) if d_states else 0.0

        state = PADState(avg_p, avg_a, avg_d)

        all_tags = set()
        for e in entries:
            if e.tags:
                all_tags.update(e.tags)

        return MemoryEntry(
            content=summary,
            importance=avg_importance,
            emotional_state=state,
            tags=list(all_tags),
            user_id=user_id
        )

    async def selective_page_out(
        self,
        working_memory: 'WorkingMemory',
        episodic_memory: 'EpisodicMemory',
        user_id: int,
        count: Optional[int] = None,
        importance_threshold: Optional[float] = None
    ) -> None:
        """
        Selectively pages out memory entries from WorkingMemory to EpisodicMemory.
        Prioritizes entries below the importance threshold or oldest items if count is specified.

        Args:
            working_memory: WorkingMemory instance.
            episodic_memory: EpisodicMemory instance.
            user_id: ID of the user context.
            count: Optional explicit number of entries to page out.
            importance_threshold: Optional importance cutoff (entries <= threshold selected).
        """
        entries = working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        threshold = importance_threshold if importance_threshold is not None else self.default_importance_threshold

        # Select candidates for paging out: low importance entries first
        low_importance_entries = [e for e in entries if e.importance <= threshold]

        if low_importance_entries:
            selected_entries = low_importance_entries[:count] if count else low_importance_entries
        else:
            num_to_select = count if count is not None else max(1, len(entries) // 2)
            selected_entries = entries[:num_to_select]

        if not selected_entries:
            return

        original_selected = list(selected_entries)
        to_store = list(selected_entries)

        if len(to_store) > 1:
            try:
                compressed = await self.compress_context(to_store)
                to_store = [compressed]
            except Exception as e:
                logging.error(f"Context compression failed during selective_page_out: {e}")

        for entry in to_store:
            metadata = {
                "paged_out_selectively": True,
                "importance": entry.importance,
            }
            if entry.emotional_state:
                metadata["pad_p"] = entry.emotional_state.pleasure
                metadata["pad_a"] = entry.emotional_state.arousal
                metadata["pad_d"] = entry.emotional_state.dominance
            if entry.tags:
                metadata["tags"] = ",".join(entry.tags)

            episodic_memory.store_event(
                text=entry.content,
                metadata=metadata,
                user_id=user_id
            )
            logging.debug(f"Selectively paged out memory entry {entry.id} for user {user_id}")

        for orig_entry in original_selected:
            working_memory.remove(orig_entry.id, user_id=user_id)

    async def selective_page_in(
        self,
        working_memory: 'WorkingMemory',
        episodic_memory: 'EpisodicMemory',
        user_id: int,
        query: str,
        top_k: int = 5
    ) -> None:
        """
        Selectively recalls relevant events from EpisodicMemory and loads them into WorkingMemory.

        Args:
            working_memory: WorkingMemory target.
            episodic_memory: EpisodicMemory source.
            user_id: User context ID.
            query: Semantic search query string.
            top_k: Max entries to retrieve and page in.
        """
        events = episodic_memory.recall_events(query=query, top_k=top_k, user_id=user_id)
        current_contents = {e.content for e in working_memory.get_entries(user_id=user_id)}

        for event_text in events:
            if event_text not in current_contents:
                entry = MemoryEntry(
                    content=event_text,
                    importance=0.6,
                    emotional_state=PADState(0, 0, 0),
                    tags=["paged_in"],
                    user_id=user_id
                )
                await working_memory.add(entry)
                logging.debug(f"Selectively paged in memory entry for user {user_id}: {event_text[:30]}...")

    async def maintain_working_memory_limits(
        self,
        working_memory: 'WorkingMemory',
        episodic_memory: 'EpisodicMemory',
        user_id: int,
        max_tokens: Optional[int] = None
    ) -> None:
        """
        Monitors working memory token usage and selectively pages out old/low-importance memories
        when the token limit is breached.

        Args:
            working_memory: WorkingMemory instance.
            episodic_memory: EpisodicMemory target for paged out items.
            user_id: User context ID.
            max_tokens: Token threshold limit.
        """
        limit = max_tokens if max_tokens is not None else self.default_max_tokens
        entries = working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        current_tokens = self.get_token_length(entries)
        if current_tokens <= limit:
            return

        logging.info(
            f"Working memory context length ({current_tokens} tokens) exceeds limit ({limit} tokens). "
            "Selectively paging out memory entries..."
        )

        while self.get_token_length(working_memory.get_entries(user_id=user_id)) > limit:
            active_entries = working_memory.get_entries(user_id=user_id)
            if not active_entries:
                break
            count_to_remove = max(1, len(active_entries) // 2)
            await self.selective_page_out(
                working_memory,
                episodic_memory,
                user_id,
                count=count_to_remove
            )
