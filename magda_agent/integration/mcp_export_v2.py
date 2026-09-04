import inspect
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from magda_agent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

class MCPExporterV2:
    """
    MCP Server adapter for Magda's SkillRegistry.
    Converts Magda skills into standard MCP tools, and provides a standard JSON-RPC 2.0 interface.
    """
    def __init__(self, registry: SkillRegistry) -> None:
        """
        Initializes the MCP Exporter with a given SkillRegistry.

        Args:
            registry (SkillRegistry): The registry containing skills to export.
        """
        self.registry = registry

    def _get_json_schema(self, func: Callable[..., Any]) -> Dict[str, Any]:
        """
        Extracts JSON schema parameters from the function signature.

        Args:
            func (Callable): The function to extract the schema from.

        Returns:
            Dict[str, Any]: A JSON schema representation of the function's parameters.
        """
        if hasattr(func, "__mcp_schema__"):
            return getattr(func, "__mcp_schema__")

        sig = inspect.signature(func)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for name, param in sig.parameters.items():
            if name in ('self', 'kwargs', 'args'):
                continue

            param_type = "string"
            if param.annotation is not inspect.Parameter.empty:
                if param.annotation is int:
                    param_type = "integer"
                elif param.annotation is float:
                    param_type = "number"
                elif param.annotation is bool:
                    param_type = "boolean"
                elif param.annotation is str:
                    param_type = "string"
                elif param.annotation is list or getattr(param.annotation, '__origin__', None) is list or param.annotation is List:
                    param_type = "array"
                elif param.annotation is dict or getattr(param.annotation, '__origin__', None) is dict or param.annotation is Dict:
                    param_type = "object"

            properties[name] = {"type": param_type}

            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Lists all registered skills as MCP-compatible tool definitions.

        Returns:
            List[Dict[str, Any]]: A list of tool definition dictionaries.
        """
        tools = []
        for name, func in self.registry.skills.items():
            description = self.registry.descriptions.get(name, "")
            schema = self._get_json_schema(func)
            tools.append({
                "name": name,
                "description": description,
                "inputSchema": schema
            })
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes a skill via the MCP protocol format. Awaits if the underlying skill is async.

        Args:
            name (str): The name of the tool/skill to call.
            arguments (Dict[str, Any]): The arguments to pass to the tool.

        Returns:
            Dict[str, Any]: The result of the tool execution in MCP format.
        """
        if not self.registry.has_skill(name):
            logger.warning("Attempted to call missing tool: %s", name)
            return {
                "content": [{"type": "text", "text": f"Error: Tool '{name}' not found."}],
                "isError": True
            }

        try:
            result = self.registry.execute_skill(name, **arguments)
            if inspect.isawaitable(result):
                result = await result
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False
            }
        except Exception as e:
            logger.error("Error executing tool %s: %s", name, e)
            return {
                "content": [{"type": "text", "text": f"Error executing tool {name}: {e}"}],
                "isError": True
            }

    async def handle_rpc_request(self, request: Any) -> Dict[str, Any]:
        """
        Handles a JSON-RPC 2.0 formatted request mapping to MCP tools.
        Supported methods:
        - "tools/list"
        - "tools/call"

        Args:
            request (Dict[str, Any]): The parsed JSON-RPC request.

        Returns:
            Dict[str, Any]: The JSON-RPC response.
        """
        if not isinstance(request, dict):
            return self._build_error(None, -32600, "Invalid Request: Expected a JSON object")

        if "jsonrpc" not in request or request["jsonrpc"] != "2.0":
            return self._build_error(request.get("id"), -32600, "Invalid Request: Missing or invalid jsonrpc version")

        method = request.get("method")
        if not method or not isinstance(method, str):
            return self._build_error(request.get("id"), -32600, "Invalid Request: missing or invalid method")

        req_id = request.get("id")

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.list_tools()
                }
            }
        elif method == "tools/call":
            params = request.get("params", {})
            if not isinstance(params, dict):
                return self._build_error(req_id, -32602, "Invalid params: expected a JSON object")

            name = params.get("name")
            if not name or not isinstance(name, str):
                return self._build_error(req_id, -32602, "Invalid params: missing or invalid tool name")

            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}

            tool_result = await self.call_tool(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": tool_result
            }
        else:
            return self._build_error(req_id, -32601, f"Method not found: {method}")

    def _build_error(self, req_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Helper method to construct a JSON-RPC 2.0 error response object.

        Args:
            req_id: The ID of the original request.
            code: The JSON-RPC error code.
            message: The JSON-RPC error message.
            data: Optional additional error data.

        Returns:
            A dictionary representing the JSON-RPC error response.
        """
        error_obj: Dict[str, Any] = {
            "code": code,
            "message": message
        }
        if data is not None:
            error_obj["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": error_obj
        }
