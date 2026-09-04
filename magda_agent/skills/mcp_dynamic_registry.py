import logging
import asyncio
from typing import Dict, Any, List

from magda_agent.skills.mcp_registry import MCPRegistry
from magda_agent.skills.mcp_client import MCPClient


class MCPPrefixedToolRegistry:
    """
    Registry for dynamic loading and routing of MCP tools with server prefixes.
    Supports runtime function concurrency via asyncio.
    """

    def __init__(self, mcp_client: MCPClient) -> None:
        """
        Initialize the prefixed tool registry.

        Args:
            mcp_client (MCPClient): The MCP client used for tool execution.
        """
        self.mcp_client = mcp_client

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Executes a remote MCP tool. Handles optional server prefixes.
        If a prefix exists (e.g., 'server.tool_name'), MCPClient handles it natively.

        Args:
            tool_name (str): The name of the tool (can be prefixed).
            kwargs: Arguments for the tool.

        Returns:
            Any: The execution result.
        """
        logging.info(f"Routing execution for tool: {tool_name}")
        return await self.mcp_client.execute_tool(tool_name, **kwargs)

    async def execute_concurrently(self, tasks: List[Dict[str, Any]]) -> List[Any]:
        """
        Executes multiple MCP tools concurrently using asyncio.

        Args:
            tasks (List[Dict[str, Any]]): A list of task dictionaries. Each dictionary
                should have 'tool' (str) and 'params' (Dict) keys.

        Returns:
            List[Any]: A list of results corresponding to the tasks.
        """
        logging.info(f"Executing {len(tasks)} MCP tools concurrently.")

        coroutines = []
        for task in tasks:
            tool_name = task.get("tool")
            params = task.get("params", {})
            if not tool_name:
                continue

            # Create a coroutine for each tool execution
            coroutines.append(self.execute_tool(tool_name, **params))

        # Run all coroutines concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return list(results)


class MCPDynamicRegistrarV4:
    """
    Endpoint for dynamically registering new MCP tools at runtime via MCP protocol.
    Specifically handles async skills to support true runtime concurrency.
    """

    def __init__(self, registry: MCPRegistry) -> None:
        """
        Initialize the dynamic registrar V4.

        Args:
            registry (MCPRegistry): The existing MCP tool registry instance.
        """
        self.registry = registry


    def _perform_enhanced_validation(self, tool_schema: Dict[str, Any]) -> bool:
        """
        Performs enhanced validation on the MCP tool schema.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema to validate.

        Returns:
            bool: True if validation passes, False otherwise.
        """
        # Check if name is valid (e.g., alphanumeric and underscores only)
        if "name" in tool_schema:
            import re
            if not re.match(r"^[a-zA-Z0-9_-]+$", tool_schema["name"]):
                logging.error("Enhanced Validation Failed: Invalid tool name format.")
                return False

        # Check if inputSchema exists and is a dictionary if provided
        if "inputSchema" in tool_schema:
            if not isinstance(tool_schema["inputSchema"], dict):
                logging.error("Enhanced Validation Failed: inputSchema must be a dictionary.")
                return False

        return True

    def register_tool_at_runtime(self, tool_schema: Dict[str, Any], is_async: bool = False) -> bool:
        """
        Dynamically registers a new MCP tool at runtime using the provided schema.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema dictionary to register.
            is_async (bool): If True, indicates the underlying execution will be asynchronous.

        Returns:
            bool: True if the tool was registered successfully, False otherwise.
        """

        logging.info("Attempting to dynamically register MCP tool at runtime (V4).")

        # Perform enhanced validation
        if not self._perform_enhanced_validation(tool_schema):
            return False


        # Load the tool into the registry
        success = self.registry.load_tool(tool_schema)

        if success:
            tool_name = tool_schema.get("name", "Unknown")

            # Additional logic: explicitly track or handle async designation in schema
            # for ConcurrentSkillExecutor to optimize or for wrapper creation.
            tool_schema["__is_async__"] = is_async

            logging.info(f"Dynamically registered tool (V4): {tool_name}, is_async={is_async}")
        else:
            logging.error("Failed to dynamically register tool (V4).")

        return success
