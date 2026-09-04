import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class MCPExportTelemetryTracker:
    """
    A telemetry hook for tracking when MCP dynamic tools are exported.
    Allows visibility into the lifecycle and usage of tools dynamically exported
    by the agent.
    """

    def __init__(self) -> None:
        """
        Initialize the MCPExportTelemetryTracker.
        """
        self.exports: List[Dict[str, Any]] = []

    def track_export(self, tool_name: str, export_metadata: Dict[str, Any]) -> None:
        """
        Track an MCP tool export event.

        Args:
            tool_name (str): The name of the tool being exported.
            export_metadata (Dict[str, Any]): Additional metadata regarding the export event.
        """
        logger.info(f"Tracking MCP tool export: {tool_name}")
        record = {
            "tool_name": tool_name,
            "metadata": export_metadata
        }
        self.exports.append(record)
