"""MCP Kernel Taint Tracking v6 for sandboxed execution and variable tracking."""

from typing import Any, Dict
from magda_agent.security.mcp_kernel import MCPKernel, SecurityError
from magda_agent.security.mcp_kernel_taint import is_tainted, mark_tainted, sanitize

class TaintedValueV6:
    """
    Tracks if a specific value is tainted.

    Attributes:
        value (Any): The underlying value.
        tainted (bool): A flag indicating if this value is tainted.
    """
    def __init__(self, value: Any, tainted: bool = False) -> None:
        """
        Initializes a new TaintedValueV6 instance.

        Args:
            value (Any): The value to track.
            tainted (bool): A boolean flag indicating whether the value is considered tainted. Defaults to False.
        """
        self.value = value
        self.tainted = tainted

    def unwrap(self) -> Any:
        """
        Retrieves the underlying untainted value.

        Returns:
            Any: The original value wrapped by this class.
        """
        return self.value

    def set_tainted(self, tainted: bool) -> None:
        """
        Sets the tainted flag of the value.

        Args:
            tainted (bool): The new tainted state.
        """
        self.tainted = tainted


class MCPKernelTaintTrackerV6(MCPKernel):
    """
    Extends MCPKernel to support executing plugins within a v6 isolated taint tracking environment.
    """

    def execute_plugin(self, code: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a plugin using MCPKernel, tracking tainted variables and wrapping tool execution logic.

        Args:
            code (str): The plugin python code to execute.
            inputs (Dict[str, Any]): A dictionary of variables to provide to the plugin.

        Returns:
            Dict[str, Any]: The resulting local variables dictionary after execution, with taint propagated appropriately.

        Raises:
            SecurityError: If the plugin code itself is tainted.
        """
        if is_tainted(code):
            raise SecurityError("Code is tainted and unsafe to execute.")

        inputs_tainted = is_tainted(inputs)

        clean_inputs = sanitize(inputs)

        # Unwrap any pre-existing TaintedValueV6 manually as sanitize might miss custom objects
        for k, v in clean_inputs.items():
            if isinstance(v, TaintedValueV6):
                clean_inputs[k] = v.unwrap()
                if v.tainted:
                    inputs_tainted = True

        result_locals = super().execute(code, locals_dict=clean_inputs)

        if inputs_tainted:
            return mark_tainted(result_locals)

        return result_locals
