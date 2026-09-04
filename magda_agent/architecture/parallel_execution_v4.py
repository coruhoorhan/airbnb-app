import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional
from magda_agent.architecture.subagent_spawner_v4 import SubagentSpawnerV4

logger = logging.getLogger(__name__)

class ParallelSubagentManagerV4:
    """
    Manages the concurrent execution of multiple subagents operating in isolated git worktrees.
    Inspired by Agent Teams isolation trend.
    """

    def __init__(self, spawner: Optional[SubagentSpawnerV4] = None) -> None:
        """
        Initialize the ParallelSubagentManagerV4.

        Args:
            spawner: Optional SubagentSpawnerV4 instance. If not provided, a new one is created.
        """
        self.spawner = spawner or SubagentSpawnerV4()

    async def run_parallel_tasks(
        self,
        tasks: List[str],
        base_context: List[Dict[str, Any]],
        agent_executor_factory: Callable[[], Any],
        merge_results: bool = False
    ) -> List[Any]:
        """
        Run multiple tasks concurrently using separate subagents.

        Args:
            tasks: A list of task descriptions.
            base_context: The shared conversation or execution context.
            agent_executor_factory: A callable that returns an agent executor for each task.
            merge_results: Whether to attempt git-level result merging from subagent branches.

        Returns:
            A list containing the results of each subagent's execution, which could include Exception objects if an execution failed.
        """
        async def create_and_spawn(task: str, idx: int) -> Any:
            executor = agent_executor_factory()
            # Use a copy of base_context to prevent race conditions during concurrent mutations
            context_copy = list(base_context)

            # Using unique branch names for isolation and optional merging
            branch_name = None
            if merge_results:
                 branch_name = f"subagent-task-{idx}"

            try:
                result = await self.spawner.spawn_subagent(
                    task_description=task,
                    full_context=context_copy,
                    agent_executor=executor,
                    branch_name=branch_name,
                    merge_results=merge_results
                )
                return result
            except Exception as e:
                logger.error(f"Task '{task}' failed with error: {e}")
                return e

        coroutines = [create_and_spawn(task, idx) for idx, task in enumerate(tasks)]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return list(results)

    def merge_state(self, results: List[Any]) -> Dict[str, Any]:
        """
        Merge state results from multiple subagent executions.

        This assumes results are dictionaries. Exceptions and non-dict results are ignored or handled gracefully.

        Args:
            results: A list of results from run_parallel_tasks.

        Returns:
            A dictionary containing the merged state.
        """
        merged_state: Dict[str, Any] = {}
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Skipping result {idx} due to exception: {result}")
                continue

            if isinstance(result, dict):
                # Basic shallow merge logic
                merged_state.update(result)
            else:
                 logger.debug(f"Result {idx} is not a dictionary. Cannot merge into state.")

        return merged_state
