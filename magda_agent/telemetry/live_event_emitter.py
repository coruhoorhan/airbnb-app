import logging
import json
import time
from typing import Any, Dict, Optional

class LiveEventEmitter:
    """
    A unified event emitter that aggregates agent state changes
    (planner, memory, execution) and streams them via WebSocket.
    """
    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the LiveEventEmitter with an optional websocket.
        """
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    def set_websocket(self, websocket: Any) -> None:
        """
        Dynamically update or set the websocket connection.
        """
        self.websocket = websocket

    async def emit_planner_change(self, data: Dict[str, Any]) -> None:
        """
        Emit a planner-related state change.
        """
        await self.emit_state_change("planner", data)

    async def emit_memory_change(self, data: Dict[str, Any]) -> None:
        """
        Emit a memory-related state change.
        """
        await self.emit_state_change("memory", data)

    async def emit_execution_change(self, data: Dict[str, Any]) -> None:
        """
        Emit an execution-related state change.
        """
        await self.emit_state_change("execution", data)

    async def emit_state_change(self, category: str, data: Dict[str, Any]) -> None:
        """
        Emit a state change event for the given category with timestamp.
        """
        if self.websocket is None:
            self.logger.debug(f"Skipping emit for {category} - no websocket connected.")
            return

        payload = {
            "type": f"{category}_change",
            "category": category,
            "timestamp": time.time(),
            "data": data
        }

        try:
            message = json.dumps(payload)
            # Support send_text (standard FastAPI style used in tests)
            if hasattr(self.websocket, "send_text"):
                await self.websocket.send_text(message)
            else:
                # Fallback to standard send if send_text is not present
                await self.websocket.send(message)
            self.logger.debug(f"Successfully emitted {category} event.")
        except Exception as e:
            self.logger.error(f"Failed to emit {category} event: {e}")
