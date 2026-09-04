import logging
from typing import Optional, Dict, Any, List
from magda_agent.memory.episodic import EpisodicMemory
from magda_agent.memory.semantic import SemanticMemory
from magda_agent.llm_client import LLMClient

class EpisodicSemanticMemoryManagerV2:
    """
    EpisodicSemanticMemoryManagerV2 handles routing information to strict separation between Episodic
    (event-based) and Semantic (knowledge-based) memory stores.
    """

    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the memory manager.

        Args:
            episodic: The episodic memory instance.
            semantic: The semantic memory instance.
            llm_client: Optional LLMClient to help route memories accurately.
        """
        self.episodic = episodic
        self.semantic = semantic
        self.llm_client = llm_client
        logging.info("Initialized EpisodicSemanticMemoryManagerV2")

    async def route_and_store(self, text: str, metadata: Optional[Dict[str, Any]] = None, user_id: Optional[int] = None) -> str:
        """
        Route the text to either episodic or semantic memory based on its content, and store it.

        Args:
            text: The information to be stored.
            metadata: Optional metadata to attach to the memory.
            user_id: Optional user identifier.

        Returns:
            str: The name of the store used ('episodic' or 'semantic').
        """
        store_type = await self._determine_store(text)

        if store_type == "semantic":
            self.semantic.store_fact(text=text, metadata=metadata, user_id=user_id)
            logging.debug(f"Routed to Semantic memory: {text[:30]}...")
            return "semantic"
        else:
            self.episodic.store_event(text=text, metadata=metadata, user_id=user_id)
            logging.debug(f"Routed to Episodic memory: {text[:30]}...")
            return "episodic"

    async def _determine_store(self, text: str) -> str:
        """
        Internal method to determine if a text is an event (episodic) or a fact (semantic).

        Args:
            text: The text to classify.

        Returns:
            str: 'episodic' or 'semantic'.
        """
        if self.llm_client:
            prompt = f"Determine if the following text is a specific event (return 'episodic') or a stable fact/knowledge (return 'semantic'). Respond with only one word: 'episodic' or 'semantic'.\n\nText: {text}"
            try:
                response = await self.llm_client.generate(prompt)
                response = response.strip().lower()
                if "semantic" in response:
                    return "semantic"
                return "episodic"
            except Exception as e:
                logging.error(f"LLM routing failed, falling back to heuristics: {e}")

        # Simple heuristics fallback
        text_lower = text.lower()
        if "yesterday" in text_lower or "today" in text_lower or "just now" in text_lower or "happened" in text_lower or "said" in text_lower or "did" in text_lower:
            return "episodic"

        if "is a" in text_lower or "are" in text_lower or "fact" in text_lower or "always" in text_lower or "means" in text_lower or "prefer" in text_lower:
             return "semantic"

        # Default to episodic if ambiguous
        return "episodic"

    def retrieve_episodic(self, query: str, top_k: int = 5, user_id: Optional[int] = None) -> List[str]:
        """
        Retrieve relevant events from the episodic memory store.

        Args:
            query: The semantic search query.
            top_k: Number of results to return.
            user_id: Optional user identifier to filter by.

        Returns:
            List[str]: A list of relevant events.
        """
        return self.episodic.recall_events(query=query, top_k=top_k, user_id=user_id)

    def retrieve_semantic(self, query: str, top_k: int = 5, user_id: Optional[int] = None) -> List[str]:
        """
        Retrieve relevant facts from the semantic memory store.

        Args:
            query: The semantic search query.
            top_k: Number of results to return.
            user_id: Optional user identifier to filter by.

        Returns:
            List[str]: A list of relevant facts.
        """
        return self.semantic.recall_facts(query=query, top_k=top_k, user_id=user_id)
