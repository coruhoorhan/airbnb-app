import logging
import json
import time
import uuid
from typing import Any, Dict, Optional

class CanvasMemoryTelemetryV5:
    """
    An export module to broadcast episodic memory consolidation events
    dynamically to a live dashboard, inspired by OpenClaw Canvas.
    """

    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the CanvasMemoryTelemetryV5.

        Args:
            websocket (Optional[Any]): An open asynchronous websocket connection.
        """
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    async def broadcast_consolidation_event(self, user_id: int, memories: list[Dict[str, Any]]) -> None:
        """
        Broadcast an episodic memory consolidation event to the connected Canvas client.

        Args:
            user_id (int): The ID of the user whose memories are being consolidated.
            memories (list[Dict[str, Any]]): A list of memory dictionaries being consolidated.
        """
        payload = {
            "type": "episodic_memory_consolidation",
            "event_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "data": {
                "user_id": user_id,
                "consolidated_count": len(memories),
                "memories": memories
            }
        }
        await self._broadcast(payload)

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        """
        Helper method to format and send JSON payload over the websocket.

        Args:
            payload (Dict[str, Any]): The payload of the event.
        """
        if self.websocket is None:
            self.logger.debug(f"Skipping broadcast for {payload.get('type')} - no websocket connected.")
            return

        try:
            message = json.dumps(payload, default=str)
            # Support send_text (standard FastAPI style used in tests)
            if hasattr(self.websocket, "send_text"):
                await self.websocket.send_text(message)
            else:
                # Fallback to standard send if send_text is not present
                await self.websocket.send(message)
            self.logger.debug(f"Successfully broadcasted {payload.get('type')} event.")
        except Exception as e:
            self.logger.error(f"Failed to broadcast {payload.get('type')} event: {e}")
