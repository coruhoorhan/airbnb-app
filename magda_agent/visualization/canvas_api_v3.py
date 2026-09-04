"""
Canvas API v3

Implements API endpoints for streaming the OpenClaw Semantic Memory Canvas state.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class SemanticCanvasServerV3:
    """
    WebSocket server for streaming live visualization of semantic memory relations.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a websocket connection and add it to the active pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Semantic canvas client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a websocket connection from the pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Semantic canvas client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_semantic_state(self, state_json: str) -> None:
        """Broadcast a semantic state message to all active websocket connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(state_json)
            except Exception as e:
                logger.error(f"Failed to send semantic state to canvas client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

def get_canvas_v3_router(canvas_server: SemanticCanvasServerV3, token: Optional[str] = None) -> APIRouter:
    """
    Returns an APIRouter providing endpoints for live semantic canvas streaming.

    Args:
        canvas_server (SemanticCanvasServerV3): The initialized canvas server that broadcasts states.
        token (Optional[str]): Optional auth token for basic websocket authentication.

    Returns:
        APIRouter: The FastAPI router containing canvas V3 endpoints.
    """
    router = APIRouter(prefix="/api/v3/canvas", tags=["Canvas V3 Semantic"])

    @router.websocket("/semantic-stream")
    async def stream_canvas_v3_semantic(websocket: WebSocket, auth_token: Optional[str] = None) -> None:
        """
        WebSocket endpoint for streaming semantic memory updates to connected clients.
        """
        if token and auth_token != token:
            await websocket.close(code=1008)
            return

        await canvas_server.connect(websocket)
        try:
            while True:
                # Keep the connection open and wait for client messages
                _data = await websocket.receive_text()
        except WebSocketDisconnect:
            canvas_server.disconnect(websocket)
        except Exception as e:
            logger.error(f"Semantic canvas stream error: {e}")
            canvas_server.disconnect(websocket)

    return router
