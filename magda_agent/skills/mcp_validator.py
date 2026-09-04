import functools
import jsonschema
import inspect
from typing import Dict, Any, Callable
from magda_agent.skills.mcp_registry import MCPRegistrationError

class MCPActionToolValidator:
    """
    Validates schemas of registered MCP action tools.
    """

    MCP_TOOL_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "inputSchema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["object"]},
                    "properties": {"type": "object"}
                },
                "required": ["type"]
            }
        },
        "required": ["name", "description"]
    }

    @classmethod
    def validate_schema(cls, schema: Dict[str, Any]) -> None:
        """
        Validates the provided schema against the MCP_TOOL_SCHEMA standard.
        Also validates the JSON schema definition in 'inputSchema' if present.

        Args:
            schema (Dict[str, Any]): The MCP tool schema.

        Raises:
            jsonschema.exceptions.ValidationError: If the schema is invalid.
        """
        jsonschema.validate(instance=schema, schema=cls.MCP_TOOL_SCHEMA)

        # Additionally validate the inputSchema to ensure it's a valid JSON schema
        input_schema = schema.get("inputSchema")
        if input_schema is not None:
            try:
                jsonschema.Draft7Validator.check_schema(input_schema)
            except jsonschema.exceptions.SchemaError as e:
                raise jsonschema.exceptions.ValidationError(f"Invalid JSON Schema in inputSchema: {e}") from e

def validate_mcp_tool(func: Callable) -> Callable:
    """
    Decorator that validates an MCP tool schema parameter.
    Assumes the parameter named 'schema' or 'tool_schema' is the schema dictionary.
    """
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        schema = None
        if "schema" in bound_args.arguments:
            schema = bound_args.arguments["schema"]
        elif "tool_schema" in bound_args.arguments:
            schema = bound_args.arguments["tool_schema"]

        if schema is not None:
            MCPActionToolValidator.validate_schema(schema)

        return func(*args, **kwargs)
    return wrapper
