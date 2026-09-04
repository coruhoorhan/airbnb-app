import logging
from typing import List, Any, Dict, Optional

class SemanticCompressionLifecyclePluginV6:
    """
    Advanced lifecycle plugin for Context Engine to compress semantic memory dynamically.
    Implements the ContextPlugin protocol.
    """

    def __init__(self, llm: Optional[Any] = None) -> None:
        """
        Initialize the plugin.

        Args:
            llm: Optional LLM client to use for semantic compression.
        """
        self.llm = llm
        self.config: Dict[str, Any] = {}

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """
        Initialize the plugin with configuration.

        Args:
            config: Configuration dictionary.
        """
        self.config = config
        logging.info("SemanticCompressionLifecyclePluginV6 bootstrapped.")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Process incoming content before it is stored or used.

        Args:
            content: The incoming string content.
            metadata: Associated metadata.

        Returns:
            Processed content.
        """
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """
        Assemble the context string from retrieved items for the LLM.

        Args:
            context_items: List of retrieved context items.
            metadata: Associated metadata.

        Returns:
            The assembled context string.
        """
        return "\n".join([str(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """
        Compact or summarize the context when limits are reached.
        Uses an LLM for semantic compression if available.

        Args:
            context_items: List of current context items.
            metadata: Associated metadata, typically including 'limit'.

        Returns:
            A compacted list of context items.
        """
        limit = metadata.get("limit", 10)
        if len(context_items) <= limit:
            return context_items

        if self.llm is None:
            logging.warning("No LLM available for semantic compression, dropping oldest items.")
            return context_items[-limit:]

        # Perform semantic compression using LLM on the oldest items
        num_to_compress = len(context_items) - limit + 1
        to_compress = context_items[:num_to_compress]
        remaining = context_items[num_to_compress:]

        combined_text = "\n".join([f"- {getattr(e, 'content', str(e))}" for e in to_compress])
        prompt = f"Please semantically compress the following context items into a single concise summary:\n{combined_text}"

        try:
            summary_content = await self.llm.chat_completion([
                {"role": "system", "content": "You compress semantic memory context. Return only the summary text."},
                {"role": "user", "content": prompt}
            ], temperature=0.3)

            from magda_agent.memory.working import MemoryEntry

            first = to_compress[0] if to_compress else None
            avg_importance = sum(getattr(e, 'importance', 0.5) for e in to_compress) / max(1, len(to_compress))
            tags = list(set(t for e in to_compress if isinstance(getattr(e, 'tags', []), list) for t in getattr(e, 'tags', [])))

            summary_entry = MemoryEntry(
                content=summary_content.strip(),
                importance=avg_importance,
                emotional_state=getattr(first, 'emotional_state', None) if first else None,
                tags=tags,
                user_id=getattr(first, 'user_id', None) if first else None
            )
            return [summary_entry] + remaining
        except Exception as e:
            logging.error(f"Semantic compression failed: {e}")
            return context_items[-limit:]

    def before_retrieval(self, query: str, user_id: int) -> str:
        """
        Called before context is retrieved. Can modify the query.

        Args:
            query: The initial query.
            user_id: The ID of the user.

        Returns:
            The potentially modified query.
        """
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Called after context is retrieved. Can modify the retrieved context.

        Args:
            context: The retrieved context items.
            query: The query used for retrieval.
            user_id: The ID of the user.

        Returns:
            The potentially modified context list.
        """
        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        """
        Called before context is written. Can modify the context.

        Args:
            context: The context to write.
            user_id: The ID of the user.

        Returns:
            The potentially modified context.
        """
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """
        Called after context is written.

        Args:
            context: The context that was written.
            user_id: The ID of the user.
        """
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """
        Called when the overall context is updated.

        Args:
            new_context: The new updated context.
            user_id: The ID of the user.
        """
        pass

    async def pre_process(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Called to pre-process content before ingestion.

        Args:
            content: The initial content.
            metadata: Associated metadata.

        Returns:
            The pre-processed content.
        """
        return content

    async def post_process(self, response: str, metadata: Dict[str, Any]) -> str:
        """
        Called to post-process a response before returning to user.

        Args:
            response: The generated response.
            metadata: Associated metadata.

        Returns:
            The post-processed response.
        """
        return response
