import time
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin
from magda_agent.safety.audit_trail import AuditTrail

class MetricPlugin(ContextPlugin):
    """
    A ContextEngine plugin that measures token usage and latency of memory retrievals,
    outputting to the AuditTrail.
    """

    def __init__(self, audit_trail: Optional[AuditTrail] = None):
        """
        Initialize the MetricPlugin.

        Args:
            audit_trail: The AuditTrail instance to log to. If None, a new instance is created.
        """
        self.audit_trail = audit_trail or AuditTrail()
        # Dictionary to store the start time for a query using user_id + query as a key heuristic
        self._retrieval_starts: Dict[str, float] = {}

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass

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
        Called before context is retrieved.
        Records the start time of the retrieval operation.
        """
        start_time = time.time()
        # Create a unique key for this retrieval operation
        key = f"{user_id}_{query}"
        self._retrieval_starts[key] = start_time
        return query

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of tokens based on word count.
        Using standard heuristic of 1 word ~ 1.33 tokens (or words / 0.75).
        """
        words = len(text.split())
        return int(words / 0.75)

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Called after context is retrieved.
        Calculates latency and estimates token usage, logging the metrics to AuditTrail.
        """
        end_time = time.time()
        key = f"{user_id}_{query}"
        start_time = self._retrieval_starts.pop(key, None)

        latency = 0.0
        if start_time is not None:
            latency = end_time - start_time

        # Estimate tokens based on the retrieved context string
        context_str = "\n".join([str(item) for item in context])
        token_count = self._estimate_tokens(context_str)

        # Log to AuditTrail
        self.audit_trail.log_call(
            tool_name="context_retrieval",
            kwargs={
                "query": query,
                "user_id": user_id,
                "estimated_tokens": token_count,
            },
            why="ContextEngine retrieval metric logging",
            result=f"Retrieved {len(context)} items",
            duration=latency,
        )

        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        """Called before context is written. Can modify the context."""
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Called after context is written."""
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Called when the overall context is updated."""
        pass
