import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

from magda_agent.skills.mcp_registry import MCPRegistry

class MCPRegistrySync:
    """
    Background loop that periodically polls a configured MCP server URL
    and dynamically registers or unregisters tools in the local MCPRegistry.
    """

    def __init__(self, registry: MCPRegistry, mcp_server_url: str, sync_interval: int = 60) -> None:
        """
        Initialize the MCPRegistrySync.

        Args:
            registry (MCPRegistry): The local registry to keep synchronized.
            mcp_server_url (str): The remote MCP server URL to poll for tools.
            sync_interval (int): Time in seconds between polling attempts. Defaults to 60.
        """
        self.registry = registry
        self.mcp_server_url = mcp_server_url
        self.sync_interval = sync_interval
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self.logger = logging.getLogger(__name__)

    async def _sync_loop(self) -> None:
        """
        The main background loop that periodically synchronizes the registry.
        """
        while self._running:
            await self.sync_once()
            if self._running:
                try:
                    await asyncio.sleep(self.sync_interval)
                except asyncio.CancelledError:
                    break

    async def sync_once(self) -> None:
        """
        Performs a single synchronization cycle by querying the remote MCP server.
        """
        self.logger.debug(f"Starting sync cycle with MCP server: {self.mcp_server_url}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.mcp_server_url}/tools")
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as e:
            self.logger.error(f"Failed to fetch tools from MCP server {self.mcp_server_url}: Network error: {e}")
            return
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Failed to fetch tools from MCP server {self.mcp_server_url}: HTTP error {e.response.status_code}")
            return
        except Exception as e:
            self.logger.error(f"Failed to fetch tools from MCP server {self.mcp_server_url}: {e}")
            return

        if not isinstance(data, dict) or "tools" not in data or not isinstance(data["tools"], list):
            self.logger.error(f"Invalid response format from MCP server {self.mcp_server_url}: 'tools' list not found.")
            return

        remote_tools: Dict[str, Dict[str, Any]] = {}
        for tool in data["tools"]:
            if isinstance(tool, dict) and "name" in tool:
                remote_tools[tool["name"]] = tool

        local_tools_names = set(self.registry.list_tools())
        remote_tools_names = set(remote_tools.keys())

        # Tools to add or update
        for name, tool_schema in remote_tools.items():
            if name not in local_tools_names:
                # Add new tool
                try:
                    success = self.registry.load_tool(tool_schema)
                    if not success:
                        self.logger.warning(f"Failed to load new MCP tool: {name}")
                except Exception as e:
                     self.logger.error(f"Error loading new MCP tool {name}: {e}")
            else:
                # Tool already exists, we might need to update it (reload)
                # To simplify, we'll reload it to ensure we have the latest schema
                try:
                     self.registry.reload_tool(tool_schema)
                except Exception as e:
                     self.logger.error(f"Error reloading existing MCP tool {name}: {e}")


        # Tools to remove
        tools_to_remove = local_tools_names - remote_tools_names
        for name in tools_to_remove:
             try:
                 self.registry.unload_tool(name)
                 self.logger.info(f"Unloaded MCP tool {name} as it is no longer present on the remote server.")
             except Exception as e:
                 self.logger.error(f"Error unloading MCP tool {name}: {e}")


    def start(self) -> None:
        """
        Starts the background synchronization loop.
        """
        if self._running:
            self.logger.warning("Sync loop is already running.")
            return

        self._running = True
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._sync_loop())
        self.logger.info(f"Started MCPRegistrySync loop with interval {self.sync_interval}s.")

    async def stop(self) -> None:
        """
        Stops the background synchronization loop.
        """
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.logger.info("Stopped MCPRegistrySync loop.")
