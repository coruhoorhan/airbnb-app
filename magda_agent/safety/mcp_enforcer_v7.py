import logging
from typing import Dict, Any, List

from magda_agent.safety.policy import PolicyLayer
from magda_agent.safety.acs import SecurityViolationError

logger = logging.getLogger(__name__)

class MCPActionEnforcer:
    """
    Enforcer component that strictly validates inputs and blocks execution
    of high-risk MCP action tools unless explicitly approved via the policy layer.
    """

    def __init__(self, sensitive_prefixes: List[str] = None):
        """
        Initializes the enforcer.

        Args:
            sensitive_prefixes: A list of tool name prefixes considered high-risk.
                                Defaults to ['write_', 'delete_', 'update_', 'execute_'].
        """
        self.sensitive_prefixes = sensitive_prefixes or ['write_', 'delete_', 'update_', 'execute_']

    def is_high_risk(self, tool_name: str) -> bool:
        """Determines if a tool is considered high risk based on its name."""
        return any(tool_name.startswith(prefix) for prefix in self.sensitive_prefixes)

    def enforce(self, tool_name: str, payload: Dict[str, Any], policy_layer: PolicyLayer) -> bool:
        """
        Enforces policy on a given MCP tool execution.

        Args:
            tool_name: The name of the tool to execute.
            payload: The arguments for the tool.
            policy_layer: The PolicyLayer instance to evaluate the action.

        Returns:
            True if the action is allowed.

        Raises:
            SecurityViolationError: If the action is blocked by the policy layer.
        """
        if self.is_high_risk(tool_name):
            logger.info(f"MCPActionEnforcer intercepting high-risk tool call: {tool_name}")
            allow, explanation = policy_layer.evaluate(tool_name, **payload)
            if not allow:
                raise SecurityViolationError(f"High-risk MCP action '{tool_name}' blocked by policy: {explanation}")
            logger.info(f"High-risk MCP action '{tool_name}' approved by policy.")
            return True

        logger.debug(f"MCPActionEnforcer allowing safe tool call: {tool_name}")
        return True
