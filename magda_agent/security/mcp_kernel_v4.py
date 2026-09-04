"""MCPKernel Taint Tracking Isolation V4 for executing sandboxed plugins."""

from typing import Any, Dict

from magda_agent.security.mcp_kernel import MCPKernel, SecurityError
from magda_agent.security.mcp_kernel_taint import is_tainted, mark_tainted, sanitize


class MCPKernelV4(MCPKernel):
    """
    Extends MCPKernel to support executing plugins with taint tracking.
    """

    def execute_plugin(self, code: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a plugin using MCPKernel, correctly tracking taint.

        Args:
            code: The plugin python code to execute.
            inputs: A dictionary of variables to provide to the plugin.

        Returns:
            The resulting local variables dictionary after execution.

        Raises:
            SecurityError: If the plugin code itself is tainted.
        """
        if is_tainted(code):
            raise SecurityError("Code is tainted and unsafe to execute.")

        inputs_tainted = is_tainted(inputs)

        # Sanitize inputs before passing to MCPKernel's execute method to avoid its strict block
        clean_inputs = sanitize(inputs)

        # Run execution
        result_locals = super().execute(code, locals_dict=clean_inputs)

        # If inputs were tainted, the output must be marked as tainted
        if inputs_tainted:
            return mark_tainted(result_locals)

        return result_locals
