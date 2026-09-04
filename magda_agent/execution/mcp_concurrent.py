import asyncio
import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

class MCPConcurrentExecutor:
    """
    A specialized concurrency module designed for running multiple
    MCP action tools in parallel without blocking the event loop.
    """

    def __init__(self) -> None:
        """Initializes the MCPConcurrentExecutor."""
        pass

    async def execute_tools_concurrently(self, tasks: List[Tuple[Callable[..., Any], Dict[str, Any]]]) -> List[Any]:
        """
        Executes a list of asynchronous tool functions concurrently.

        Args:
            tasks: A list of tuples, where each tuple contains an async callable
                   and a dictionary of kwargs to pass to that callable.

        Returns:
            A list containing the results of the tool executions in the same order
            as the input tasks. Exceptions raised by individual tools will be
            returned as Exception objects in the list rather than crashing the loop.
        """
        coroutines = []
        for func, kwargs in tasks:
            coroutines.append(func(**kwargs))

        logger.info(f"Executing {len(coroutines)} MCP tools concurrently.")

        # Use return_exceptions=True so one failing tool doesn't abort the others
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return list(results)
