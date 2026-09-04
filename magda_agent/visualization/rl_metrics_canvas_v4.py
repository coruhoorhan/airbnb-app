import json
from typing import Dict, Any

from magda_agent.learning.canvas_metrics import RLCanvasMetricsExporter


class RLMetricsCanvasV4:
    """
    OpenClaw-RL Canvas Metrics V4 visualizer.
    This class wraps the RLCanvasMetricsExporter to provide a JSON stream
    of Q-value updates and reinforcement learning metrics for the Canvas UI.
    """

    def __init__(self, exporter: RLCanvasMetricsExporter) -> None:
        """
        Initializes the RLMetricsCanvasV4 with an exporter.

        Args:
            exporter (RLCanvasMetricsExporter): The exporter used to retrieve formatted RL metrics.
        """
        self.exporter = exporter

    def get_metrics_payload(self) -> Dict[str, Any]:
        """
        Retrieves the structured RL metrics payload.

        Returns:
            Dict[str, Any]: The structured UI visualization state for RL metrics.
        """
        return self.exporter.export_canvas_payload()

    def get_metrics_json(self) -> str:
        """
        Retrieves the structured RL metrics payload as a JSON string.

        Returns:
            str: JSON-encoded string of the RL metrics state.
        """
        return json.dumps(self.get_metrics_payload())
