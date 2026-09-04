import logging
import time
from typing import Dict, List, Any, Optional
from magda_agent.tracing.tracer import ThoughtChainTracer

logger = logging.getLogger(__name__)

class CanvasLoggerPluginV3:
    """
    An enhanced ContextEngine plugin (V3) designed for the OpenClaw-inspired
    live Canvas UI. It captures and logs real-time agent thought processes
    and context lifecycle events.
    """

    def __init__(self, tracer: Optional[ThoughtChainTracer] = None) -> None:
        """
        Initializes CanvasLoggerPluginV3.

        Args:
            tracer: Optional ThoughtChainTracer to integrate and synchronize trace steps.
        """
        self.tracer = tracer
        self.logs: List[Dict[str, Any]] = []

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin and log the config."""
        event = {
            "timestamp": time.time(),
            "event": "bootstrap",
            "category": "bootstrap",
            "config": config
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.bootstrap: {event}")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Log incoming content being ingested."""
        event = {
            "timestamp": time.time(),
            "event": "ingest",
            "category": "ingest",
            "content": content,
            "metadata": metadata
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.ingest: {event}")
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Log the context assembly event."""
        event = {
            "timestamp": time.time(),
            "event": "assemble",
            "category": "assemble",
            "item_count": len(context_items),
            "metadata": metadata
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.assemble: {event}")
        return "\n".join([str(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Log context compaction/summarization events."""
        event = {
            "timestamp": time.time(),
            "event": "compact",
            "category": "compaction",
            "item_count_before": len(context_items),
            "metadata": metadata
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.compact: {event}")
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """Log pre-retrieval query state."""
        event = {
            "timestamp": time.time(),
            "event": "before_retrieval",
            "category": "retrieval",
            "query": query,
            "user_id": user_id
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.before_retrieval: {event}")
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """Log retrieved items and context length."""
        event = {
            "timestamp": time.time(),
            "event": "after_retrieval",
            "category": "retrieval",
            "context_length": len(context),
            "query": query,
            "user_id": user_id
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.after_retrieval: {event}")
        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        """Log actions happening before memory/context is written."""
        event = {
            "timestamp": time.time(),
            "event": "before_write",
            "category": "write",
            "context": str(context),
            "user_id": user_id
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.before_write: {event}")
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Log post-write state."""
        event = {
            "timestamp": time.time(),
            "event": "after_write",
            "category": "write",
            "context": str(context),
            "user_id": user_id
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.after_write: {event}")

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Log context update events."""
        event = {
            "timestamp": time.time(),
            "event": "on_context_update",
            "category": "on_context_update",
            "context": str(new_context),
            "user_id": user_id
        }
        self.logs.append(event)
        logger.debug(f"CanvasLoggerPluginV3.on_context_update: {event}")

    def log_thought_step(self, step_name: str, data: Any = None, category: str = "thought", user_id: Optional[Any] = None) -> None:
        """
        Manually log a structured agent thought process step.

        Args:
            step_name: Name/description of the thought/action step.
            data: Additional payload or context data.
            category: Thought process category (e.g., planning, evaluation, reasoning).
            user_id: Optional user identifier.
        """
        event = {
            "timestamp": time.time(),
            "event": "thought_step",
            "step": step_name,
            "category": category,
            "data": data,
        }
        if user_id is not None:
            event["user_id"] = user_id
        self.logs.append(event)

        # Sync back to the tracer if configured
        if self.tracer is not None:
            self.tracer.add_step(step_name, data)

        logger.info(f"CanvasLoggerPluginV3.log_thought_step: {event}")

    def get_logs(self, include_tracer: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieves all captured logs.

        Args:
            include_tracer: Whether to incorporate trace steps from the integrated ThoughtChainTracer.

        Returns:
            List[Dict[str, Any]]: Chronologically merged list of logs.
        """
        all_logs = list(self.logs)

        if include_tracer and self.tracer is not None:
            tracer_steps = self.tracer.get_trace()
            for step in tracer_steps:
                # Avoid duplicates if already recorded
                # Convert step to visualizer format
                converted_step = {
                    "timestamp": step.get("timestamp", time.time()),
                    "event": "thought_step",
                    "step": step.get("step"),
                    "category": "thought_tracer",
                    "data": step.get("data")
                }
                all_logs.append(converted_step)

        # Sort combined logs chronologically by timestamp
        all_logs.sort(key=lambda x: x.get("timestamp", 0.0))
        return all_logs

    def clear_logs(self, clear_tracer: bool = False) -> None:
        """
        Clears the stored logs.

        Args:
            clear_tracer: Whether to also clear the integrated ThoughtChainTracer's context trace.
        """
        self.logs.clear()
        if clear_tracer and self.tracer is not None:
            self.tracer.clear()
        logger.debug("CanvasLoggerPluginV3 logs cleared.")

    def get_formatted_thought_trace(self) -> Dict[str, Any]:
        """
        Formats the current logs into a structured thought process trace object
        ready for live Canvas UI consumption.
        """
        logs = self.get_logs(include_tracer=True)
        return {
            "schema_version": "openclaw_canvas_v3",
            "timestamp": time.time(),
            "trace_length": len(logs),
            "steps": [
                {
                    "timestamp": log.get("timestamp"),
                    "category": log.get("category", "thought"),
                    "event": log.get("event"),
                    "step": log.get("step") or log.get("event"),
                    "details": log.get("data") or log.get("config") or log.get("content") or log.get("context") or {}
                }
                for log in logs
            ]
        }
