"""MCPKernel Taint Tracking Sandbox V4.

Provides an enhanced sandbox execution environment that strictly deep-taints
outputs (like lists and dicts) when any input was tainted, enforcing strong
provenance tracking within MCP tools.
"""
from typing import Any, Callable, Dict

# We import from v2 to avoid circular imports present in v3 when importing EpisodicMemory -> MemorySystem -> TaintedWorkingMemory -> v3
from magda_agent.safety.taint_tracking_v2 import (
    MCPKernelV2,
    SandboxExecutionEnvironmentV2,
    TaintTrackerV2,
)
from magda_agent.safety.taint import PolicyViolationError


class TaintTrackerV4(TaintTrackerV2):
    """Enhanced TaintTracker inheriting from V2/V3 equivalent.

    Provides strict propagation tracking for sandbox environments.
    """

    def __init__(self) -> None:
        """Initialize the TaintTrackerV4."""
        super().__init__()


class SandboxExecutionEnvironmentV4(SandboxExecutionEnvironmentV2):
    """An enhanced sandbox execution environment using TaintTrackerV4.

    This sandbox ensures that if any inputs to a tool are tainted,
    the output structures (such as lists or dicts) are deeply tainted
    with the combined origins of all tainted inputs.
    """

    def __init__(self, tracker: TaintTrackerV4) -> None:
        """Initialize the SandboxExecutionEnvironmentV4.

        Args:
            tracker: The TaintTrackerV4 instance.
        """
        super().__init__(tracker=tracker)

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute a function in the sandbox.

        Automatically deep-propagates taint from inputs to output structures.

        Args:
            func: The function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of execution, deep-tainted if any inputs were tainted.
        """
        origins = set()
        for arg in args:
            origins.update(self.tracker.get_origins(arg))
        for val in kwargs.values():
            origins.update(self.tracker.get_origins(val))

        result = super().execute(func, *args, **kwargs)

        if origins:
            return self.tracker.taint_with_origins(result, origins)
        return result

    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute an async function in the sandbox.

        Automatically deep-propagates taint from inputs to output structures.

        Args:
            func: The async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The awaited result of execution, deep-tainted if any inputs were tainted.
        """
        origins = set()
        for arg in args:
            origins.update(self.tracker.get_origins(arg))
        for val in kwargs.values():
            origins.update(self.tracker.get_origins(val))

        result = await super().execute_async(func, *args, **kwargs)

        if origins:
            return self.tracker.taint_with_origins(result, origins)
        return result


class MCPKernelV4(MCPKernelV2):
    """Enhanced Kernel for executing tools safely with V4 taint origin tracking."""

    def __init__(self) -> None:
        """Initialize the MCPKernelV4."""
        super().__init__()
        self.tracker = TaintTrackerV4()
        self.sandbox = SandboxExecutionEnvironmentV4(self.tracker)

    def execute_tool(self, tool_func: Callable[..., Any], inputs: Dict[str, Any], is_sensitive: bool = False) -> Any:
        """Executes a tool within the kernel. If is_sensitive is True, tainted inputs will fail.

        Args:
            tool_func: The tool function.
            inputs: Dict of input arguments.
            is_sensitive: Whether the tool is sensitive and should block tainted inputs.

        Returns:
            The result of tool execution.

        Raises:
            PolicyViolationError: If a sensitive tool receives tainted inputs.
            RuntimeError: If execution fails for other reasons.
        """
        if is_sensitive:
            if self.tracker.is_tainted(inputs):
                origins = self.tracker.get_origins(inputs)
                raise PolicyViolationError(f"Tainted input to sensitive tool call from origins: {origins}")

        try:
            return self.sandbox.execute(tool_func, **inputs)
        except Exception as e:
            if isinstance(e, PolicyViolationError):
                raise
            raise RuntimeError(f"Tool execution failed: {str(e)}")
