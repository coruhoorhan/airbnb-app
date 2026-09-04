import asyncio
from typing import List, Dict, Any, Callable, Awaitable, Union

class ConcurrentDispatcher:
    """
    Concurrent execution dispatcher for external action tools.
    Allows multiple tool executions to run in parallel using asyncio.gather.
    Isolates errors in individual tools to prevent the entire batch from crashing.
    """

    def __init__(self):
        pass

    async def execute_concurrently(self, tools: List[Dict[str, Any]], executor_func: Union[Callable[[str, Dict[str, Any]], Awaitable[Any]], Callable[[str, Dict[str, Any]], Any]]) -> List[Any]:
        """
        Executes a list of tools concurrently using the provided executor function.

        Args:
            tools: A list of dictionaries, where each dict has at least 'tool_name' and 'arguments'.
            executor_func: An async or sync function that takes a tool_name and its arguments, and returns the execution result.

        Returns:
            A list of execution results, where each result corresponds to the tool in the same position.
            If a tool execution fails, its result will be the exception object or an error dict.
        """
        async def safe_execute(tool):
            try:
                tool_name = tool.get('tool_name')
                arguments = tool.get('arguments', {})
                if asyncio.iscoroutinefunction(executor_func):
                    return await executor_func(tool_name, arguments)
                else:
                    return await asyncio.to_thread(executor_func, tool_name, arguments)
            except Exception as e:
                return e

        tasks = [safe_execute(tool) for tool in tools]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
