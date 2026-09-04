import json
from typing import Any, Dict, List

class ProceduralMemoryGenerator:
    """
    A procedural memory generator that converts multi-step success logs
    into reusable skill templates.
    """

    def generate_skill_template(self, success_logs: List[Dict[str, Any]]) -> str:
        """
        Parses a list of success log dictionaries (representing steps taken)
        and generates a reusable skill template.

        Args:
            success_logs (List[Dict[str, Any]]): A list of dictionaries, where each dictionary
                represents a successful step. Expected to have keys like 'action', 'parameters',
                and optionally 'result'.

        Returns:
            str: A formatted JSON string representing the skill template.
        """
        if not success_logs:
            return json.dumps({"skill_name": "unknown_skill", "steps": []}, indent=2)

        steps = []
        for i, log in enumerate(success_logs):
            step = {
                "step_index": i + 1,
                "action": log.get("action", "unknown_action"),
                "parameters": log.get("parameters", {})
            }
            steps.append(step)

        template = {
            "skill_name": "auto_generated_skill",
            "description": "Automatically generated skill from success logs.",
            "steps": steps
        }

        return json.dumps(template, indent=2)
