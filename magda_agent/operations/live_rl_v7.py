import asyncio
import json
import logging
from typing import Set, Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve

logger = logging.getLogger(__name__)

class OpenClawRLCanvasMetricsV7:
    """
    Live canvas updates for RL openclaw metrics V7.
    Provides a WebSocket server to broadcast PAD shifts and telemetry events
    in JSON format to connected visualization clients.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8766):
        """
        Initializes the OpenClawRLCanvasMetricsV7.

        Args:
            host (str): The host address to bind the WebSocket server to.
            port (int): The port to bind the WebSocket server to.
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server: Optional[Any] = None

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handles incoming WebSocket connections and registers them.

        Args:
            websocket (WebSocketServerProtocol): The connected WebSocket client.
        """
        self.clients.add(websocket)
        logger.info(f"Client connected to RL Canvas Metrics V7: {websocket.remote_address}")
        try:
            # Drain any unexpected incoming messages and wait for connection close
            async for _ in websocket:
                pass
        finally:
            self.clients.remove(websocket)
            logger.info(f"Client disconnected from RL Canvas Metrics V7: {websocket.remote_address}")

    async def start(self) -> None:
        """
        Starts the WebSocket server for RL telemetry broadcasting.
        """
        logger.info(f"Starting OpenClawRLCanvasMetricsV7 server on {self.host}:{self.port}")
        self._server = await serve(self._handler, self.host, self.port)

    async def stop(self) -> None:
        """
        Stops the WebSocket server and closes all client connections.
        """
        if self._server:
            logger.info("Stopping OpenClawRLCanvasMetricsV7 server")
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self.clients:
            await asyncio.gather(*(client.close() for client in self.clients))
            self.clients.clear()

    async def broadcast_pad_shift(self, pleasure: float, arousal: float, dominance: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Broadcasts a PAD (Pleasure, Arousal, Dominance) shift event to all connected clients.

        Args:
            pleasure (float): The pleasure shift value.
            arousal (float): The arousal shift value.
            dominance (float): The dominance shift value.
            metadata (Optional[Dict[str, Any]]): Optional metadata associated with the shift.
        """
        event_data = {
            "pleasure": pleasure,
            "arousal": arousal,
            "dominance": dominance
        }
        if metadata:
            event_data["metadata"] = metadata

        await self.broadcast_telemetry("pad_shift", event_data)

    async def broadcast_telemetry(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Formats telemetry events to JSON and broadcasts them to all connected clients.

        Args:
            event_type (str): The type of the telemetry event.
            data (Dict[str, Any]): The data associated with the event.
        """
        if not self.clients:
            return

        payload = {
            "type": event_type,
            "data": data
        }

        try:
            message = json.dumps(payload)
        except TypeError as e:
            logger.error(f"Failed to serialize broadcast payload: {e}")
            return

        tasks = [
            asyncio.create_task(client.send(message))
            for client in self.clients
            if not client.closed
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
