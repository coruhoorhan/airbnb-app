import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class CanvasMemoryMetricsExporterV8:
    """
    Handles tracking, aggregation, and formatting of memory consolidation metrics
    for live Canvas UI visualization, inspired by OpenClaw trends.
    """

    def __init__(self, max_events: int = 50) -> None:
        """
        Initializes the CanvasMemoryMetricsExporterV8.

        Args:
            max_events (int): Maximum number of recent consolidation events to retain.
        """
        self.events: List[Dict[str, Any]] = []
        self.max_events = max_events

    def record_consolidation(
        self,
        user_id: Union[int, str],
        memories: List[Dict[str, Any]],
        importance_scores: Optional[List[float]] = None,
        compression_ratio: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records a single memory consolidation event and calculates metrics.

        Args:
            user_id (Union[int, str]): The user or session ID associated with the memories.
            memories (List[Dict[str, Any]]): The list of memory objects being consolidated.
            importance_scores (Optional[List[float]]): Optional importance scores for each memory.
            compression_ratio (float): Ratio of consolidated size/tokens to raw size/tokens.
            metadata (Optional[Dict[str, Any]]): Additional contextual metadata.

        Returns:
            Dict[str, Any]: The recorded event entry with calculated metrics.
        """
        scores = importance_scores or []
        avg_importance = (
            sum(scores) / len(scores) if scores else 0.0
        )

        event_entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "user_id": user_id,
            "consolidated_count": len(memories),
            "importance_scores": scores,
            "average_importance": round(avg_importance, 4),
            "compression_ratio": round(compression_ratio, 4),
            "memories": memories,
            "metadata": metadata or {},
        }

        self.events.append(event_entry)
        if len(self.events) > self.max_events:
            self.events.pop(0)

        return event_entry

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Aggregates overall memory consolidation statistics across recorded events.

        Returns:
            Dict[str, Any]: Summary metrics including total count, average importance,
                           and average compression ratio.
        """
        if not self.events:
            return {
                "total_events": 0,
                "total_consolidated_memories": 0,
                "global_average_importance": 0.0,
                "global_average_compression_ratio": 0.0,
                "recent_event_count": 0,
            }

        total_events = len(self.events)
        total_memories = sum(e["consolidated_count"] for e in self.events)

        all_importance = [
            e["average_importance"] for e in self.events if e["average_importance"] > 0.0
        ]
        global_avg_importance = (
            sum(all_importance) / len(all_importance) if all_importance else 0.0
        )

        all_compression = [e["compression_ratio"] for e in self.events]
        global_avg_compression = (
            sum(all_compression) / len(all_compression) if all_compression else 0.0
        )

        return {
            "total_events": total_events,
            "total_consolidated_memories": total_memories,
            "global_average_importance": round(global_avg_importance, 4),
            "global_average_compression_ratio": round(global_avg_compression, 4),
            "recent_event_count": total_events,
        }

    def get_canvas_payload(
        self,
        event_type: str = "memory_consolidation_metrics",
        latest_event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Formats the accumulated metrics into a structured payload for Canvas UI ingestion.

        Args:
            event_type (str): Type identifier for the Canvas UI event.
            latest_event (Optional[Dict[str, Any]]): The most recent event payload if available.

        Returns:
            Dict[str, Any]: Standardized Canvas UI payload dictionary.
        """
        summary = self.get_metrics_summary()
        recent = [
            {
                "event_id": e["event_id"],
                "timestamp": e["timestamp"],
                "user_id": e["user_id"],
                "consolidated_count": e["consolidated_count"],
                "average_importance": e["average_importance"],
                "compression_ratio": e["compression_ratio"],
            }
            for e in self.events[-10:]
        ]

        return {
            "type": event_type,
            "event_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "status": "active",
            "data": {
                "summary": summary,
                "latest_event": latest_event,
                "recent_events": recent,
            },
        }

    def export_json(self) -> str:
        """
        Exports the formatted Canvas payload as a JSON string.

        Returns:
            str: JSON string of the Canvas UI payload.
        """
        return json.dumps(self.get_canvas_payload())


class CanvasMetricsBroadcasterV8:
    """
    An export module to broadcast memory consolidation metrics
    to a live dashboard via WebSockets.
    """

    def __init__(
        self,
        websocket: Optional[Any] = None,
        exporter: Optional[CanvasMemoryMetricsExporterV8] = None,
    ) -> None:
        """
        Initializes the CanvasMetricsBroadcasterV8.

        Args:
            websocket (Optional[Any]): An open asynchronous WebSocket connection.
            exporter (Optional[CanvasMemoryMetricsExporterV8]): Metrics exporter instance.
        """
        self.websocket = websocket
        self.exporter = exporter or CanvasMemoryMetricsExporterV8()
        self.logger = logging.getLogger(__name__)

    async def broadcast_consolidation_metrics(
        self,
        user_id: Union[int, str],
        memories: List[Dict[str, Any]],
        importance_scores: Optional[List[float]] = None,
        compression_ratio: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records a memory consolidation event, updates metrics, and broadcasts
        the updated Canvas payload over WebSocket.

        Args:
            user_id (Union[int, str]): User or session ID.
            memories (List[Dict[str, Any]]): List of consolidated memories.
            importance_scores (Optional[List[float]]): Memory importance scores.
            compression_ratio (float): Compression ratio.
            metadata (Optional[Dict[str, Any]]): Additional metadata.

        Returns:
            Dict[str, Any]: The recorded consolidation event.
        """
        event_entry = self.exporter.record_consolidation(
            user_id=user_id,
            memories=memories,
            importance_scores=importance_scores,
            compression_ratio=compression_ratio,
            metadata=metadata,
        )

        payload = self.exporter.get_canvas_payload(latest_event=event_entry)
        await self._broadcast(payload)
        return event_entry

    async def broadcast_metrics(self, payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Broadcasts the current memory metrics payload to the Canvas UI.

        Args:
            payload (Optional[Dict[str, Any]]): Optional custom payload to send.

        Returns:
            bool: True if broadcast succeeded, False otherwise.
        """
        if payload is None:
            payload = self.exporter.get_canvas_payload()
        return await self._broadcast(payload)

    async def _broadcast(self, payload: Dict[str, Any]) -> bool:
        """
        Helper method to serialize and send JSON payload over WebSocket.

        Args:
            payload (Dict[str, Any]): Event payload dictionary.

        Returns:
            bool: True if sent successfully, False otherwise.
        """
        if self.websocket is None:
            self.logger.debug(
                f"Skipping broadcast for {payload.get('type')} - no websocket connected."
            )
            return False

        try:
            message = json.dumps(payload)
            if hasattr(self.websocket, "send_text"):
                await self.websocket.send_text(message)
            else:
                await self.websocket.send(message)
            self.logger.debug(f"Successfully broadcasted {payload.get('type')} event.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to broadcast {payload.get('type')} event: {e}")
            return False
