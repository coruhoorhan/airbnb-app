import logging
from typing import Any, Dict, List, Optional


class MCPGovernanceV6:
    """
    Governance layer for intercepting and sandboxing external MCP tool execution calls.
    """

    def __init__(self, allowed_tools: Optional[List[str]] = None, denied_tools: Optional[List[str]] = None) -> None:
        """
        Initializes the governance layer.

        Args:
            allowed_tools: List of tool names that are explicitly allowed. If None, all tools not in denied_tools are allowed.
            denied_tools: List of tool names that are explicitly blocked.
        """
        self.allowed_tools = allowed_tools
        self.denied_tools = denied_tools or []

    def intercept_tool_execution(self, name: str, **kwargs: Any) -> None:
        """
        Intercepts an external tool call and raises an error if it's blocked by the governance policy.

        Args:
            name: The name of the tool being executed.
            **kwargs: Arguments passed to the tool.

        Raises:
            RuntimeError: If the tool is blocked.
        """
        if name in self.denied_tools:
            logging.warning(f"Governance block: Tool '{name}' is explicitly denied.")
            raise RuntimeError(f"Tool {name} is blocked by governance policy.")

        if self.allowed_tools is not None and name not in self.allowed_tools:
            logging.warning(f"Governance block: Tool '{name}' is not in the allowed list.")
            raise RuntimeError(f"Tool {name} is blocked by governance policy.")
