import logging
from typing import Dict, Any
import httpx

class MCPEvaluatorPluginV2:
    """
    Evaluator plugin that evaluates new skills against an MCP dynamic verification sandbox.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        """
        Initialize the MCPEvaluatorPluginV2.

        Args:
            timeout (float): The HTTP request timeout in seconds.
        """
        self.timeout = timeout

    async def evaluate_skill(self, tool_schema: Dict[str, Any], sandbox_url: str) -> Dict[str, Any]:
        """
        Evaluates a skill schema against an MCP dynamic verification sandbox.

        Args:
            tool_schema (Dict[str, Any]): The MCP tool schema to evaluate.
            sandbox_url (str): The URL of the dynamic verification sandbox.

        Returns:
            Dict[str, Any]: The evaluation result, or an error dictionary if it fails.
        """
        if not self._is_valid_schema(tool_schema):
            error_msg = f"Invalid schema format: {tool_schema}"
            logging.error(error_msg)
            return {"status": "error", "message": error_msg}

        payload = {
            "schema": tool_schema,
            "action": "evaluate"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(sandbox_url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error occurred during evaluation: {e.response.status_code}"
            logging.error(error_msg)
            return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Failed to evaluate skill at {sandbox_url}: {str(e)}"
            logging.error(error_msg)
            return {"status": "error", "message": error_msg}

    def _is_valid_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Verifies if the schema complies with basic MCP tool standards.

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
