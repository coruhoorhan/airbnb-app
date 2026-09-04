import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable

import httpx

from magda_agent.skills.registry import SkillRegistry

class MCPDynamicRegistrationPipeline:
    """
    Pipeline for fetching remote MCP server schemas and registering them
    as native functions dynamically into the local SkillRegistry.
    """

    def __init__(self, registry: SkillRegistry) -> None:
        """
        Initialize the MCPDynamicRegistrationPipeline.

        Args:
            registry (SkillRegistry): The local SkillRegistry to register tools into.
        """
        self.registry = registry
        self.logger = logging.getLogger(__name__)

    def _create_native_proxy(self, mcp_server_url: str, tool_name: str) -> Callable[..., Any]:
        """
        Creates an asynchronous native function proxy that forwards calls to the remote MCP server.

        Args:
            mcp_server_url (str): The base URL of the remote MCP server.
            tool_name (str): The name of the remote tool to call.

        Returns:
            Callable[..., Any]: The native proxy function.
        """
        async def proxy_func(**kwargs: Any) -> Any:
            """
            Native proxy function that forwards execution to the remote MCP server.

            Args:
                **kwargs: The arguments to pass to the remote tool.

            Returns:
                Any: The result from the remote tool execution.
            """
            url = f"{mcp_server_url}/tools/{tool_name}/execute"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json={"arguments": kwargs})
                    response.raise_for_status()
                    data = response.json()
                    return data.get("result", data)
            except Exception as e:
                self.logger.error(f"Error executing remote MCP tool {tool_name} at {mcp_server_url}: {e}")
                return f"Error executing remote MCP tool {tool_name}: {e}"

        # Optionally, one could attach the original signature here, but SkillRegistry
        # normally executes via kwargs unpacking.
        proxy_func.__name__ = tool_name
        return proxy_func

    async def fetch_and_register(self, mcp_server_url: str) -> bool:
        """
        Fetches tools from a remote MCP server and registers them as native skills.

        Args:
            mcp_server_url (str): The base URL of the remote MCP server.

        Returns:
            bool: True if tools were fetched and registered successfully, False otherwise.
        """
        self.logger.info(f"Fetching MCP schemas from {mcp_server_url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{mcp_server_url}/tools")
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch tools from MCP server {mcp_server_url}: {e}")
            return False

        if not isinstance(data, dict) or "tools" not in data or not isinstance(data["tools"], list):
            self.logger.error(f"Invalid response format from MCP server {mcp_server_url}: 'tools' list not found.")
            return False

        success_count = 0
        for tool in data["tools"]:
            if isinstance(tool, dict) and "name" in tool:
                name = tool["name"]
                description = tool.get("description", f"Remote MCP tool: {name}")

                # Create a proxy native function that will call the HTTP endpoint
                proxy_func = self._create_native_proxy(mcp_server_url, name)

                try:
                    self.registry.register_skill(name, proxy_func, description)
                    success_count += 1
                    self.logger.info(f"Registered remote MCP tool {name} as a native skill.")
                except Exception as e:
                    self.logger.error(f"Error registering MCP tool {name}: {e}")

        return success_count > 0
