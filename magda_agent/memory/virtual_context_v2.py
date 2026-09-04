import logging
from typing import TYPE_CHECKING, List, Optional, Any, Callable, Awaitable
from magda_agent.llm_client import LLMClient
from magda_agent.emotions.engine import PADState
from magda_agent.memory.working import WorkingMemory, MemoryEntry

if TYPE_CHECKING:
    from magda_agent.memory.episodic import EpisodicMemory

class VirtualContextManagerV2:
    """
    VirtualContextManagerV2 handles advanced virtual context management for
    explicitly paging out old short-term memory (WorkingMemory) into EpisodicMemory,
    and paging it back in when requested.
    """
    def __init__(self, llm_client: Optional['LLMClient'] = None, max_tokens: int = 1000000) -> None:
        """
        Initializes the VirtualContextManagerV2.

        Args:
            llm_client: An optional LLMClient for advanced summarization during compression.
            max_tokens: The maximum number of tokens to support in the LargeContextWindow (default 1M).
        """
        self.llm_client = llm_client
        from magda_agent.memory.large_context import LargeContextWindow
        self.large_context_window = LargeContextWindow(max_tokens=max_tokens)

    async def compress_context(self, entries: List['MemoryEntry']) -> 'MemoryEntry':
        """
        Compresses multiple memory entries into a single summary entry.

        Args:
            entries: A list of MemoryEntry objects to compress.

        Returns:
            A new MemoryEntry containing the summarized context.

        Raises:
            ValueError: If the entries list is empty.
        """
        if not entries:
            raise ValueError("No entries to compress")

        combined_text = "\n".join(e.content for e in entries)

        if self.llm_client:
            prompt = [{"role": "system", "content": "Summarize these memory entries concisely."},
                      {"role": "user", "content": combined_text}]
            summary = await self.llm_client.chat_completion(prompt)
        else:
            summary = f"Summary of {len(entries)} items: {combined_text[:50]}..."

        user_id = entries[0].user_id
        avg_importance = sum(e.importance for e in entries) / len(entries)
        avg_p = sum(e.emotional_state.pleasure for e in entries) / len(entries)
        avg_a = sum(e.emotional_state.arousal for e in entries) / len(entries)
        avg_d = sum(e.emotional_state.dominance for e in entries) / len(entries)
        state = PADState(avg_p, avg_a, avg_d)

        return MemoryEntry(content=summary, importance=avg_importance, emotional_state=state, user_id=user_id)

    async def page_out_explicit(self, working_memory: 'WorkingMemory', episodic_memory: 'EpisodicMemory', user_id: int, count: int = 1) -> None:
        """
        Explicitly move the oldest `count` entries from WorkingMemory to EpisodicMemory.
        This provides more explicit pagination control compared to basic implicit paging out.

        Args:
            working_memory: The WorkingMemory instance to page out from.
            episodic_memory: The EpisodicMemory instance to page out into.
            user_id: The ID of the user.
            count: Number of oldest entries to page out.
        """
        entries = working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        to_remove = entries[:count]
        if len(to_remove) > 1:
            try:
                # Attempt to compress context before paging out
                compressed_entry = await self.compress_context(to_remove)
                to_remove = [compressed_entry]
            except Exception as e:
                logging.error(f"Context compression failed during page_out_explicit: {e}")

        # We need the original entries to remove from working memory by their IDs
        # If compressed, to_remove only contains the new compressed entry,
        # so we also need to iterate over the original `entries[:count]` to remove them
        original_to_remove = entries[:count]

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

            episodic_memory.store_event(
                text=entry.content,
                metadata=metadata,
                user_id=user_id
            )
            logging.debug(f"Paged out memory entry {entry.id} for user {user_id}")

            # Also index the paged-out entry in the LargeContextWindow for fast in-memory access
            tokens = self.get_token_length([entry])
            self.large_context_window.add_chunk(
                content=entry.content,
                tokens=tokens,
                metadata={
                    "user_id": user_id,
                    "importance": entry.importance,
                }
            )

        for orig_entry in original_to_remove:
            working_memory.remove(orig_entry.id, user_id=user_id)

    async def page_in_explicit(self, working_memory: 'WorkingMemory', episodic_memory: 'EpisodicMemory', user_id: int, query: str, top_k: int = 5) -> None:
        """
        Explicitly recall relevant events from EpisodicMemory and load them into WorkingMemory
        based on a search query.

        Args:
            working_memory: The WorkingMemory instance to page in to.
            episodic_memory: The EpisodicMemory instance to page in from.
            user_id: The ID of the user.
            query: The semantic search query.
            top_k: The number of results to fetch.
        """
        # Retrieve from LargeContextWindow if available
        retrieved_from_lcw = []
        if hasattr(self, 'large_context_window'):
            retrieved_chunks = self.large_context_window.retrieve(query, max_results=top_k)
            for chunk in retrieved_chunks:
                chunk_metadata = chunk.get("metadata", {})
                if chunk_metadata.get("user_id") == user_id:
                    retrieved_from_lcw.append(chunk["content"])

        # Also recall from EpisodicMemory
        events = episodic_memory.recall_events(query=query, top_k=top_k, user_id=user_id)

        # Combine results to ensure robust, comprehensive, and duplicate-free recall
        all_events = []
        seen = set()
        for text in retrieved_from_lcw + events:
            if text not in seen:
                seen.add(text)
                all_events.append(text)

        for event_text in all_events[:top_k]:
            current_contents = [e.content for e in working_memory.get_entries(user_id=user_id)]
            if event_text not in current_contents:
                entry = MemoryEntry(
                    content=event_text,
                    importance=0.5,
                    emotional_state=PADState(0, 0, 0),
                    user_id=user_id
                )
                await working_memory.add(entry)
                logging.debug(f"Paged in explicit memory entry for user {user_id}: {event_text[:30]}...")

    async def paginate_explicit_memory_blocks(self, working_memory: 'WorkingMemory', episodic_memory: 'EpisodicMemory', user_id: int, block_size: int = 2) -> None:
        """
        Divides the working memory into explicit blocks of a given size and pages them out to episodic memory.

        Args:
            working_memory: The WorkingMemory instance to page out from.
            episodic_memory: The EpisodicMemory instance to page out into.
            user_id: The ID of the user.
            block_size: The number of entries per block to paginate.
        """
        entries = working_memory.get_entries(user_id=user_id)
        if not entries:
            return

        to_remove = entries[:- (len(entries) % block_size)] if len(entries) % block_size != 0 else entries
        if not to_remove:
            return

        blocks = [to_remove[i:i + block_size] for i in range(0, len(to_remove), block_size)]

        for block in blocks:
            for entry in block:
                metadata = {
                    "paged_out_explicitly": True,
                    "importance": entry.importance,
                    "pad_p": entry.emotional_state.pleasure,
                    "pad_a": entry.emotional_state.arousal,
                    "pad_d": entry.emotional_state.dominance
                }
                if entry.tags:
                    metadata["tags"] = ",".join(entry.tags)

                episodic_memory.store_event(
                    text=entry.content,
                    metadata=metadata,
                    user_id=user_id
                )
                logging.debug(f"Paged out memory entry {entry.id} in block explicitly for user {user_id}")

            for entry in block:
                working_memory.remove(entry.id, user_id=user_id)

    def get_token_length(self, entries: List['MemoryEntry']) -> int:
        """
        Calculates a heuristic token length for the given memory entries.

        Args:
            entries: A list of MemoryEntry objects.

        Returns:
            The estimated token count.
        """
        total_words = sum(len(e.content.split()) for e in entries)
        return int(total_words * 1.3)

    async def maintain_working_memory_limits(self, working_memory: 'WorkingMemory', episodic_memory: 'EpisodicMemory', user_id: int, max_tokens: int = 4000) -> None:
        """
        Calculates token length of current working context and transparently pages out
        older memories explicitly if the limit is exceeded.

        Args:
            working_memory: The WorkingMemory instance to manage.
            episodic_memory: The EpisodicMemory instance to page into.
            user_id: The ID of the user.
            max_tokens: The maximum token length allowed before paging out.
        """
        if getattr(self, '_in_maintenance', False):
            return
        self._in_maintenance = True

        try:
            entries = working_memory.get_entries(user_id=user_id)
            if not entries:
                return

            # If any individual entry exceeds max_tokens, chunk it into smaller blocks
            for entry in list(entries):
                entry_tokens = self.get_token_length([entry])
                if entry_tokens > max_tokens:
                    logging.info(f"Entry {entry.id} is extremely large ({entry_tokens} tokens). Chunking it...")
                    words = entry.content.split()
                    chunk_words_limit = max(10, int(max_tokens / 1.3 / 2))
                    chunks = [" ".join(words[i:i + chunk_words_limit]) for i in range(0, len(words), chunk_words_limit)]

                    working_memory.remove(entry.id, user_id=user_id)

                    for idx, chunk_content in enumerate(chunks):
                        chunk_entry = MemoryEntry(
                            content=chunk_content,
                            importance=entry.importance,
                            emotional_state=entry.emotional_state,
                            user_id=user_id,
                            tags=(entry.tags or []) + [f"chunk_{idx}"]
                        )
                        await working_memory.add(chunk_entry)

            # Re-fetch entries after potential chunking
            entries = working_memory.get_entries(user_id=user_id)
            current_tokens = self.get_token_length(entries)

            if current_tokens <= max_tokens:
                return

            logging.info(f"Working memory context length ({current_tokens} tokens) exceeds limit ({max_tokens} tokens). Paging out...")

            # Iteratively page out least important entries until the total token count is within aggressive threshold (75% of max_tokens)
            aggressive_threshold = max_tokens * 0.75
            while self.get_token_length(entries) > aggressive_threshold and len(entries) > 1:
                # Sort entries by importance ascending to page out least important first
                entries_sorted_by_importance = sorted(entries, key=lambda e: e.importance)

                # To page out explicit items that are not necessarily the oldest,
                # we can use our page_out_explicit logic or manually page them out.
                # page_out_explicit removes entries[:count]. We need to adjust working_memory directly
                # or temporarily re-order them? Working memory doesn't allow re-ordering easily.
                # We will manually page out the least important entries here.

                count_to_remove = max(1, len(entries) // 2)
                to_remove = entries_sorted_by_importance[:count_to_remove]

                if len(to_remove) > 1:
                    try:
                        compressed_entry = await self.compress_context(to_remove)
                        to_remove = [compressed_entry]
                    except Exception as e:
                        logging.warning(f"Compression failed during aggressive paging: {e}")

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

                    episodic_memory.store_event(
                        text=entry.content,
                        metadata=metadata,
                        user_id=user_id
                    )
                    logging.debug(f"Aggressively paged out memory entry {entry.id} (importance: {entry.importance}) for user {user_id}")

                    if hasattr(self, 'large_context_window'):
                        tokens = self.get_token_length([entry])
                        self.large_context_window.add_chunk(
                            content=entry.content,
                            tokens=tokens,
                            metadata={
                                "user_id": user_id,
                                "importance": entry.importance,
                            }
                        )

                # Remove from working memory based on ID
                original_entries_to_remove = entries_sorted_by_importance[:count_to_remove]
                for orig_entry in original_entries_to_remove:
                    working_memory.remove(orig_entry.id, user_id=user_id)

                entries = working_memory.get_entries(user_id=user_id)
        finally:
            self._in_maintenance = False


class VirtualWorkingMemoryV2(WorkingMemory):
    """
    VirtualWorkingMemoryV2 subclass of WorkingMemory that tracks token usage
    dynamically and automatically pages out older entries into EpisodicMemory
    when configured token thresholds are exceeded.
    """
    def __init__(self, limit: int = 10, context_engine: Optional[Any] = None, token_threshold: int = 4000) -> None:
        super().__init__(limit=limit, context_engine=context_engine)
        self.token_threshold = token_threshold

    def get_token_count(self, user_id: Optional[int] = None) -> int:
        """
        Dynamically and accurately tracks approximate token counts of active working memory.
        """
        entries = self.get_entries(user_id=user_id)
        total_words = sum(len(e.content.split()) for e in entries)
        return int(total_words * 1.3)

    async def add(self, entry: MemoryEntry, summarizer: Optional[Callable[[List['MemoryEntry']], Awaitable['MemoryEntry']]] = None) -> None:
        """
        Adds a memory entry to active working memory and evaluates token usage limits,
        automatically paging out older memories to prevent context overflow.
        """
        await super().add(entry, summarizer)

        u_id = entry.user_id if entry.user_id is not None else -1
        vcm = getattr(self, 'virtual_context_manager', None)
        em = getattr(self, 'episodic_memory', None)

        if vcm and em:
            await vcm.maintain_working_memory_limits(self, em, u_id, max_tokens=self.token_threshold)
