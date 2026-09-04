"""MCP Kernel Taint Tracking Context Integrator V5.

Integrates taint tracking into working memory to correctly propagate
taint flags through context updates.
"""

from typing import Any, Callable, Dict, List, Optional, Set

from magda_agent.memory.working import MemoryEntry, WorkingMemory
from magda_agent.safety.taint_tracking_v3 import TaintTrackerV3


class TaintedMemoryEntry(MemoryEntry):
    """A memory entry that tracks whether its content is tainted."""

    def __init__(self, content: str, importance: float, emotional_state: Any, tags: List[str] = None, user_id: Optional[int] = None, is_tainted: bool = False, taint_origins: Optional[Set[str]] = None):
        """Initializes a TaintedMemoryEntry.

        Args:
            content: The text content.
            importance: The importance score.
            emotional_state: The associated emotional state.
            tags: List of tags.
            user_id: The user ID.
            is_tainted: True if the content is tainted.
            taint_origins: Set of origins if tainted.
        """
        super().__init__(content=content, importance=importance, emotional_state=emotional_state, tags=tags, user_id=user_id)
        self.is_tainted = is_tainted
        self.taint_origins = taint_origins or set()


class TaintedWorkingMemory(WorkingMemory):
    """WorkingMemory that integrates with TaintTrackerV3 to track and propagate taints."""

    def __init__(self, limit: int = 10, context_engine: Optional[Any] = None, tracker: Optional[TaintTrackerV3] = None):
        """Initializes the TaintedWorkingMemory.

        Args:
            limit: The maximum number of entries per user.
            context_engine: Optional context engine.
            tracker: Optional TaintTrackerV3 instance.
        """
        super().__init__(limit=limit, context_engine=context_engine)
        self.tracker = tracker or TaintTrackerV3()

    async def add(self, entry: MemoryEntry, summarizer: Optional[Callable[[List['MemoryEntry']], Any]] = None) -> None:
        """Adds a memory entry to the active working memory, tracking taints.

        Args:
            entry: The memory entry to add.
            summarizer: Optional summarizer function.
        """
        is_tainted = False
        origins = set()

        # Check if the entry itself is a TaintedMemoryEntry
        if hasattr(entry, 'is_tainted'):
            is_tainted = getattr(entry, 'is_tainted')
            origins = getattr(entry, 'taint_origins', set())

        # Check if the content is tainted using the tracker
        if self.tracker.is_tainted(entry.content):
            is_tainted = True
            origins.update(self.tracker.get_origins(entry.content))

        # Sanitize the content before storing to prevent issues
        clean_content = self.tracker.sanitize(entry.content)

        # Create a new TaintedMemoryEntry
        tainted_entry = TaintedMemoryEntry(
            content=clean_content,
            importance=entry.importance,
            emotional_state=entry.emotional_state,
            tags=entry.tags,
            user_id=entry.user_id,
            is_tainted=is_tainted,
            taint_origins=origins
        )

        # Add the tainted entry to the underlying storage
        await super().add(tainted_entry, summarizer=summarizer)

    def get_entries(self, user_id: Optional[int] = None) -> List[MemoryEntry]:
        """Gets the current working memory entries for a user, reconstructing taints.

        Args:
            user_id: The user ID.

        Returns:
            A list of MemoryEntry with reconstructed taints.
        """
        entries = super().get_entries(user_id=user_id)
        return self._reconstruct_taints(entries)

    def get_all_entries(self) -> List[MemoryEntry]:
        """Gets all flattened memory entries across all users, reconstructing taints.

        Returns:
            A list of all MemoryEntry with reconstructed taints.
        """
        entries = super().get_all_entries()
        return self._reconstruct_taints(entries)

    def _reconstruct_taints(self, entries: List[MemoryEntry]) -> List[MemoryEntry]:
        """Reconstructs taints on the retrieved memory entries.

        Args:
            entries: The list of entries to process.

        Returns:
            The processed list.
        """
        processed_entries = []
        for entry in entries:
            is_tainted = getattr(entry, 'is_tainted', False)
            if is_tainted:
                origins = getattr(entry, 'taint_origins', set())
                # Re-taint the content for the returned entry
                tainted_content = self.tracker.taint_with_origins(entry.content, origins)

                # We return a standard MemoryEntry with the tainted content so callers can use tracker
                processed_entry = MemoryEntry(
                    content=tainted_content,
                    importance=entry.importance,
                    emotional_state=entry.emotional_state,
                    tags=entry.tags,
                    user_id=entry.user_id
                )
                processed_entry.id = entry.id
                processed_entry.timestamp = entry.timestamp

                # Copy tainted specific attrs so it works well internally
                setattr(processed_entry, 'is_tainted', is_tainted)
                setattr(processed_entry, 'taint_origins', origins)

                processed_entries.append(processed_entry)
            else:
                processed_entries.append(entry)

        return processed_entries
