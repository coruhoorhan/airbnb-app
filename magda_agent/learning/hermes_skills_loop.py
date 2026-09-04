import time
from typing import Dict, Any, Optional

class HermesSkillsLoop:
    """
    Hermes Self-Improving Skills Loop.

    This module tracks skill usage success/failure and iteratively updates
    a local skill metadata registry to improve context and performance.
    """

    def __init__(self) -> None:
        """
        Initializes the HermesSkillsLoop.
        The local skill metadata registry is an in-memory dictionary.
        """
        self._registry: Dict[str, Dict[str, Any]] = {}

    def record_skill_outcome(
        self, skill_name: str, success: bool, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Records the outcome of a skill execution.

        Args:
            skill_name: The name of the skill executed.
            success: Whether the skill execution was successful.
            metadata: Additional metadata related to the execution.
        """
        if skill_name not in self._registry:
            self._registry[skill_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_usage": 0,
                "last_used_timestamp": 0.0,
                "success_rate": 0.0,
                "metadata": {}
            }

        skill_data = self._registry[skill_name]
        skill_data["total_usage"] += 1

        if success:
            skill_data["success_count"] += 1
        else:
            skill_data["failure_count"] += 1

        skill_data["last_used_timestamp"] = time.time()
        skill_data["success_rate"] = skill_data["success_count"] / skill_data["total_usage"]

        if metadata:
            # Update metadata recursively or simply update keys
            skill_data["metadata"].update(metadata)

    def get_skill_metadata(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the tracked metadata for a specific skill.

        Args:
            skill_name: The name of the skill.

        Returns:
            A dictionary containing the skill metadata, or None if not found.
        """
        return self._registry.get(skill_name)
