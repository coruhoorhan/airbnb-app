import time
from typing import Any, Dict, List, Optional
from magda_agent.memory.context_engine import ContextPlugin
from magda_agent.safety.audit_trail import AuditTrail

class MetricPluginV2(ContextPlugin):
    """
    A ContextEngine plugin that measures token usage and latency of memory retrievals,
    specifically tracking token length and latency during the assemble phase,
    outputting to the AuditTrail.
    """

    def __init__(self, audit_trail: Optional[AuditTrail] = None):
        """
        Initialize the MetricPluginV2.

        Args:
            audit_trail: The AuditTrail instance to log to. If None, a new instance is created.
        """
        self.audit_trail = audit_trail or AuditTrail()

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process incoming content before it is stored or used."""
        return content

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of tokens based on word count.
        Using standard heuristic of 1 word ~ 1.33 tokens (or words / 0.75).
        """
        words = len(text.split())
        return int(words / 0.75)

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """
        Assemble the context string from retrieved items for the LLM.
        Tracks the token length and retrieval latency during this phase.
        """
        start_time = time.time()

        assembled_str = "\n".join([str(item) for item in context_items])

        end_time = time.time()
        latency = end_time - start_time

        token_count = self._estimate_tokens(assembled_str)

        # Log to AuditTrail
        self.audit_trail.log_call(
            tool_name="context_assemble",
            kwargs={
                "metadata": metadata,
                "estimated_tokens": token_count,
            },
            why="ContextEngine assemble metric logging",
            result=f"Assembled {len(context_items)} items",
            duration=latency,
        )

        return assembled_str

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact or summarize the context when limits are reached."""
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """Called before context is retrieved."""
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """Called after context is retrieved."""
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
