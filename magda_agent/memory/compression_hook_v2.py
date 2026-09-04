import logging
import asyncio
from typing import List, Any, Dict, Optional
from magda_agent.memory.context_engine import ContextPlugin
from magda_agent.llm_client import LLMClient
from magda_agent.memory.working import MemoryEntry

class CompressionHookPluginV2(ContextPlugin):
    """
    A ContextPlugin that automatically compresses short-term memory during
    the before_retrieval phase to maintain a compact context window,
    inspired by MemGPT/Letta trends (Context compression + selective retrieval).
    It compresses virtual context before retrieval if limits are exceeded.
    """

    def __init__(self, memory_system: Optional[Any] = None, llm: Optional[LLMClient] = None, limit: int = 10) -> None:
        """
        Initialize the CompressionHookPluginV2.

        Args:
            memory_system: Optional reference to the overarching MemorySystem
                           which gives access to the short-term working memory.
            llm: Optional reference to an LLMClient for summarization.
            limit: The maximum number of items before compression is triggered.
        """
        self.memory_system = memory_system
        self.llm = llm
        self.limit = limit
        logging.info(f"CompressionHookPluginV2 initialized with limit {limit}.")

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if "memory_system" in config:
            self.memory_system = config["memory_system"]
        if "llm" in config:
            self.llm = config["llm"]
        if "limit" in config:
            self.limit = config["limit"]

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process incoming content before it is stored or used."""
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Assemble the context string from retrieved items for the LLM."""
        return "\n".join([str(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact or summarize the context when limits are reached."""
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """
        Automatically compresses short-term memory before context retrieval.
        It checks the working memory limit, and if exceeded, synchronously
        triggers a background task or blocks on the compression to reduce entries.
        Because before_retrieval is synchronous in ContextEngine, we handle
        LLM compression via asyncio.run if necessary, though ideally we schedule it
        or use a heuristic. For this hook, we will execute it in the event loop.
        """
        logging.debug("CompressionHookPluginV2: before_retrieval executing memory compaction.")

        if self.memory_system and hasattr(self.memory_system, 'working_memory'):
            working_memory = self.memory_system.working_memory

            if hasattr(working_memory, 'get_entries') and hasattr(working_memory, 'remove') and hasattr(working_memory, 'add'):
                entries = working_memory.get_entries(user_id)

                limit = getattr(working_memory, 'limit', self.limit)

                if limit is None:
                    limit = self.limit

                if len(entries) >= limit:
                    entries_to_compress = len(entries) - limit + 2

                    if entries_to_compress < 2:
                        entries_to_compress = 2

                    to_compress = entries[:entries_to_compress]

                    if self.llm:
                        try:
                            try:
                                loop = asyncio.get_running_loop()
                                loop.create_task(self._async_compress(to_compress, working_memory, user_id))
                            except RuntimeError:
                                asyncio.run(self._async_compress(to_compress, working_memory, user_id))
                        except Exception as e:
                            logging.error(f"CompressionHookPluginV2: Error triggering compression: {e}")
                            self._fallback_remove(entries, working_memory, limit, user_id)
                    else:
                        self._fallback_remove(entries, working_memory, limit, user_id)

        return query

    async def _async_compress(self, to_compress: List[Any], working_memory: Any, user_id: int) -> None:
        """Helper to asynchronously compress and update memory."""
        combined_text = "\n".join([f"- {getattr(e, 'content', str(e))}" for e in to_compress])
        prompt = f"Please summarize the following short-term memory context into a concise summary while maintaining key facts and semantic links:\n{combined_text}"

        try:
            summary_content = await self.llm.chat_completion([
                {"role": "system", "content": "You compress memory context. Return only the summary text."},
                {"role": "user", "content": prompt}
            ], temperature=0.3)

            first = to_compress[0] if to_compress else None
            avg_importance = sum(getattr(e, 'importance', 0.5) for e in to_compress) / max(1, len(to_compress))

            summary_entry = MemoryEntry(
                content=summary_content.strip(),
                importance=avg_importance,
                emotional_state=getattr(first, 'emotional_state', None) if first else None,
                tags=list(set(t for e in to_compress if isinstance(getattr(e, 'tags', []), list) for t in getattr(e, 'tags', []))),
                user_id=getattr(first, 'user_id', None) if first else None
            )

            # Safely remove old items and add new one
            for e in to_compress:
                working_memory.remove(getattr(e, 'id'), user_id)

            await working_memory.add(summary_entry)

            logging.info(f"CompressionHookPluginV2 successfully compressed {len(to_compress)} entries.")

        except Exception as e:
            logging.error(f"CompressionHookPluginV2: LLM compression failed: {e}")

    def _fallback_remove(self, entries: List[Any], working_memory: Any, limit: int, user_id: int) -> None:
        """Fallback method to remove least important entries when LLM is unavailable."""
        entries_to_remove = len(entries) - limit + 1
        sorted_by_importance = sorted(
            entries,
            key=lambda x: getattr(x, 'importance', 0.0)
        )
        for i in range(entries_to_remove):
            entry_to_remove = sorted_by_importance[i]
            working_memory.remove(getattr(entry_to_remove, 'id'), user_id)
            logging.debug(f"CompressionHookPluginV2 fallback removed memory entry {getattr(entry_to_remove, 'id')}")

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """Called after context is retrieved."""
        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        """Called before context is written."""
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Called after context is written."""
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Called when the overall context is updated."""
        pass
