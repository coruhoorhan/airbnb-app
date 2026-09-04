"""
MCP Tool Runtime Permission Scoping module.
Maps specific MCP tools to permission scopes and enforces explicit confirmation for sensitive tools.
"""

import enum
import logging
from typing import Any, Dict, Tuple

from magda_agent.safety.policy import PolicyLayer


class PermissionScope(enum.Enum):
    """Enumeration of permission scopes for MCP tools."""
    SAFE = "safe"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class MCPPermissionScopingPolicy(PolicyLayer):
    """
    PolicyLayer implementation that enforces permission scopes for MCP tools.
    Requires explicit 'confirmed=True' in tool kwargs for SENSITIVE or RESTRICTED tools.
    """

    def __init__(self) -> None:
        """Initializes the MCP permission scoping policy with an empty mapping."""
        super().__init__()
        self._tool_scopes: Dict[str, PermissionScope] = {}

    def set_tool_scope(self, tool_name: str, scope: PermissionScope) -> None:
        """
        Maps an MCP tool to a specific permission scope.

        Args:
            tool_name: The name of the tool.
            scope: The permission scope to assign.
        """
        self._tool_scopes[tool_name] = scope

    def evaluate(self, tool_name: str, **kwargs: Any) -> Tuple[bool, str]:
        """
        Evaluates the tool execution against permission scoping rules.
        Falls back to the parent PolicyLayer evaluation if local rules pass.

        Args:
            tool_name: The name of the tool to evaluate.
            kwargs: Arguments provided to the tool.

        Returns:
            Tuple[bool, str]: (True if allowed, Explanation string).
        """
        # Check if the tool has a specific scope mapped
        scope = self._tool_scopes.get(tool_name, PermissionScope.SAFE)

        if scope in (PermissionScope.SENSITIVE, PermissionScope.RESTRICTED):
            confirmed = kwargs.get("confirmed")
            # Need strict boolean True
            if confirmed is not True:
                explanation = (
                    f"Action '{tool_name}' requires explicit confirmation because its scope is {scope.value}. "
                    "You must provide 'confirmed=True' in the tool arguments to proceed."
                )

                # Log denial locally like parent PolicyLayer would
                self.audit_logger.log_call(
                    tool_name=tool_name,
                    kwargs=kwargs,
                    why=kwargs.get("why", "Permission scope verification"),
                    result={"allowed": False, "explanation": explanation},
                    duration=0.0,
                )
                logging.warning(f"MCPPermissionScopingPolicy: DENY - {tool_name} with args {kwargs}. Reason: {explanation}")
                return False, explanation

        # Proceed to base PolicyLayer evaluation
        return super().evaluate(tool_name, **kwargs)
