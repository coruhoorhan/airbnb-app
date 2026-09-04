import ast
import os
import glob
from typing import Dict, Any, List, Optional
import logging
from magda_agent.skills.mcp_registry_v7 import MCPRegistryV7

class MCPAutoDiscoveryV1:
    """
    Auto-discovery mechanism that scans a directory for Python modules,
    extracts function definitions using AST, converts them to MCP tool schemas,
    and registers them dynamically in the MCPRegistryV7.
    """

    def __init__(self, registry: MCPRegistryV7):
        """
        Initialize the discovery module with a target registry.

        Args:
            registry (MCPRegistryV7): The registry to update.
        """
        self.registry = registry

    def discover_and_register(self, directory: str) -> None:
        """
        Scans a directory for .py files, parses them, and registers tools.

        Args:
            directory (str): The directory path to scan.
        """
        if not os.path.isdir(directory):
            logging.error(f"Discovery directory not found: {directory}")
            return

        for filepath in glob.glob(os.path.join(directory, "**/*.py"), recursive=True):
            self._process_file(filepath)

    def _process_file(self, filepath: str) -> None:
        """
        Parses a single Python file using AST and registers extracted tools.

        Args:
            filepath (str): The path to the Python file.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except Exception as e:
            logging.error(f"Failed to parse file {filepath}: {e}")
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                schema = self._extract_schema_from_function(node)
                if schema:
                    self.registry.register_tool(schema)

    def _extract_schema_from_function(self, node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        """
        Converts an AST FunctionDef node to an MCP tool schema.
        Only considers functions that start with 'mcp_tool_' or have a docstring.
        We require a docstring for the description.

        Args:
            node (ast.FunctionDef): The function definition node.

        Returns:
            Optional[Dict[str, Any]]: The generated schema or None if invalid.
        """
        # Exclude private/magic functions unless explicitly an MCP tool
        if node.name.startswith("_"):
            return None

        # Extract docstring
        docstring = ast.get_docstring(node)
        if not docstring:
            # We require a description for MCP tools
            return None

        # Build schema
        schema: Dict[str, Any] = {
            "name": node.name,
            "description": docstring.strip(),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

        properties = schema["inputSchema"]["properties"]
        required = schema["inputSchema"]["required"]

        # Parse arguments
        args = node.args.args
        defaults = node.args.defaults

        # Number of arguments without defaults
        num_required = len(args) - len(defaults)

        for i, arg in enumerate(args):
            # Skip self/cls
            if arg.arg in ("self", "cls") and i == 0:
                continue

            arg_name = arg.arg

            # Map type hints to JSON schema types (basic mapping)
            arg_type = "string" # Default
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    if arg.annotation.id == "int":
                        arg_type = "integer"
                    elif arg.annotation.id == "float":
                        arg_type = "number"
                    elif arg.annotation.id == "bool":
                        arg_type = "boolean"
                    elif arg.annotation.id in ("list", "List"):
                        arg_type = "array"
                    elif arg.annotation.id in ("dict", "Dict"):
                        arg_type = "object"

            properties[arg_name] = {
                "type": arg_type,
                "description": f"Parameter {arg_name}"
            }

            # Check if required (no default value)
            if i < num_required:
                required.append(arg_name)

        return schema
