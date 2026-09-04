import logging
import os
import inspect
from typing import Dict, Any, List, Protocol, runtime_checkable
from magda_agent.teams.mcp_isolation_v5 import MCPIsolationManagerV5

@runtime_checkable
class MCPActionAdapter(Protocol):
    """
    Protocol for dynamically providing external MCP action tools to the registry.
    """
    async def fetch_action_tools(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of MCP action tool schemas from an external source asynchronously.

        Returns:
            List[Dict[str, Any]]: A list of action tool schemas.
        """
        ...

class MCPRegistryV7:
    """
    Registry specialized in handling action tools exported via the Model Context Protocol (MCP) version 7.
    Allows for dynamic synchronization of action tools from registered adapters.
    """

    def __init__(self, base_repo_path: str | None = None) -> None:
        """Initialize the MCP Registry V7 for action tools."""
        self.mcp_tools: Dict[str, Dict[str, Any]] = {}
        self.adapters: List[MCPActionAdapter] = []

        # Use provided base_repo_path, or attempt to find the git root, or fallback to current dir
        if base_repo_path is None:
            base_repo_path = os.getcwd()

        self.isolation_manager = MCPIsolationManagerV5(base_repo_path=base_repo_path)

    def register_tool(self, schema: Dict[str, Any]) -> bool:
        """
        Alias for load_action_tool for backward compatibility.

        Args:
            schema (Dict[str, Any]): The MCP tool schema dictionary.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        return self.load_action_tool(schema)

    def list_tools(self) -> List[str]:
        """
        Alias for list_action_tools for backward compatibility.

        Returns:
            List[str]: A list of tool names.
        """
        return self.list_action_tools()

    def unload_tool(self, name: str) -> bool:
        """
        Alias for unload_action_tool for backward compatibility.

        Args:
            name (str): The name of the MCP tool to unload.

        Returns:
            bool: True if the tool was successfully unloaded, False if not found.
        """
        return self.unload_action_tool(name)

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Returns a list of all tools for backward compatibility.

        Returns:
            List[Dict[str, Any]]: A list of all registered tool schemas.
        """
        return [self.mcp_tools[k] for k in self.mcp_tools]

    def get_tool(self, name: str) -> Dict[str, Any]:
        """
        Alias for get_action_tool for backward compatibility.

        Args:
            name (str): The name of the MCP action tool.

        Returns:
            Dict[str, Any]: The tool schema, or an empty dictionary if not found.
        """
        return self.get_action_tool(name)

    def unregister_tool(self, name: str) -> bool:
        """
        Alias for unload_action_tool for backward compatibility.

        Args:
            name (str): The name of the MCP action tool.

        Returns:
            bool: True if the tool was successfully unloaded, False if not found.
        """
        return self.unload_action_tool(name)


    def load_action_tool(self, tool_schema: Dict[str, Any]) -> bool:
        """
        Dynamically loads and verifies an external MCP action tool schema.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema dictionary.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        if not self._is_valid_action_schema(tool_schema):
            logging.error(f"Failed to load MCP action tool: Invalid schema {tool_schema}")
            return False

        name: str = tool_schema["name"]
        self.mcp_tools[name] = tool_schema
        logging.info(f"Successfully loaded MCP action tool: {name}")
        return True

    def _is_valid_action_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Verifies if the schema complies with MCP tool standards for action tools.
        Expects basic MCP fields and possibly action-specific metadata.

        Args:
            schema (Dict[str, Any]): The MCP tool schema.

        Returns:
            bool: True if valid, False otherwise.
        """
        if not isinstance(schema, dict):
            return False

        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in schema or not isinstance(schema[field], str) or not schema[field]:
                return False

        # Validate inputSchema if it exists
        if "inputSchema" in schema and not isinstance(schema["inputSchema"], dict):
            return False

        return True

    def get_action_tool(self, name: str) -> Dict[str, Any]:
        """
        Retrieve a loaded MCP action tool by name.

        Args:
            name (str): The name of the MCP action tool.

        Returns:
            Dict[str, Any]: The tool schema, or an empty dictionary if not found.
        """
        return self.mcp_tools.get(name, {})

    def list_action_tools(self) -> List[str]:
        """
        List all available MCP action tools.

        Returns:
            List[str]: A list of tool names.
        """
        return list(self.mcp_tools.keys())

    def unload_action_tool(self, name: str) -> bool:
        """
        Dynamically unregisters and removes an MCP action tool from the registry.

        Args:
            name (str): The name of the MCP action tool to unload.

        Returns:
            bool: True if the tool was successfully unloaded, False if not found.
        """
        if name in self.mcp_tools:
            del self.mcp_tools[name]
            logging.info(f"Successfully unloaded MCP action tool: {name}")
            return True
        logging.warning(f"Failed to unload MCP action tool: {name} not found in registry.")
        return False

    def register_adapter(self, adapter: MCPActionAdapter) -> None:
        """
        Registers an adapter to dynamically fetch external action tools.

        Args:
            adapter (MCPActionAdapter): The adapter instance providing action tools.
        """
        self.adapters.append(adapter)
        logging.info(f"Registered MCP action adapter: {adapter}")

    async def sync_from_adapters(self) -> int:
        """
        Synchronizes action tools from all registered adapters asynchronously.

        Returns:
            int: The total number of action tools successfully synced and loaded.
        """
        loaded_count = 0
        for adapter in self.adapters:
            try:
                tools = await adapter.fetch_action_tools()
                for tool in tools:
                    if self.load_action_tool(tool):
                        loaded_count += 1
            except Exception as e:
                logging.error(f"Error syncing from action adapter {adapter}: {e}")

        logging.info(f"Synchronized {loaded_count} action tools from adapters.")
        return loaded_count

    def execute_tool(self, name: str, args: Dict[str, Any], auth_token: str | None = None) -> Any:
        """
        Executes a registered MCP action tool within an isolated git worktree,
        and optionally through the Auth Sandbox if available.
        """
        if name not in self.mcp_tools:
            raise Exception(f"Tool {name} not found")

        worktree_path = None
        tool = self.mcp_tools[name]
        requires_isolation = tool.get("requires_isolation", False)

        try:
            if requires_isolation:
                # Create an isolated worktree for the tool execution only if explicitly required
                worktree_path = self.isolation_manager.create_isolated_worktree(name)

            # Pass the isolated worktree directory to the execution context
            # We inject the working directory into the args if the sandbox or function supports it
            exec_args = args.copy()

            if getattr(self, "auth_sandbox", None):
                # Optionally pass cwd if auth_sandbox supports it
                if worktree_path:
                     exec_args["cwd"] = worktree_path
                return self.auth_sandbox.execute_tool(name, exec_args, auth_token)

            # Fallback raw execution mock for non-sandboxed flows
            func = tool.get("func")
            if func:
                sig = inspect.signature(func)
                # Check if the function accepts **kwargs or a specific 'cwd' parameter
                if worktree_path and any(param.kind == inspect.Parameter.VAR_KEYWORD or param.name == "cwd" for param in sig.parameters.values()):
                    exec_args["cwd"] = worktree_path
                return func(**exec_args)

            if worktree_path:
                exec_args["cwd"] = worktree_path
            return {"status": "executed", "name": name, "args": exec_args}

        finally:
            if worktree_path:
                try:
                    self.isolation_manager.cleanup_worktree(worktree_path)
                except Exception as e:
                    logging.error(f"Failed to cleanup isolated worktree for {name}: {e}")

    def clear(self) -> None:
        """
        Clears all loaded action tools and registered adapters from the registry.
        """
        self.mcp_tools.clear()
        self.adapters.clear()
        logging.info("Cleared all MCP action tools and adapters from the registry.")
