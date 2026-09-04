import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class CanvasLearningMetricsExporterV9:
    """
    Handles tracking, aggregation, and formatting of online RL learning metric shifts
    (e.g., User Model parameters) for live Canvas UI visualization, inspired by OpenClaw Canvas Live Visualization trends.
    """

    def __init__(self, max_events: int = 50) -> None:
        """
        Initializes the CanvasLearningMetricsExporterV9.

        Args:
            max_events (int): Maximum number of recent learning shift events to retain.
        """
        self.events: list[Dict[str, Any]] = []
        self.max_events = max_events

    def record_learning_shift(
        self,
        user_id: Union[int, str],
        user_model_parameters: Dict[str, Any],
        metric_shifts: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records a single online RL learning metric shift event and formats the metrics.

        Args:
            user_id (Union[int, str]): The user or session ID.
            user_model_parameters (Dict[str, Any]): The updated user model parameters.
            metric_shifts (Dict[str, float]): The shifts/changes in specific learning metrics.
            metadata (Optional[Dict[str, Any]]): Additional contextual metadata.

        Returns:
            Dict[str, Any]: The recorded event entry with calculated metrics.
        """
        event_entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "user_id": user_id,
            "user_model_parameters": user_model_parameters,
            "metric_shifts": metric_shifts,
            "metadata": metadata or {},
        }

        self.events.append(event_entry)
        if len(self.events) > self.max_events:
            self.events.pop(0)

        return event_entry

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Aggregates overall learning metric shift statistics across recorded events.

        Returns:
            Dict[str, Any]: Summary metrics including total recorded shifts and
                            average magnitude of specific metrics (if any).
        """
        if not self.events:
            return {
                "total_shifts_recorded": 0,
                "recent_event_count": 0,
            }

        total_shifts = len(self.events)

        return {
            "total_shifts_recorded": total_shifts,
            "recent_event_count": total_shifts,
        }

    def get_canvas_payload(
        self,
        event_type: str = "learning_metric_shift",
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
                "metric_shifts": e["metric_shifts"],
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


class CanvasLearningBroadcasterV9:
    """
    An export module to broadcast online RL learning metric shifts
    to a live dashboard via WebSockets.
    """

    def __init__(
        self,
        websocket: Optional[Any] = None,
        exporter: Optional[CanvasLearningMetricsExporterV9] = None,
    ) -> None:
        """
        Initializes the CanvasLearningBroadcasterV9.

        Args:
            websocket (Optional[Any]): An open asynchronous WebSocket connection.
            exporter (Optional[CanvasLearningMetricsExporterV9]): Metrics exporter instance.
        """
        self.websocket = websocket
        self.exporter = exporter or CanvasLearningMetricsExporterV9()
        self.logger = logging.getLogger(__name__)

    async def broadcast_learning_shift(
        self,
        user_id: Union[int, str],
        user_model_parameters: Dict[str, Any],
        metric_shifts: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records a learning shift event, updates metrics, and broadcasts
        the updated Canvas payload over WebSocket.

        Args:
            user_id (Union[int, str]): User or session ID.
            user_model_parameters (Dict[str, Any]): The updated user model parameters.
            metric_shifts (Dict[str, float]): The shifts/changes in specific learning metrics.
            metadata (Optional[Dict[str, Any]]): Additional metadata.

        Returns:
            Dict[str, Any]: The recorded shift event.
        """
        event_entry = self.exporter.record_learning_shift(
            user_id=user_id,
            user_model_parameters=user_model_parameters,
            metric_shifts=metric_shifts,
            metadata=metadata,
        )

        payload = self.exporter.get_canvas_payload(latest_event=event_entry)
        await self._broadcast(payload)
        return event_entry

    async def broadcast_metrics(self, payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Broadcasts the current learning metrics payload to the Canvas UI.

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
