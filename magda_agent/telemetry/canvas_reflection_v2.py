"""
OpenClaw Canvas Live Reflection Tracing V2.

Inspired by OpenClaw Canvas Live Visualization trends: Implements a real-time
V2 reflection telemetry exporter that serializes internal monologue, counterfactual
reasoning, attention focus, and emotional PAD vectors into structured live payloads
for the Canvas UI.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class ReflectionTypeV2(str, Enum):
    INTERNAL_MONOLOGUE = "internal_monologue"
    BELIEF_UPDATE = "belief_update"
    PAD_SHIFT = "pad_shift"
    SUBAGENT_REFLECTION = "subagent_reflection"
    COUNTERFACTUAL_REASONING = "counterfactual_reasoning"
    PLAN_REEVALUATION = "plan_reevaluation"


@dataclass
class CanvasReflectionEventV2:
    """Represents a V2 rich reflection event ready for live Canvas streaming."""

    event_id: str = field(default_factory=lambda: f"refl_v2_{uuid.uuid4().hex[:8]}")
    reflection_type: str = ReflectionTypeV2.INTERNAL_MONOLOGUE.value
    agent_id: str = "magda_primary"
    content: str = ""
    sentiment_score: float = 0.0
    pad_vector: Dict[str, float] = field(default_factory=lambda: {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0})
    cognitive_load: float = 0.5  # 0.0 to 1.0
    attention_focus: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    ui_channel: str = "canvas_reflection_v2"

    def to_canvas_v2_envelope(self) -> Dict[str, Any]:
        """Convert into standard Canvas V2 UI telemetry envelope."""
        return {
            "type": "canvas_reflection_event_v2",
            "channel": self.ui_channel,
            "timestamp": self.timestamp,
            "data": {
                "event_id": self.event_id,
                "reflection_type": self.reflection_type,
                "agent_id": self.agent_id,
                "content": self.content,
                "sentiment_score": round(self.sentiment_score, 4),
                "pad_vector": self.pad_vector,
                "cognitive_load": round(self.cognitive_load, 2),
                "attention_focus": self.attention_focus,
                "timestamp": self.timestamp,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CanvasReflectionExporterV2:
    """
    Canvas Live Reflection Exporter V2.

    Formats and dispatches V2 reflection telemetry to connected Canvas WebSocket clients
    or registered stream handlers.
    """

    def __init__(
        self,
        websocket: Optional[Any] = None,
        agent_id: str = "magda_primary",
        dispatch_handler: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        ui_channel: str = "canvas_reflection_v2",
    ):
        self.websocket = websocket
        self.agent_id = agent_id
        self.dispatch_handler = dispatch_handler
        self.ui_channel = ui_channel
        self._exported_events: List[CanvasReflectionEventV2] = []

    async def export_reflection_async(
        self,
        content: str,
        reflection_type: Union[ReflectionTypeV2, str] = ReflectionTypeV2.INTERNAL_MONOLOGUE,
        sentiment_score: float = 0.0,
        pad_vector: Optional[Dict[str, float]] = None,
        cognitive_load: float = 0.5,
        attention_focus: Optional[List[str]] = None,
    ) -> CanvasReflectionEventV2:
        """
        Create and export a V2 reflection event asynchronously.
        """
        refl_str = reflection_type.value if isinstance(reflection_type, ReflectionTypeV2) else str(reflection_type)

        event = CanvasReflectionEventV2(
            reflection_type=refl_str,
            agent_id=self.agent_id,
            content=content,
            sentiment_score=max(-1.0, min(1.0, float(sentiment_score))),
            pad_vector=pad_vector or {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0},
            cognitive_load=max(0.0, min(1.0, float(cognitive_load))),
            attention_focus=list(attention_focus or []),
            timestamp=time.time(),
            ui_channel=self.ui_channel,
        )

        envelope = event.to_canvas_v2_envelope()
        self._exported_events.append(event)

        # 1. Custom async dispatch callback
        if self.dispatch_handler:
            try:
                if inspect.iscoroutinefunction(self.dispatch_handler):
                    await self.dispatch_handler(envelope)
                else:
                    self.dispatch_handler(envelope)
            except Exception as ex:
                logger.error(f"Error in Canvas V2 dispatch handler: {ex}")

        # 2. WebSocket streaming
        if self.websocket:
            try:
                msg = json.dumps(envelope)
                if hasattr(self.websocket, "send_text"):
                    if inspect.iscoroutinefunction(self.websocket.send_text):
                        await self.websocket.send_text(msg)
                    else:
                        self.websocket.send_text(msg)
                elif hasattr(self.websocket, "send"):
                    if inspect.iscoroutinefunction(self.websocket.send):
                        await self.websocket.send(msg)
                    else:
                        self.websocket.send(msg)
            except Exception as ex:
                logger.error(f"Failed to stream reflection over websocket: {ex}")

        return event

    def export_reflection(
        self,
        content: str,
        reflection_type: Union[ReflectionTypeV2, str] = ReflectionTypeV2.INTERNAL_MONOLOGUE,
        sentiment_score: float = 0.0,
        pad_vector: Optional[Dict[str, float]] = None,
        cognitive_load: float = 0.5,
        attention_focus: Optional[List[str]] = None,
    ) -> CanvasReflectionEventV2:
        """Synchronous wrapper for exporting reflection events."""
        return asyncio.run(self.export_reflection_async(
            content=content,
            reflection_type=reflection_type,
            sentiment_score=sentiment_score,
            pad_vector=pad_vector,
            cognitive_load=cognitive_load,
            attention_focus=attention_focus,
        ))

    async def stream_batch_async(
        self,
        events: List[CanvasReflectionEventV2],
    ) -> int:
        """Stream multiple reflection events in batch."""
        count = 0
        for ev in events:
            envelope = ev.to_canvas_v2_envelope()
            self._exported_events.append(ev)
            if self.dispatch_handler:
                if inspect.iscoroutinefunction(self.dispatch_handler):
                    await self.dispatch_handler(envelope)
                else:
                    self.dispatch_handler(envelope)
            if self.websocket and hasattr(self.websocket, "send_text"):
                await self.websocket.send_text(json.dumps(envelope))
            count += 1
        return count

    def get_exported_events(self) -> List[CanvasReflectionEventV2]:
        """Retrieve copy of all exported reflection events."""
        return list(self._exported_events)

    def clear_history(self) -> None:
        """Clear exported events history."""
        self._exported_events.clear()
