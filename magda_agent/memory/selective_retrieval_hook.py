from typing import List, Any
from magda_agent.memory.selective_retrieval import SelectiveMemoryRetriever
from magda_agent.memory.working import MemoryEntry
from magda_agent.emotions.engine import PADState

class SelectiveRetrievalHook:
    """
    A plugin for the ContextEngine that hooks into after_retrieval
    to fetch contextually relevant episodic memories based on the planner's
    current subgoal (the query) and append them to the working memory context.
    """
    def __init__(self, retriever: SelectiveMemoryRetriever, top_k: int = 5):
        """
        Initializes the SelectiveRetrievalHook.

        Args:
            retriever: The SelectiveMemoryRetriever instance to use for finding episodes.
            top_k: The maximum number of episodic memories to retrieve.
        """
        self.retriever = retriever
        self.top_k = top_k

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Lifecycle hook called after context is retrieved.
        Retrieves top_k episodic memories relevant to the query and appends them
        to the context.

        Args:
            context: The initially retrieved context (from WorkingMemory).
            query: The search query, typically the planner's current task/subgoal.
            user_id: The ID of the user requesting context.

        Returns:
            The augmented list of context items.
        """
        # Ensure we don't modify the original list in place unexpectedly if passed by reference
        updated_context = list(context)

        episodes = self.retriever.get_relevant_episodes(current_task=query, user_id=user_id, top_k=self.top_k)

        for ep in episodes:
            # Wrap string episode in a MemoryEntry if needed,
            # ContextEngine can usually handle strings or MemoryEntries.
            # We'll use MemoryEntry to be consistent with working memory.
            entry = MemoryEntry(
                content=ep,
                importance=0.5,
                emotional_state=PADState(0.0, 0.0, 0.0),
                tags=["episodic_recall"],
                user_id=user_id
            )
            updated_context.append(entry)

        return updated_context
