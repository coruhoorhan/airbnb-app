"""
Skill Execution Experience Extraction module.

This module provides the SkillHintsExtractor class, which analyzes recent
successful external skill execution logs and synthesizes reusable "hints"
to optimize and speed up subsequent invocations of those same tools.
"""

from typing import List, Dict, Any

class SkillHintsExtractor:
    """
    Extracts reusable hints from successful tool execution logs.
    """

    def __init__(self, llm_client: Any = None):
        """
        Initialize the extractor.

        Args:
            llm_client: Optional LLM client to use for synthesizing hints.
        """
        self.llm_client = llm_client

    def extract_hints(self, tool_execution_logs: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Extract hints from a list of tool execution logs.

        Args:
            tool_execution_logs (List[Dict[str, Any]]): A list of dictionaries representing
                tool executions. Each dictionary should contain at least 'tool_name',
                'arguments', and 'success' keys.

        Returns:
            Dict[str, str]: A dictionary mapping tool names to synthesized hint strings.
        """
        successful_executions: Dict[str, List[Dict[str, Any]]] = {}

        for log in tool_execution_logs:
            tool_name = log.get("tool_name")
            success = log.get("success", False)
            arguments = log.get("arguments", {})

            if success and tool_name:
                if tool_name not in successful_executions:
                    successful_executions[tool_name] = []
                successful_executions[tool_name].append(arguments)

        hints = {}
        for tool_name, executions in successful_executions.items():
            hints[tool_name] = self._synthesize_hint(tool_name, executions)

        return hints

    def _synthesize_hint(self, tool_name: str, executions: List[Dict[str, Any]]) -> str:
        """
        Synthesize a hint for a specific tool based on its successful executions.

        Args:
            tool_name (str): The name of the tool.
            executions (List[Dict[str, Any]]): A list of arguments from successful executions.

        Returns:
            str: The synthesized hint.
        """
        if self.llm_client:
            # Simulate an LLM call to synthesize the hint
            prompt = f"Synthesize a usage hint for the tool '{tool_name}' based on these successful arguments: {executions}"
            # In a real implementation, this would call self.llm_client.generate(prompt)
            # We assume the mock returns a string directly
            return self.llm_client.generate(prompt)

        # Fallback to a simple heuristic if no LLM client is provided
        num_executions = len(executions)
        common_keys = set()
        if executions:
            common_keys = set(executions[0].keys())
            for exec_args in executions[1:]:
                common_keys.intersection_update(exec_args.keys())

        keys_str = ", ".join(common_keys) if common_keys else "no common arguments"
        return f"Tool '{tool_name}' successfully used {num_executions} times. Common arguments: {keys_str}."
