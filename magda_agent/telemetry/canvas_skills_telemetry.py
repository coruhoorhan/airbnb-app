import json
import logging
from typing import Any, Dict, Optional

class CanvasSkillsTelemetry:
    """
    A telemetry streamer that broadcasts skill execution lifecycle events
    (start, success, fail) to an external Canvas client via WebSockets.
    """

    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the CanvasSkillsTelemetry.

        Args:
            websocket (Optional[Any]): An open asynchronous websocket connection.
        """
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    async def broadcast_skill_start(self, skill_name: str, kwargs: Dict[str, Any]) -> None:
        """
        Broadcast that a skill execution has started.

        Args:
            skill_name (str): The name of the skill.
            kwargs (Dict[str, Any]): The arguments passed to the skill.
        """
        payload = {
            "skill_name": skill_name,
            "kwargs": kwargs,
            "status": "start"
        }
        await self._broadcast_event("skill_start", payload)

    async def broadcast_skill_success(self, skill_name: str, result: Any, duration_ms: float) -> None:
        """
        Broadcast that a skill execution was successful.

        Args:
            skill_name (str): The name of the skill.
            result (Any): The result returned by the skill.
            duration_ms (float): Execution duration in milliseconds.
        """
        payload = {
            "skill_name": skill_name,
            "result": str(result),  # convert to string to ensure json serialization
            "duration_ms": duration_ms,
            "status": "success"
        }
        await self._broadcast_event("skill_success", payload)

    async def broadcast_skill_fail(self, skill_name: str, error: str, duration_ms: float) -> None:
        """
        Broadcast that a skill execution has failed.

        Args:
            skill_name (str): The name of the skill.
            error (str): The error message.
            duration_ms (float): Execution duration in milliseconds before failure.
        """
        payload = {
            "skill_name": skill_name,
            "error": error,
            "duration_ms": duration_ms,
            "status": "fail"
        }
        await self._broadcast_event("skill_fail", payload)

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
