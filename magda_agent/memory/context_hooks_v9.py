import logging
import time
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin

class SemanticMemoryFilterPlugin(ContextPlugin):
    """
    OpenClaw-inspired V9 Context Plugin.
    Implements a post-retrieval hook to filter out outdated semantic memories
    before they enter the active context window.
    """

    def __init__(self, max_age_seconds: float = 30 * 24 * 3600) -> None:
        """
        Initializes the SemanticMemoryFilterPlugin.

        Args:
            max_age_seconds: The maximum allowed age in seconds for a semantic memory.
                             Defaults to 30 days.
        """
        self.max_age_seconds = max_age_seconds
        self.config: Dict[str, Any] = {}
        logging.debug(f"Initialized SemanticMemoryFilterPlugin with max_age_seconds={self.max_age_seconds}")

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """
        Bootstrap lifecycle hook. Initializes plugin state from config.
        Allows overriding max_age_seconds dynamically.

        Args:
            config: Configuration dictionary injected by ContextEngine.
        """
        self.config = config
        if "max_age_seconds" in config:
            self.max_age_seconds = float(config["max_age_seconds"])
        logging.info(f"SemanticMemoryFilterPlugin bootstrapped with max_age_seconds={self.max_age_seconds}")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process incoming content before it is stored or used. (No-op here)"""
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Assemble the context string from retrieved items for the LLM. (No-op here)"""
        return "\n".join([str(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact or summarize the context when limits are reached. (No-op here)"""
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """Called before context is retrieved. (No-op here)"""
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Called after context is retrieved.
        Filters out semantic memories (identified by dicts with 'metadata')
        where the timestamp is older than max_age_seconds.

        Args:
            context: List of retrieved context elements.
            query: The query that was executed.
            user_id: ID of the user.

        Returns:
            Filtered context list.
        """
        filtered_context = []
        current_time = time.time()

        for item in context:
            keep_item = True
            if isinstance(item, dict) and "metadata" in item and isinstance(item["metadata"], dict):
                metadata = item["metadata"]
                if "timestamp" in metadata:
                    try:
                        item_time = float(metadata["timestamp"])
                        age = current_time - item_time
                        if age > self.max_age_seconds:
                            keep_item = False
                            logging.debug(f"Filtered out outdated semantic memory: ID={item.get('id', 'unknown')}, age={age:.2f}s")
                    except (ValueError, TypeError):
                        logging.warning(f"Invalid timestamp in semantic memory metadata: {metadata['timestamp']}")

            if keep_item:
                filtered_context.append(item)

        return filtered_context

    def before_write(self, context: Any, user_id: int) -> Any:
        """Called before context is written. (No-op here)"""
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Called after context is written. (No-op here)"""
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Called when the overall context is updated. (No-op here)"""
        pass

    async def pre_process(self, content: str, metadata: Dict[str, Any]) -> str:
        """Called to pre-process content before ingestion. (No-op here)"""
        return content

    async def post_process(self, response: str, metadata: Dict[str, Any]) -> str:
        """Called to post-process a response before returning to user. (No-op here)"""
        return response
