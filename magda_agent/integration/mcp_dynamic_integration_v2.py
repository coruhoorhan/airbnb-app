import logging
from typing import Dict, Any, Callable, Optional
from magda_agent.skills.mcp_registry_v7 import MCPRegistryV7

class MCPDynamicIntegrationV2:
    """
    A dynamic module to seamlessly import and execute external MCP tools at runtime.
    Wraps MCP tools dynamically and registers them into the skill registry.
    """

    def __init__(self, registry: MCPRegistryV7):
        """
        Initialize the MCP Dynamic Integration module.

        Args:
            registry (MCPRegistryV7): The skill registry to use for registering tools.
        """
        self.registry = registry
        # Map of tool_name to its executable wrapper
        self._executors: Dict[str, Callable[..., Any]] = {}

    def register_and_wrap(self, tool_schema: Dict[str, Any], executor: Callable[..., Any]) -> bool:
        """
        Dynamically reads an MCP standard tool definition, wraps it into the skill registry,
        and associates it with an execution callable.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema.
            executor (Callable[..., Any]): The callable that executes the tool logic.

        Returns:
            bool: True if registration was successful, False otherwise.
        """
        if not isinstance(tool_schema, dict) or "name" not in tool_schema:
            logging.error("Failed to register tool: Invalid schema missing 'name'.")
            return False

        tool_name = tool_schema["name"]

        # Register the schema into the registry
        if self.registry.register_tool(tool_schema):
            self._executors[tool_name] = executor
            logging.info(f"Dynamically registered and wrapped MCP tool: {tool_name}")
            return True
        else:
            logging.error(f"Registry failed to register MCP tool schema: {tool_name}")
            return False

    def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Dynamically executes a registered external MCP tool.

        Args:
            tool_name (str): The name of the MCP tool to execute.
            **kwargs (Any): The arguments to pass to the tool's executor.

        Returns:
            Any: The result from the executor, or None if tool not found or failed.
        """
        if tool_name not in self._executors:
            logging.error(f"Execution failed: MCP tool '{tool_name}' not found or not wrapped.")
            return None

        executor = self._executors[tool_name]
        try:
            result = executor(**kwargs)
            return result
        except Exception as e:
            logging.error(f"Execution failed for MCP tool '{tool_name}': {e}")
            return None

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregisters the tool from both the integration module and the underlying registry.

        Args:
            tool_name (str): The name of the MCP tool to unregister.

        Returns:
            bool: True if successfully unregistered, False otherwise.
        """
        if tool_name in self._executors:
            del self._executors[tool_name]
            return self.registry.unregister_tool(tool_name)
        return False
