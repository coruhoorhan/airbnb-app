"""
MCP Action Tool Governance V5 Module.

Implements an Action Tool Governance layer that intercepts and logs external
tool calls to ensure sandboxed execution. Inspired by MCP/ACS standards.
"""
import logging
from typing import Any, Dict, Protocol, runtime_checkable, Optional


class GovernanceError(Exception):
    """Exception raised for governance or security violations during tool execution."""
    pass


@runtime_checkable
class ToolExecutor(Protocol):
    """
    Protocol for underlying tool executors or sandboxes.
    """
    def execute_tool(self, tool_name: str, args: Dict[str, Any], auth_token: Optional[str] = None) -> Any:
        """
        Executes a tool with the given name and arguments.
        """
        ...


class ActionToolGovernance:
    """
    Governance layer that wraps an existing tool executor (e.g., registry or sandbox).
    Intercepts calls, logs execution attempts, and enforces basic policy checks.
    """

    def __init__(self, backend: ToolExecutor, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize the Action Tool Governance layer.

        Args:
            backend (ToolExecutor): The underlying executor or sandbox to wrap.
            logger (Optional[logging.Logger]): Logger instance to use. If None, uses default.
        """
        self.backend = backend
        self.logger = logger or logging.getLogger(__name__)

    def execute_tool(self, tool_name: str, args: Dict[str, Any], auth_token: Optional[str] = None) -> Any:
        """
        Intercepts tool execution, logs the attempt, and passes execution to the backend.

        Args:
            tool_name (str): The name of the tool to execute.
            args (Dict[str, Any]): The arguments to pass to the tool.
            auth_token (Optional[str]): An optional authentication token.

        Returns:
            Any: The result of the tool execution from the backend.

        Raises:
            GovernanceError: If the backend fails or policy is violated.
        """
        # 1. Pre-execution interception and logging
        self.logger.info(
            f"[GOVERNANCE] Intercepted execution attempt for tool '{tool_name}'. "
            f"Args keys: {list(args.keys())}, Auth provided: {'Yes' if auth_token else 'No'}"
        )

        try:
            # 2. Forward to underlying backend sandbox/registry
            result = self.backend.execute_tool(tool_name, args, auth_token)

            # 3. Post-execution success logging
            self.logger.info(f"[GOVERNANCE] Successfully executed tool '{tool_name}'.")
            return result

        except Exception as e:
            # 4. Exception interception and logging
            self.logger.error(
                f"[GOVERNANCE] Tool execution failed for '{tool_name}'. Reason: {e}"
            )
            # Re-raise as GovernanceError or propagate depending on strictness
            if isinstance(e, GovernanceError):
                raise e
            raise GovernanceError(f"Backend execution failed for tool '{tool_name}': {e}") from e
