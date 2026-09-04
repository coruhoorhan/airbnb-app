import logging
import json
import time
from typing import Any, Dict, Optional

class RLDashboardV8:
    """
    An OpenClaw Canvas-inspired telemetry hook for streaming online RL metric
    shifts (PAD changes) to an external dashboard via WebSockets.
    """

    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the RLDashboardV8.

        Args:
            websocket (Optional[Any]): An open asynchronous websocket connection.
        """
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    async def broadcast_pad_shift(self, user_id: int, pad_shift: Dict[str, float]) -> None:
        """
        Broadcast an online RL PAD metric shift to the connected dashboard.

        Args:
            user_id (int): The ID of the user triggering the PAD shift.
            pad_shift (Dict[str, float]): A dictionary containing 'pleasure', 'arousal', and 'dominance' float values.
        """
        payload = {
            "type": "rl_pad_shift",
            "timestamp": time.time(),
            "data": {
                "user_id": user_id,
                "pad_shift": pad_shift
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
            message = json.dumps(payload)
            # Support send_text (standard FastAPI style used in tests)
            if hasattr(self.websocket, "send_text"):
                await self.websocket.send_text(message)
            else:
                # Fallback to standard send if send_text is not present
                await self.websocket.send(message)
            self.logger.debug(f"Successfully broadcasted {payload.get('type')} event.")
        except Exception as e:
            self.logger.error(f"Failed to broadcast {payload.get('type')} event: {e}")
