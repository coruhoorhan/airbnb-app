import asyncio
import json
import logging
from typing import Any, Dict, Optional


class CanvasTelemetryStreamerV9:
    """
    A websocket telemetry streamer that broadcasts agent memory state
    and planner steps in real-time to an external Canvas client.
    """

    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the CanvasTelemetryStreamerV9.

        Args:
            websocket (Optional[Any]): An open asynchronous websocket connection.
        """
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    async def broadcast_memory_state(self, memory_state: Dict[str, Any]) -> None:
        """
        Broadcast the agent's memory state to the connected Canvas client.

        Args:
            memory_state (Dict[str, Any]): The memory state to broadcast.
        """
        await self._broadcast_event("memory_state_update", memory_state)

    async def broadcast_planner_step(self, planner_step: Dict[str, Any]) -> None:
        """
        Broadcast a planner step to the connected Canvas client.

        Args:
            planner_step (Dict[str, Any]): The planner step to broadcast.
        """
        await self._broadcast_event("planner_step_update", planner_step)

    async def _broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Helper method to format and send events over the websocket.

        Args:
            event_type (str): The type of the event.
            data (Dict[str, Any]): The payload of the event.
        """
        if self.websocket is None:
            self.logger.debug(f"Skipping broadcast for {event_type} - no websocket connected.")
            return

        payload = {
            "type": event_type,
            "data": data
        }

        try:
            message = json.dumps(payload)
            await self.websocket.send_text(message)
            self.logger.debug(f"Successfully broadcasted {event_type} event.")
        except Exception as e:
            self.logger.error(f"Failed to broadcast {event_type} event: {e}")
