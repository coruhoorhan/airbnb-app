import asyncio
import json
import logging
from typing import Set, Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve


logger = logging.getLogger(__name__)


class CanvasLiveVisualizer:
    """
    A real-time canvas visualization component using WebSockets.
    Monitors the agent's internal state and OpenClaw-RL PAD state shifts,
    mirroring OpenClaw's Live Canvas architecture.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """
        Initializes the CanvasLiveVisualizer.

        Args:
            host: The host address to bind the WebSocket server to.
            port: The port to bind the WebSocket server to.
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server: Optional[Any] = None

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handles incoming WebSocket connections and registers them.

        Args:
            websocket: The connected WebSocket client.
        """
        self.clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}")
        try:
            # Keep connection open and wait for it to close
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            logger.info(f"Client disconnected: {websocket.remote_address}")

    async def start(self) -> None:
        """
        Starts the WebSocket server.
        """
        logger.info(f"Starting CanvasLiveVisualizer server on {self.host}:{self.port}")
        self._server = await serve(self._handler, self.host, self.port)

    async def stop(self) -> None:
        """
        Stops the WebSocket server.
        """
        if self._server:
            logger.info("Stopping CanvasLiveVisualizer server")
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Close all active client connections
        if self.clients:
            await asyncio.gather(*(client.close() for client in self.clients))
            self.clients.clear()

    async def broadcast_state(self, state: Dict[str, Any], pad_shifts: Dict[str, float]) -> None:
        """
        Broadcasts the agent's internal state and PAD shifts to all connected clients.

        Args:
            state: A dictionary representing the agent's current internal state.
            pad_shifts: A dictionary representing PAD (Pleasure, Arousal, Dominance) state shifts.
        """
        if not self.clients:
            return

        payload = {
            "type": "state_update",
            "data": {
                "state": state,
                "pad_shifts": pad_shifts
            }
        }

        try:
            message = json.dumps(payload)
        except TypeError as e:
            logger.error(f"Failed to serialize broadcast payload: {e}")
            return

        # Broadcast the message to all connected clients
        # Use asyncio.gather for concurrent broadcasting
        tasks = [
            asyncio.create_task(client.send(message))
            for client in self.clients
            if not client.closed
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
