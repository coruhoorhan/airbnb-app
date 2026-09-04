"""MCP Tool Execution Isolation Wrapper.

Provides isolated execution namespaces for MCP tools and enforces
taint tracking via TaintTrackerV2 to prevent unsafe data transitions.
"""
import copy
import inspect
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Set

from magda_agent.safety.taint_tracking_v2 import (
    PolicyViolationError,
    SandboxExecutionEnvironmentV2,
    TaintTrackerV2,
    get_origins,
    is_tainted,
)

logger = logging.getLogger(__name__)


class IsolatedContextNamespace:
    """Isolated execution scope for MCP tool execution.

    Holds isolated state variables, memory scope, and tool execution history
    to prevent state pollution of the main agent context.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        parent_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize an isolated context namespace.

        Args:
            name: Optional human-readable name for the namespace.
            parent_context: Optional dictionary to seed initial namespace variables.
        """
        self.namespace_id: str = f"mcp_ns_{uuid.uuid4().hex[:8]}"
        self.name: str = name or self.namespace_id
        self._data: Dict[str, Any] = copy.deepcopy(parent_context) if parent_context else {}
        self._history: List[Dict[str, Any]] = []

    def set_variable(self, key: str, value: Any) -> None:
        """Set a variable in the isolated namespace context."""
        self._data[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Retrieve a variable from the isolated namespace context."""
        return self._data.get(key, default)

    def has_variable(self, key: str) -> bool:
        """Check if a variable exists in the isolated namespace context."""
        return key in self._data

    def clear(self) -> None:
        """Clear all variables in the isolated namespace."""
        self._data.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of the current namespace state dictionary."""
        return copy.deepcopy(self._data)

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Return the tool execution history recorded in this namespace."""
        return list(self._history)

    def record_execution(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        output: Any,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record a tool execution entry in the namespace history log."""
        self._history.append({
            "tool_name": tool_name,
            "inputs": copy.deepcopy(inputs),
            "output": output,
            "success": success,
            "error": error,
        })

    def __enter__(self) -> "IsolatedContextNamespace":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        pass

    async def __aenter__(self) -> "IsolatedContextNamespace":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        pass


class MCPIsolationWrapper:
    """Wrapper executing MCP tools in an isolated execution namespace.

    Employs TaintTrackerV2 checks to detect and block unsafe data transitions
    and protects main agent context from side-effects or untrusted mutation.
    """

    def __init__(
        self,
        tracker: Optional[TaintTrackerV2] = None,
        sensitive_tools: Optional[Set[str]] = None,
        blocked_origins: Optional[Set[str]] = None,
        strict_mode: bool = True,
    ) -> None:
        """Initialize the MCP tool isolation wrapper.

        Args:
            tracker: Optional TaintTrackerV2 instance.
            sensitive_tools: Set of tool names deemed sensitive.
            blocked_origins: Set of taint origins disallowed from tool execution.
            strict_mode: Whether to enforce strict policy violations.
        """
        self.tracker: TaintTrackerV2 = tracker or TaintTrackerV2()
        self.sandbox: SandboxExecutionEnvironmentV2 = SandboxExecutionEnvironmentV2(self.tracker)
        self.sensitive_tools: Set[str] = set(sensitive_tools) if sensitive_tools else set()
        self.blocked_origins: Set[str] = set(blocked_origins) if blocked_origins else set()
        self.strict_mode: bool = strict_mode

    def create_namespace(
        self,
        name: Optional[str] = None,
        parent_context: Optional[Dict[str, Any]] = None,
    ) -> IsolatedContextNamespace:
        """Create a new isolated context namespace.

        Args:
            name: Optional namespace name.
            parent_context: Optional dict to seed initial variables.

        Returns:
            A new IsolatedContextNamespace instance.
        """
        return IsolatedContextNamespace(name=name, parent_context=parent_context)

    def _validate_safety(self, tool_name: str, inputs: Dict[str, Any], is_sensitive: bool = False) -> None:
        """Validate taint status and policy compliance of tool inputs.

        Raises:
            PolicyViolationError: If input data is tainted for a sensitive tool or matches blocked origins.
        """
        has_taint = self.tracker.is_tainted(inputs)
        origins = self.tracker.get_origins(inputs)

        # Check blocked origins
        if self.blocked_origins and (origins & self.blocked_origins):
            blocked_intersection = origins & self.blocked_origins
            msg = f"Input taint origin(s) {blocked_intersection} blocked for tool '{tool_name}'."
            logger.warning(msg)
            raise PolicyViolationError(msg)

        # Check sensitive tools
        is_tool_sensitive = is_sensitive or (tool_name in self.sensitive_tools)
        if is_tool_sensitive and has_taint:
            msg = f"Tainted input from origins {origins} passed to sensitive tool '{tool_name}'."
            logger.warning(msg)
            raise PolicyViolationError(msg)

    def execute_tool(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        inputs: Dict[str, Any],
        namespace: Optional[IsolatedContextNamespace] = None,
        is_sensitive: bool = False,
    ) -> Any:
        """Execute a synchronous MCP tool in an isolated context namespace.

        Args:
            tool_func: The tool function to execute.
            tool_name: The name of the MCP tool.
            inputs: Input arguments dictionary.
            namespace: Optional target namespace. If None, a temporary namespace is created.
            is_sensitive: Flag indicating whether this specific execution is sensitive.

        Returns:
            The execution result (taint-propagated if inputs were tainted).

        Raises:
            PolicyViolationError: If taint checks or safety policies fail.
            RuntimeError: If tool execution fails.
        """
        self._validate_safety(tool_name, inputs, is_sensitive=is_sensitive)

        target_ns = namespace or self.create_namespace(name=f"exec_{tool_name}")

        # Protect inputs against caller in-place mutation
        isolated_inputs = copy.copy(inputs)

        try:
            result = self.sandbox.execute(tool_func, **isolated_inputs)
            target_ns.record_execution(tool_name, inputs, result, success=True)
            target_ns.set_variable(f"last_result_{tool_name}", result)
            return result
        except Exception as e:
            if isinstance(e, PolicyViolationError):
                raise
            err_msg = str(e)
            target_ns.record_execution(tool_name, inputs, None, success=False, error=err_msg)
            raise RuntimeError(f"Isolated execution of tool '{tool_name}' failed: {err_msg}") from e

    async def execute_tool_async(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        inputs: Dict[str, Any],
        namespace: Optional[IsolatedContextNamespace] = None,
        is_sensitive: bool = False,
    ) -> Any:
        """Execute an asynchronous MCP tool in an isolated context namespace.

        Args:
            tool_func: The async tool function to execute.
            tool_name: The name of the MCP tool.
            inputs: Input arguments dictionary.
            namespace: Optional target namespace. If None, a temporary namespace is created.
            is_sensitive: Flag indicating whether this specific execution is sensitive.

        Returns:
            The execution result (taint-propagated if inputs were tainted).

        Raises:
            PolicyViolationError: If taint checks or safety policies fail.
            RuntimeError: If tool execution fails.
        """
        self._validate_safety(tool_name, inputs, is_sensitive=is_sensitive)

        target_ns = namespace or self.create_namespace(name=f"exec_async_{tool_name}")

        isolated_inputs = copy.copy(inputs)

        try:
            if inspect.iscoroutinefunction(tool_func):
                result = await self.sandbox.execute_async(tool_func, **isolated_inputs)
            else:
                result = self.sandbox.execute(tool_func, **isolated_inputs)
                if inspect.isawaitable(result):
                    result = await result

            target_ns.record_execution(tool_name, inputs, result, success=True)
            target_ns.set_variable(f"last_result_{tool_name}", result)
            return result
        except Exception as e:
            if isinstance(e, PolicyViolationError):
                raise
            err_msg = str(e)
            target_ns.record_execution(tool_name, inputs, None, success=False, error=err_msg)
            raise RuntimeError(f"Isolated execution of async tool '{tool_name}' failed: {err_msg}") from e
