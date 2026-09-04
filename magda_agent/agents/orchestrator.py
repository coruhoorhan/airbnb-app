import asyncio
import logging
from typing import Any, Dict, List, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    A multi-agent orchestrator that supports dynamically scaling up
    sub-agents for parallel processing, inspired by Hermes Agent.
    """

    def __init__(self, agent_spawner: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None) -> None:
        """
        Initialize the multi-agent orchestrator.

        Args:
            agent_spawner: A factory function that takes a task definition (Dict)
                           and returns a coroutine executing that task. If None,
                           tasks must provide their own execution context or
                           be mocked.
        """
        self.agent_spawner = agent_spawner

    async def _execute_single_task(self, task: Dict[str, Any]) -> Any:
        """
        Executes a single task using the agent spawner.

        Args:
            task: A dictionary containing task parameters.

        Returns:
            The result of the task execution.
        """
        if self.agent_spawner:
            return await self.agent_spawner(task)
        else:
            # Fallback if no spawner is provided (e.g., for simple tests)
            logger.warning("No agent_spawner configured, returning task id.")
            # Simulate a quick async operation
            await asyncio.sleep(0.01)
            return {"status": "completed", "task_id": task.get("id")}

    async def run_parallel_tasks(self, tasks: List[Dict[str, Any]], timeout: float = 10.0) -> List[Any]:
        """
        Executes a list of tasks in parallel with a timeout mechanism.

        Args:
            tasks: A list of task dictionaries.
            timeout: The maximum time (in seconds) allowed for all tasks to complete.

        Returns:
            A list of results from the executed tasks. If a task exceeds the
            timeout, an asyncio.TimeoutError is raised for the entire batch.

        Raises:
            asyncio.TimeoutError: If the entire batch of tasks exceeds the timeout.
            Exception: Any exception raised by individual tasks is propagated.
        """
        if not tasks:
            return []

        # Create coroutines for all tasks
        coroutines = [self._execute_single_task(task) for task in tasks]

        logger.info(f"Orchestrator scaling up to process {len(tasks)} parallel tasks.")

        try:
            # Run tasks concurrently, enforcing the overall timeout
            results = await asyncio.wait_for(asyncio.gather(*coroutines), timeout=timeout)
            logger.info("All parallel tasks completed successfully.")
            return list(results)
        except asyncio.TimeoutError:
            logger.error(f"Parallel task execution exceeded timeout of {timeout}s.")
            raise
        except Exception as e:
            logger.error(f"Error during parallel execution: {e}")
            raise
