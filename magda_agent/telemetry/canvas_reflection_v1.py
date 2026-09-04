"""
OpenClaw Canvas Live Reflection Tracing V1.

Inspired by OpenClaw Canvas Live Visualization trends: Implements a real-time
reflection telemetry broadcaster that formats and transmits subconscious thoughts,
introspective state transitions, and cognitive updates to the live Canvas dashboard.
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


class ReflectionEventType(str, Enum):
    INTROSPECTION = "introspection"
    COGNITIVE_SHIFT = "cognitive_shift"
    EMOTIONAL_UPDATE = "emotional_update"
    BELIEF_REVISION = "belief_revision"
    WORKING_MEMORY_CONSOLIDATION = "working_memory_consolidation"
    GOAL_PROGRESS = "goal_progress"


@dataclass
class CanvasReflectionEventPayload:
    """Standardized event payload for the Canvas reflection layer."""

    event_id: str = field(default_factory=lambda: f"refl_{uuid.uuid4().hex[:8]}")
    event_type: str = "introspection"
    agent_id: str = "magda_primary"
    subconscious_thought: str = ""
    confidence: float = 0.9
    pad_state: Dict[str, float] = field(default_factory=lambda: {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0})
    memory_delta: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ui_layer: str = "reflection_canvas"

    def to_canvas_payload(self) -> Dict[str, Any]:
        """Convert to the standard Canvas UI telemetry envelope."""
        return {
            "type": "canvas_reflection_event",
            "layer": self.ui_layer,
            "data": {
                "event_id": self.event_id,
                "event_type": self.event_type,
                "agent_id": self.agent_id,
                "subconscious_thought": self.subconscious_thought,
                "confidence": self.confidence,
                "pad_state": self.pad_state,
                "memory_delta": self.memory_delta,
                "timestamp": self.timestamp,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CanvasReflectionTelemetryBroadcasterV1:
    """
    Canvas Live Reflection Telemetry Broadcaster V1.

    Broadcasts real-time reflection and introspection updates to the Canvas visualizer.
    """

    def __init__(
        self,
        websocket: Optional[Any] = None,
        agent_id: str = "magda_primary",
        broadcast_handler: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ):
        self.websocket = websocket
        self.agent_id = agent_id
        self.broadcast_handler = broadcast_handler
        self._history: List[CanvasReflectionEventPayload] = []

    async def broadcast_reflection_async(
        self,
        subconscious_thought: str,
        event_type: Union[ReflectionEventType, str] = ReflectionEventType.INTROSPECTION,
        confidence: float = 0.9,
        pad_state: Optional[Dict[str, float]] = None,
        memory_delta: Optional[Dict[str, Any]] = None,
    ) -> CanvasReflectionEventPayload:
        """
        Format and broadcast an introspection event asynchronously.
        """
        ev_type_str = event_type.value if isinstance(event_type, ReflectionEventType) else str(event_type)
        payload = CanvasReflectionEventPayload(
            event_type=ev_type_str,
            agent_id=self.agent_id,
            subconscious_thought=subconscious_thought,
            confidence=max(0.0, min(1.0, float(confidence))),
            pad_state=pad_state or {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0},
            memory_delta=memory_delta or {},
            timestamp=time.time(),
        )

        canvas_msg = payload.to_canvas_payload()
        self._history.append(payload)

        # 1. Dispatch over custom broadcast handler if configured
        if self.broadcast_handler:
            try:
                if inspect.iscoroutinefunction(self.broadcast_handler):
                    await self.broadcast_handler(canvas_msg)
                else:
                    self.broadcast_handler(canvas_msg)
            except Exception as e:
                logger.error(f"Error in broadcast handler: {e}")

        # 2. Dispatch over websocket if connected
        if self.websocket:
            try:
                msg_json = json.dumps(canvas_msg)
                if hasattr(self.websocket, "send_text"):
                    if inspect.iscoroutinefunction(self.websocket.send_text):
                        await self.websocket.send_text(msg_json)
                    else:
                        self.websocket.send_text(msg_json)
                elif hasattr(self.websocket, "send"):
                    if inspect.iscoroutinefunction(self.websocket.send):
                        await self.websocket.send(msg_json)
                    else:
                        self.websocket.send(msg_json)
            except Exception as e:
                logger.error(f"Failed to send reflection over websocket: {e}")

        logger.debug(f"Broadcasted Canvas reflection event [{ev_type_str}]: '{subconscious_thought[:40]}...'")
        return payload

    def broadcast_reflection(
        self,
        subconscious_thought: str,
        event_type: Union[ReflectionEventType, str] = ReflectionEventType.INTROSPECTION,
        confidence: float = 0.9,
        pad_state: Optional[Dict[str, float]] = None,
        memory_delta: Optional[Dict[str, Any]] = None,
    ) -> CanvasReflectionEventPayload:
        """Synchronous wrapper for broadcasting reflection events."""
        return asyncio.run(self.broadcast_reflection_async(
            subconscious_thought=subconscious_thought,
            event_type=event_type,
            confidence=confidence,
            pad_state=pad_state,
            memory_delta=memory_delta,
        ))

    async def broadcast_batch_async(
        self,
        events: List[CanvasReflectionEventPayload],
    ) -> int:
        """Broadcast a batch of pre-constructed reflection events."""
        sent = 0
        for ev in events:
            canvas_msg = ev.to_canvas_payload()
            self._history.append(ev)
            if self.broadcast_handler:
                if inspect.iscoroutinefunction(self.broadcast_handler):
                    await self.broadcast_handler(canvas_msg)
                else:
                    self.broadcast_handler(canvas_msg)
            if self.websocket:
                msg_json = json.dumps(canvas_msg)
                if hasattr(self.websocket, "send_text"):
                    await self.websocket.send_text(msg_json)
            sent += 1
        return sent

    def get_history(self) -> List[CanvasReflectionEventPayload]:
        """Retrieve all recorded reflection events."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear recorded reflection events."""
        self._history.clear()
