import asyncio
import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

class MCPBatchingExecutor:
    """
    A concurrent executor tailored for MCP tools that batches requests
    heading to the same server.

    This executor takes a list of tasks, where each task includes the
    server name it targets, the tool function to call, and its arguments.
    It groups the tasks by server and executes them concurrently.
    """

    def __init__(self) -> None:
        """Initializes the MCPBatchingExecutor."""
        pass

    async def execute_in_batches(self, tasks: List[Tuple[str, Callable[..., Any], Dict[str, Any]]]) -> List[Any]:
        """
        Executes a list of asynchronous tool functions, batched by server name.

        Args:
            tasks: A list of tuples, where each tuple contains:
                   - The name of the target server (str)
                   - An async callable (the tool function)
                   - A dictionary of kwargs to pass to that callable

        Returns:
            A list containing the results of the tool executions in the exact same
            order as the input tasks. Exceptions raised by individual tools will be
            returned as Exception objects in the list rather than crashing the loop.
        """
        # Dictionary to hold lists of (original_index, callable, kwargs) per server
        batches: Dict[str, List[Tuple[int, Callable[..., Any], Dict[str, Any]]]] = {}
        for index, (server_name, func, kwargs) in enumerate(tasks):
            if server_name not in batches:
                batches[server_name] = []
            batches[server_name].append((index, func, kwargs))

        logger.info(f"Batched {len(tasks)} tasks into {len(batches)} servers.")

        results: List[Any] = [None] * len(tasks)

        async def execute_server_batch(server_name: str, batch_tasks: List[Tuple[int, Callable[..., Any], Dict[str, Any]]]) -> None:
            """Executes all tasks for a specific server concurrently."""
            coroutines = []
            indices = []
            for original_index, func, kwargs in batch_tasks:
                coroutines.append(func(**kwargs))
                indices.append(original_index)

            # Use return_exceptions=True so one failing tool doesn't abort the others
            batch_results = await asyncio.gather(*coroutines, return_exceptions=True)

            for original_index, result in zip(indices, batch_results):
                results[original_index] = result

        # Execute all server batches concurrently
        server_batch_coroutines = [
            execute_server_batch(server_name, batch_tasks)
            for server_name, batch_tasks in batches.items()
        ]

        await asyncio.gather(*server_batch_coroutines)

        return results
