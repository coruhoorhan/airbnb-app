import logging
from typing import Dict, Any, List, Callable

class MCPRegistrationError(ValueError):
    """
    Raised when an MCP tool fails schema validation or interceptor checks during registration.
    """
    pass

class MCPRegistry:
    """
    Registry specialized in handling tools exported via the Model Context Protocol (MCP).
    """

    def __init__(self) -> None:
        """Initialize the MCP Registry."""
        self.mcp_tools: Dict[str, Dict[str, Any]] = {}
        self._interceptors: List[Callable[[Dict[str, Any]], None]] = []

        # Automatically register the default schema validation interceptor
        from magda_agent.skills.mcp_validator import MCPActionToolValidator
        self._interceptors.append(MCPActionToolValidator.validate_schema)

    def add_interceptor(self, interceptor: Callable[[Dict[str, Any]], None]) -> None:
        """
        Dynamically registers a new interceptor to the MCPRegistry.

        Args:
            interceptor (Callable[[Dict[str, Any]], None]): The interceptor function.
        """
        if not hasattr(self, "_interceptors"):
            self._interceptors = []
        self._interceptors.append(interceptor)

    def load_tool(self, tool_schema: Dict[str, Any]) -> bool:
        """
        Dynamically loads and verifies an external MCP tool schema.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema dictionary.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        # Perform basic schema verification first to maintain backward compatibility
        if not self._is_valid_schema(tool_schema):
            logging.error(f"Failed to load MCP tool: Invalid schema {tool_schema}")
            return False

        if not hasattr(self, "_interceptors"):
            from magda_agent.skills.mcp_validator import MCPActionToolValidator
            self._interceptors = [MCPActionToolValidator.validate_schema]

        import jsonschema
        # Run all registered interceptors next
        for interceptor in self._interceptors:
            try:
                interceptor(tool_schema)
            except jsonschema.exceptions.ValidationError as e:
                raise MCPRegistrationError(f"Schema validation failed: {e}") from e
            except Exception as e:
                raise MCPRegistrationError(f"Registration interceptor error: {e}") from e

        name: str = tool_schema["name"]
        self.mcp_tools[name] = tool_schema
        logging.info(f"Successfully loaded MCP tool: {name}")
        return True

    def _is_valid_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Verifies if the schema complies with MCP tool standards.

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

        return True

    def get_tool(self, name: str) -> Dict[str, Any]:
        """
        Retrieve a loaded MCP tool by name.

        Args:
            name (str): The name of the MCP tool.

        Returns:
            Dict[str, Any]: The tool schema, or empty dict if not found.
        """
        return self.mcp_tools.get(name, {})

    def list_tools(self) -> List[str]:
        """
        List all available MCP tools.

        Returns:
            List[str]: A list of tool names.
        """
        return list(self.mcp_tools.keys())

    def reload_tool(self, tool_schema: Dict[str, Any]) -> bool:
        """
        Dynamically hot-reloads an MCP tool configuration.

        Args:
            tool_schema (Dict[str, Any]): The updated MCP tool schema dictionary.

        Returns:
            bool: True if reloaded successfully, False otherwise.
        """
        if not isinstance(tool_schema, dict) or "name" not in tool_schema:
            logging.error(f"Failed to reload MCP tool: Invalid schema {tool_schema}")
            return False

        name = tool_schema["name"]

        if name in self.mcp_tools:
            self.unload_tool(name)
            logging.info(f"Unloaded existing MCP tool for reload: {name}")

        success = self.load_tool(tool_schema)
        if success:
            logging.info(f"Successfully hot-reloaded MCP tool: {name}")
        else:
            logging.error(f"Failed to load MCP tool during reload: {name}")
        return success

    def unload_tool(self, name: str) -> bool:
        """
        Dynamically unregisters and removes an MCP tool from the registry.

        Args:
            name (str): The name of the MCP tool to unload.

        Returns:
            bool: True if the tool was successfully unloaded, False if not found.
        """
        if name in self.mcp_tools:
            del self.mcp_tools[name]
            logging.info(f"Successfully unloaded MCP tool: {name}")
            return True
        logging.warning(f"Failed to unload MCP tool: {name} not found in registry.")
        return False
