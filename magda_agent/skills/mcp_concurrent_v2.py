"""
MCP Concurrent Execution v2

This module provides support for executing multiple independent Model Context Protocol (MCP)
action tools concurrently, inspired by OpenAI Agents SDK capabilities.
"""

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional

class MCPConcurrentExecutorV2:
    """
    Executes multiple independent MCP tools concurrently using asyncio.gather.
    """
    def __init__(self, max_concurrency: Optional[int] = None):
        """
        Initialize the executor.

        Args:
            max_concurrency: Optional maximum number of concurrent tasks. If None, unlimited.
        """
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency else None

    async def execute_tools(self, tools: List[Callable[..., Coroutine[Any, Any, Any]]], kwargs_list: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute a list of MCP tools concurrently.

        Args:
            tools: List of async tool functions to execute.
            kwargs_list: List of keyword arguments corresponding to each tool.

        Returns:
            List of results corresponding to the tools executed.

        Raises:
            ValueError: If lengths of tools and kwargs_list do not match.
        """
        if len(tools) != len(kwargs_list):
            raise ValueError("Lengths of tools and kwargs_list must match.")

        if self._semaphore:
            async def _run_with_semaphore(tool: Callable, kwargs: Dict[str, Any]) -> Any:
                async with self._semaphore:
                    return await tool(**kwargs)
            tasks = [_run_with_semaphore(tool, kwargs) for tool, kwargs in zip(tools, kwargs_list)]
        else:
            tasks = [tool(**kwargs) for tool, kwargs in zip(tools, kwargs_list)]

        return await asyncio.gather(*tasks, return_exceptions=True)
