"""
OpenClaw RL Canvas Skills Metrics V2

This module provides a WebSocket handler to broadcast dynamic skill adjustments
and learning metrics over websockets for real-time visualization.
"""

import asyncio
import json
import time
from typing import Dict, Any, List

class CanvasSkillsMetricsV2:
    """
    Handles streaming of skill metrics and adjustments over WebSockets.
    """

    def __init__(self):
        """Initializes the metrics visualizer state."""
        self.connected_clients: List[Any] = []

    async def register_client(self, websocket: Any) -> None:
        """
        Registers a new WebSocket client.

        Args:
            websocket: The websocket connection to register.
        """
        self.connected_clients.append(websocket)

    async def unregister_client(self, websocket: Any) -> None:
        """
        Unregisters a WebSocket client.

        Args:
            websocket: The websocket connection to unregister.
        """
        if websocket in self.connected_clients:
            self.connected_clients.remove(websocket)

    def format_payload(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Formats a metric payload into a JSON string with timestamp.

        Args:
            event_type: The type of event (e.g., 'skill_adjustment', 'learning_metric').
            data: The core payload data.

        Returns:
            str: JSON formatted string payload.
        """
        payload = {
            "timestamp": time.time(),
            "type": event_type,
            "data": data
        }
        return json.dumps(payload)

    async def broadcast_metric(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcasts a metric event to all connected WebSocket clients.

        Args:
            event_type: The type of metric event.
            data: The metric data payload.
        """
        if not self.connected_clients:
            return

        payload = self.format_payload(event_type, data)

        tasks = []
        for client in self.connected_clients:
            # Assuming client has a send method compatible with asyncio WebSockets
            tasks.append(client.send(payload))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_connection(self, websocket: Any, path: str = "/") -> None:
        """
        An async WebSocket handler that receives metrics and forwards them.

        Args:
            websocket: The WebSocket connection.
            path: The connection path.
        """
        await self.register_client(websocket)
        try:
            # Keep connection open and listen for incoming messages if necessary.
            # Here we just wait for disconnection.
            async for _ in websocket:
                pass
        except Exception as e:
            # Handle disconnection
            pass
        finally:
            await self.unregister_client(websocket)
