import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from magda_agent.memory.working import WorkingMemory

logger = logging.getLogger(__name__)

class CanvasMemoryStreamer:
    """
    WebSocket server for streaming live working memory changes (diffs).
    """
    def __init__(self, working_memory: WorkingMemory, interval: float = 1.0):
        self.working_memory = working_memory
        self.interval = interval
        self.active_connections: List[WebSocket] = []
        self._running = False
        self._last_state: Dict[int, List[Dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept a websocket connection and add it to the active pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Canvas client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a websocket connection from the pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Canvas client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Broadcast a message to all active websocket connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to canvas client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    def _get_current_state(self) -> Dict[int, List[Dict[str, Any]]]:
        """Extract the current state of working memory."""
        state = {}
        for user_id, entries in self.working_memory._entries_by_user.items():
            state[user_id] = [
                {
                    "id": e.id,
                    "content": e.content,
                    "timestamp": e.timestamp,
                    "importance": e.importance,
                    "tags": e.tags
                } for e in entries
            ]
        return state

    def _calculate_diff(self, current_state: Dict[int, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Calculate diffs between the last state and current state."""
        diffs = {"added": {}, "removed": {}, "updated": {}}

        # For simplicity, we diff on entry ID
        all_last_users = set(self._last_state.keys())
        all_current_users = set(current_state.keys())

        for user_id in all_last_users.union(all_current_users):
            last_entries = self._last_state.get(user_id, [])
            current_entries = current_state.get(user_id, [])

            last_dict = {e["id"]: e for e in last_entries}
            current_dict = {e["id"]: e for e in current_entries}

            added = []
            removed = []
            updated = []

            for eid, entry in current_dict.items():
                if eid not in last_dict:
                    added.append(entry)
                elif last_dict[eid] != entry:
                    updated.append(entry)

            for eid, entry in last_dict.items():
                if eid not in current_dict:
                    removed.append(entry)

            if added:
                diffs["added"][user_id] = added
            if removed:
                diffs["removed"][user_id] = removed
            if updated:
                diffs["updated"][user_id] = updated

        return diffs

    async def start_streaming(self):
        """Start the background task that periodically broadcasts the cognitive state."""
        self._running = True
        logger.info("Canvas memory streaming started.")
        self._last_state = self._get_current_state()

        while self._running:
            try:
                if self.active_connections:
                    current_state = self._get_current_state()
                    diffs = self._calculate_diff(current_state)

                    if diffs["added"] or diffs["removed"] or diffs["updated"]:
                        await self.broadcast(json.dumps({"type": "memory_diff", "diffs": diffs}))
                        self._last_state = current_state
            except Exception as e:
                logger.error(f"Error while streaming canvas memory state: {e}")
            await asyncio.sleep(self.interval)

    async def stop_streaming(self):
        """Stop the background streaming task."""
        self._running = False
        logger.info("Canvas memory streaming stopped.")
