import logging
from typing import List, Dict, Optional, Any

class ExperienceGeneratorV2:
    """
    Hermes-inspired Skill Creation v2 module.
    Analyzes historical trace logs and auto-generates Python skills based on successful interactions.
    """

    def __init__(self, llm_client: Any) -> None:
        """
        Initializes the ExperienceGeneratorV2.

        Args:
            llm_client: The LLM client used to generate skill code from traces.
        """
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)

    def _format_traces(self, traces: List[Dict[str, Any]]) -> str:
        """
        Formats a list of execution traces into a string for the LLM prompt.

        Args:
            traces: A list of dictionaries representing the trace logs.

        Returns:
            A formatted string of the traces.
        """
        formatted = "Execution Traces:\n"
        for i, trace in enumerate(traces):
            step_name = trace.get("step_name", "Unknown Step")
            input_data = trace.get("input", "None")
            output_data = trace.get("output", "None")
            status = trace.get("status", "Unknown")

            formatted += f"Step {i+1}: {step_name} | Status: {status}\n"
            formatted += f"  Input: {input_data}\n"
            formatted += f"  Output: {output_data}\n"
        return formatted

    async def generate_skill_from_traces(
        self,
        traces: List[Dict[str, Any]],
        skill_name: str,
        description: str
    ) -> Optional[str]:
        """
        Generates Python skill code based on a sequence of successful execution traces.

        Args:
            traces: The list of trace dictionaries.
            skill_name: The desired name for the generated skill.
            description: A brief description of what the skill should accomplish.

        Returns:
            The generated Python code as a string, or None if generation fails.
        """
        if not traces:
            self.logger.warning("No traces provided for skill generation.")
            return None

        # Check if traces represent a successful outcome (heuristic: last trace status is success)
        last_trace = traces[-1]
        if last_trace.get("status") != "success":
            self.logger.warning("Traces do not indicate a successful interaction. Aborting generation.")
            return None

        formatted_traces = self._format_traces(traces)

        prompt = f"""
You are an expert AI agent developer.
Based on the following successful execution traces, generate a reusable Python module that encapsulates this behavior into a new skill.

Skill Name: {skill_name}
Description: {description}

{formatted_traces}

The generated code MUST:
1. Be a valid Python class.
2. Include type hints for all parameters and return types.
3. Include detailed docstrings.
4. Implement a `run` or `execute` method that performs the core logic inferred from the traces.

Return ONLY the Python code. Do not include markdown formatting like ```python.
"""
        try:
            # Assuming llm_client has an async generate_text method for the purpose of this mockable interface
            response = await self.llm_client.generate_text(prompt)
            # Basic cleanup in case LLM still returns markdown blocks
            if response.startswith("```python"):
                response = response[9:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return response.strip()
        except Exception as e:
            self.logger.error(f"Failed to generate skill from traces: {e}")
            return None
