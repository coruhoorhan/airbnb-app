import json
from typing import Dict, List, Any
import time

class SkillTelemetryTracker:
    """
    A tracker for skill usage metrics that aggregates statistics over time
    and can export them in an agentskills.io compatible JSON format.
    """

    def __init__(self) -> None:
        """
        Initialize the telemetry tracker with an empty metrics dictionary.
        """
        # skill_name -> {"total_calls": int, "success_count": int, "total_execution_time_ms": float}
        self._metrics: Dict[str, Dict[str, Any]] = {}

    def record_usage(self, skill_name: str, success: bool, execution_time_ms: float) -> None:
        """
        Record a single execution of a skill.

        Args:
            skill_name (str): The name of the skill executed.
            success (bool): Whether the execution was successful.
            execution_time_ms (float): The time taken for the execution in milliseconds.
        """
        if skill_name not in self._metrics:
            self._metrics[skill_name] = {
                "total_calls": 0,
                "success_count": 0,
                "total_execution_time_ms": 0.0
            }

        metrics = self._metrics[skill_name]
        metrics["total_calls"] += 1
        if success:
            metrics["success_count"] += 1
        metrics["total_execution_time_ms"] += execution_time_ms

    def get_aggregated_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the aggregated metrics for all tracked skills.

        Returns:
            Dict[str, Dict[str, Any]]: Aggregated metrics per skill.
        """
        aggregated: Dict[str, Dict[str, Any]] = {}
        for skill_name, data in self._metrics.items():
            total_calls = data["total_calls"]
            success_count = data["success_count"]
            total_exec_time = data["total_execution_time_ms"]

            success_rate = (success_count / total_calls) if total_calls > 0 else 0.0
            avg_exec_time = (total_exec_time / total_calls) if total_calls > 0 else 0.0

            aggregated[skill_name] = {
                "total_calls": total_calls,
                "success_rate": round(success_rate, 4),
                "average_execution_time_ms": round(avg_exec_time, 2)
            }
        return aggregated

    def export_agentskills_format(self) -> str:
        """
        Export the aggregated telemetry data in an agentskills.io compatible JSON string.

        Returns:
            str: JSON string representing the telemetry export.
        """
        aggregated = self.get_aggregated_metrics()

        skills_payload: List[Dict[str, Any]] = []
        for skill_name, metrics in aggregated.items():
            skills_payload.append({
                "name": skill_name,
                "metrics": metrics
            })

        payload = {
            "skills": skills_payload,
            "version": "1.0",
            "exporter": "magda_telemetry"
        }

        return json.dumps(payload, indent=2)
