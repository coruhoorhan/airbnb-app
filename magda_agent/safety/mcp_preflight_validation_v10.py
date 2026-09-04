"""MCP Action Tool Preflight Validation Layer V10.

Provides strict JSON schema argument type-checking for MCP JSON-RPC action tools
before policy evaluation or tool execution.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional, Tuple, Union
import jsonschema

logger = logging.getLogger(__name__)


class MCPActionToolPreflightValidatorV10:
    """
    Preflight validator specifically for MCP action tools.
    Enforces strict JSON schema argument validation on incoming action tool calls
    before passing them to the policy layer or tool execution layer.
    """

    def __init__(
        self,
        schemas: Optional[Dict[str, Dict[str, Any]]] = None,
        policy_layer: Optional[Any] = None,
        executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> None:
        """
        Initialize the MCPActionToolPreflightValidatorV10.

        Args:
            schemas: Optional dictionary mapping tool names to their JSON schema definitions.
            policy_layer: Optional policy layer instance for evaluation after preflight schema checks.
            executor: Optional tool execution function/callable.
        """
        self.schemas: Dict[str, Dict[str, Any]] = schemas or {}
        self.policy_layer = policy_layer
        self.executor = executor

    def register_tool_schema(self, tool_name: str, schema: Dict[str, Any]) -> None:
        """
        Registers a JSON schema for a specific tool name.

        Args:
            tool_name: The name of the action tool.
            schema: The JSON schema or MCP tool definition containing an 'inputSchema'.
        """
        if "inputSchema" in schema and isinstance(schema["inputSchema"], dict):
            input_schema = schema["inputSchema"]
        else:
            input_schema = schema

        try:
            jsonschema.Draft7Validator.check_schema(input_schema)
        except jsonschema.exceptions.SchemaError as e:
            raise ValueError(f"Invalid JSON Schema for tool '{tool_name}': {e}") from e

        self.schemas[tool_name] = input_schema
        logger.info(f"Registered preflight schema for tool: {tool_name}")

    def validate_args(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates arguments against the registered JSON schema for tool_name.

        Args:
            tool_name: Name of the action tool.
            arguments: Dictionary of arguments supplied for the tool.

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if tool_name not in self.schemas:
            return False, f"Tool '{tool_name}' is not registered in preflight schema registry."

        input_schema = self.schemas[tool_name]
        try:
            jsonschema.validate(instance=arguments, schema=input_schema)
            return True, ""
        except jsonschema.exceptions.ValidationError as e:
            return False, f"Schema validation error for tool '{tool_name}': {e.message}"

    def validate_preflight_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, int, str]:
        """
        Performs full preflight checks: strict schema validation first, then policy evaluation if provided.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool call arguments.

        Returns:
            Tuple[bool, int, str]: (is_allowed, error_code, error_message)
                JSON-RPC error codes:
                -32601: Method/Tool not found
                -32602: Invalid params (Schema validation failure)
                -32000: Policy blocked / Preflight failure
        """
        if tool_name not in self.schemas:
            return False, -32601, f"Method or tool not found: '{tool_name}'."

        is_schema_valid, schema_err = self.validate_args(tool_name, arguments)
        if not is_schema_valid:
            logger.warning(f"Preflight schema validation blocked tool '{tool_name}': {schema_err}")
            return False, -32602, f"Invalid params: {schema_err}"

        # If strict schema validation passes, proceed to policy evaluation if available
        if self.policy_layer is not None:
            try:
                allowed, reason = self.policy_layer.evaluate(tool_name, arguments)
                if not allowed:
                    logger.warning(f"Policy evaluation blocked tool '{tool_name}': {reason}")
                    return False, -32000, f"Policy evaluation blocked execution: {reason}"
            except Exception as e:
                logger.error(f"Error evaluating policy layer for tool '{tool_name}': {e}")
                return False, -32000, f"Policy evaluation failed: {str(e)}"

        return True, 0, ""

    def process_jsonrpc_request(
        self, request: Union[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Intercepts and processes a JSON-RPC request, applying preflight schema validation before policy and execution.

        Args:
            request: JSON string or dictionary representing the JSON-RPC call.

        Returns:
            Dict[str, Any]: Standardized JSON-RPC 2.0 response dictionary.
        """
        if isinstance(request, str):
            try:
                req_dict = json.loads(request)
            except json.JSONDecodeError:
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: Invalid JSON string."},
                }
        elif isinstance(request, dict):
            req_dict = request
        else:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: Payload must be object or JSON string."},
            }

        req_id = req_dict.get("id")
        if req_dict.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: jsonrpc version must be '2.0'."},
            }

        method = req_dict.get("method")
        if not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: 'method' must be a non-empty string."},
            }

        params = req_dict.get("params", {})

        # Distinguish between standard MCP tool calls ("tools/call" or "call_tool") and direct method calls
        if method in ("tools/call", "call_tool"):
            if not isinstance(params, dict):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Invalid params: 'params' must be an object."},
                }
            tool_name = params.get("name")
            if not tool_name or not isinstance(tool_name, str):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Invalid params: 'name' is required for tool calls."},
                }
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Invalid params: 'arguments' must be an object."},
                }
        else:
            tool_name = method
            arguments = params if isinstance(params, dict) else {}

        is_valid, err_code, err_msg = self.validate_preflight_call(tool_name, arguments)
        if not is_valid:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": err_code, "message": err_msg},
            }

        # If preflight checks pass and an executor is provided, execute the tool
        if self.executor is not None:
            try:
                result = self.executor(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result,
                }
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Internal error during execution: {str(e)}"},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"status": "validated", "tool": tool_name, "arguments": arguments},
        }
