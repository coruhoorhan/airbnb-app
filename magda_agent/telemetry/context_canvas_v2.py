"""
OpenClaw Context Engine Canvas Visualization V2.

Inspired by OpenClaw Canvas Live Visualization trends: Serializes dynamic Context
Engine state, working memory nodes, semantic clusters, token budgets, and active
retrieval weights into a structured JSON payload optimized for live Canvas UI rendering.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CanvasContextPayload:
    """Standardized Canvas UI state representation of the Context Engine."""

    canvas_id: str = field(default_factory=lambda: f"canvas_ctx_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    token_budget: Dict[str, int] = field(default_factory=lambda: {
        "used": 0, "max": 4000, "available": 4000, "threshold": 3200
    })
    working_memory_nodes: List[Dict[str, Any]] = field(default_factory=list)
    semantic_clusters: List[Dict[str, Any]] = field(default_factory=list)
    episodic_buffer_count: int = 0
    retrieval_weights: Dict[str, float] = field(default_factory=lambda: {
        "recency": 1.0, "semantic_similarity": 1.5, "importance": 1.2
    })
    active_plugins: List[str] = field(default_factory=list)
    ui_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_canvas_envelope(self) -> Dict[str, Any]:
        """Convert into standard Canvas event envelope."""
        return {
            "type": "context_engine_canvas_update",
            "layer": "context_visualization_v2",
            "timestamp": self.timestamp,
            "data": {
                "canvas_id": self.canvas_id,
                "token_budget": self.token_budget,
                "working_memory_nodes": self.working_memory_nodes,
                "semantic_clusters": self.semantic_clusters,
                "episodic_buffer_count": self.episodic_buffer_count,
                "retrieval_weights": self.retrieval_weights,
                "active_plugins": self.active_plugins,
                "ui_metadata": self.ui_metadata,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextEngineCanvasVisualizerV2:
    """
    Context Engine Canvas Visualizer V2.

    Extracts, normalizes, and serializes state from diverse Context Engine modules
    into standardized live payloads.
    """

    def __init__(self, default_max_tokens: int = 4000):
        self.default_max_tokens = default_max_tokens
        self._history: List[Dict[str, Any]] = []

    def extract_state_from_engine(self, context_engine: Any) -> CanvasContextPayload:
        """
        Extract and normalize internal state from a Context Engine instance or dictionary.
        """
        # 1. Token budget
        max_tokens = getattr(context_engine, "max_context_tokens", None) or getattr(context_engine, "max_tokens", self.default_max_tokens)
        used_tokens = 0
        if hasattr(context_engine, "get_total_tokens") and callable(context_engine.get_total_tokens):
            used_tokens = context_engine.get_total_tokens()
        elif hasattr(context_engine, "total_tokens"):
            used_tokens = getattr(context_engine, "total_tokens")
        elif isinstance(context_engine, dict) and "tokens" in context_engine:
            used_tokens = context_engine["tokens"]

        threshold = int(max_tokens * 0.8)
        available = max(0, max_tokens - used_tokens)

        token_budget = {
            "used": int(used_tokens),
            "max": int(max_tokens),
            "available": int(available),
            "threshold": threshold,
        }

        # 2. Working memory nodes
        nodes: List[Dict[str, Any]] = []
        if hasattr(context_engine, "get_entries") and callable(context_engine.get_entries):
            raw_entries = context_engine.get_entries()
            for idx, entry in enumerate(raw_entries):
                if hasattr(entry, "to_dict"):
                    nodes.append(entry.to_dict())
                elif isinstance(entry, dict):
                    nodes.append(entry)
                else:
                    nodes.append({"id": f"node_{idx}", "content": str(entry)})
        elif hasattr(context_engine, "working_memory") and isinstance(context_engine.working_memory, list):
            for idx, entry in enumerate(context_engine.working_memory):
                nodes.append(entry if isinstance(entry, dict) else {"id": f"node_{idx}", "content": str(entry)})
        elif isinstance(context_engine, dict) and "entries" in context_engine:
            nodes = list(context_engine["entries"])

        # 3. Semantic clusters
        clusters: List[Dict[str, Any]] = []
        if hasattr(context_engine, "get_clusters") and callable(context_engine.get_clusters):
            raw_c = context_engine.get_clusters()
            for c in raw_c:
                clusters.append(c.to_dict() if hasattr(c, "to_dict") else dict(c))
        elif isinstance(context_engine, dict) and "clusters" in context_engine:
            clusters = list(context_engine["clusters"])

        # 4. Episodic buffer count
        buffer_count = 0
        if hasattr(context_engine, "episodic_buffer"):
            buffer_count = len(getattr(context_engine, "episodic_buffer"))
        elif isinstance(context_engine, dict) and "episodic_buffer" in context_engine:
            buffer_count = len(context_engine["episodic_buffer"])

        # 5. Retrieval weights
        weights = {"recency": 1.0, "semantic_similarity": 1.5, "importance": 1.2}
        if hasattr(context_engine, "get_weights") and callable(context_engine.get_weights):
            weights = dict(context_engine.get_weights())
        elif isinstance(context_engine, dict) and "weights" in context_engine:
            weights = dict(context_engine["weights"])

        # 6. Active plugins
        plugins = []
        if hasattr(context_engine, "active_plugins"):
            plugins = list(getattr(context_engine, "active_plugins"))
        elif isinstance(context_engine, dict) and "plugins" in context_engine:
            plugins = list(context_engine["plugins"])

        return CanvasContextPayload(
            token_budget=token_budget,
            working_memory_nodes=nodes,
            semantic_clusters=clusters,
            episodic_buffer_count=buffer_count,
            retrieval_weights=weights,
            active_plugins=plugins,
        )

    def serialize_to_payload(self, context_engine: Any) -> Dict[str, Any]:
        """Convert engine state into standard Canvas UI payload dictionary."""
        payload_obj = self.extract_state_from_engine(context_engine)
        envelope = payload_obj.to_canvas_envelope()
        self._history.append(envelope)
        return envelope

    def serialize_to_json(self, context_engine: Any, indent: int = 2) -> str:
        """Convert engine state into JSON formatted Canvas UI envelope."""
        envelope = self.serialize_to_payload(context_engine)
        return json.dumps(envelope, indent=indent)

    def validate_canvas_schema(self, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate structure of a Canvas UI envelope."""
        errors = []
        if not isinstance(payload, dict):
            return False, ["Payload must be a JSON object."]

        if payload.get("type") != "context_engine_canvas_update":
            errors.append(f"Invalid envelope type: '{payload.get('type')}'. Expected 'context_engine_canvas_update'.")

        if payload.get("layer") != "context_visualization_v2":
            errors.append(f"Invalid layer: '{payload.get('layer')}'. Expected 'context_visualization_v2'.")

        data = payload.get("data")
        if not data or not isinstance(data, dict):
            errors.append("Payload missing 'data' object.")
        else:
            required_keys = ["token_budget", "working_memory_nodes", "semantic_clusters", "retrieval_weights"]
            for rk in required_keys:
                if rk not in data:
                    errors.append(f"Data object missing required field '{rk}'.")

        return len(errors) == 0, errors

    async def stream_to_canvas_async(
        self,
        context_engine: Any,
        broadcaster_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ) -> Dict[str, Any]:
        """Serialize state and dispatch over broadcaster coroutine."""
        payload = self.serialize_to_payload(context_engine)
        if broadcaster_fn:
            if inspect.iscoroutinefunction(broadcaster_fn):
                await broadcaster_fn(payload)
            else:
                broadcaster_fn(payload)
        return payload
