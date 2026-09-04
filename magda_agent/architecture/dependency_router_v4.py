"""
Magentic-One Task Dependency Resolution Engine v4.

Inspired by Magentic-One and Agent Teams: Implements an orchestration router
component that topologically sorts DAG-based execution plans and routes independent
sub-tasks concurrently to subagents in isolated git worktrees.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class DAGTaskNode:
    """Represents a discrete node in a DAG execution plan."""

    task_id: str
    name: str
    assigned_role: str = "coder"
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    worktree_isolation: bool = True
    status: str = "pending"  # "pending", "running", "completed", "failed", "skipped"
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    worktree_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAGTaskNode":
        # Handle aliases
        t_id = data.get("task_id") or data.get("id") or str(uuid.uuid4())
        name = data.get("name") or data.get("title") or data.get("description") or t_id
        role = data.get("assigned_role") or data.get("role") or data.get("worker") or "coder"
        deps = data.get("dependencies") or data.get("deps") or []
        params = data.get("parameters") or data.get("args") or data.get("params") or {}
        iso = data.get("worktree_isolation", True)

        return cls(
            task_id=t_id,
            name=name,
            assigned_role=role,
            dependencies=deps,
            parameters=params,
            worktree_isolation=iso,
        )


class DAGCycleDetectedError(ValueError):
    """Raised when a cyclical dependency is discovered in the task DAG."""
    pass


class MagenticOneDependencyRouterV4:
    """
    Dependency Resolution Engine & Orchestration Router V4.
    Computes topological sorts and execution waves for DAG execution plans,
    routing independent tasks in parallel to isolated worker subagents.
    """

    def __init__(
        self,
        subagent_dispatcher: Optional[Callable[[DAGTaskNode, Dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
        max_concurrency: int = 8,
    ) -> None:
        self.subagent_dispatcher = subagent_dispatcher
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)

    @staticmethod
    def topological_sort(tasks: List[DAGTaskNode]) -> List[DAGTaskNode]:
        """
        Computes a linear topological sort of tasks using Kahn's algorithm.
        Raises DAGCycleDetectedError if a cycle exists.
        """
        task_map: Dict[str, DAGTaskNode] = {t.task_id: t for t in tasks}
        in_degree: Dict[str, int] = {t.task_id: 0 for t in tasks}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        for t in tasks:
            for dep in t.dependencies:
                if dep in task_map:
                    adj_list[dep].append(t.task_id)
                    in_degree[t.task_id] += 1
                else:
                    logger.warning(f"Dependency '{dep}' for task '{t.task_id}' not found in task graph.")

        queue: deque[str] = deque([node for node, deg in in_degree.items() if deg == 0])
        sorted_nodes: List[DAGTaskNode] = []

        while queue:
            node_id = queue.popleft()
            sorted_nodes.append(task_map[node_id])

            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(task_map):
            raise DAGCycleDetectedError("Cycle detected in task dependencies DAG.")

        return sorted_nodes

    @classmethod
    def compute_execution_waves(cls, tasks: List[DAGTaskNode]) -> List[List[DAGTaskNode]]:
        """
        Groups tasks into discrete execution waves.
        Wave 0 contains all tasks with no dependencies.
        Wave N contains all tasks whose dependencies were satisfied by waves 0..N-1.
        All tasks within a single wave can be executed concurrently in parallel.
        """
        task_map: Dict[str, DAGTaskNode] = {t.task_id: t for t in tasks}
        in_degree: Dict[str, int] = {t.task_id: len([d for d in t.dependencies if d in task_map]) for t in tasks}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        for t in tasks:
            for dep in t.dependencies:
                if dep in task_map:
                    adj_list[dep].append(t.task_id)

        waves: List[List[DAGTaskNode]] = []
        current_wave_ids = [t_id for t_id, deg in in_degree.items() if deg == 0]
        processed_count = 0

        while current_wave_ids:
            wave_nodes = [task_map[t_id] for t_id in current_wave_ids]
            waves.append(wave_nodes)
            processed_count += len(wave_nodes)

            next_wave_ids: List[str] = []
            for node_id in current_wave_ids:
                for neighbor in adj_list[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_wave_ids.append(neighbor)

            current_wave_ids = next_wave_ids

        if processed_count != len(task_map):
            raise DAGCycleDetectedError("Cycle detected in task dependencies during wave resolution.")

        return waves

    async def _execute_single_task(
        self,
        task: DAGTaskNode,
        upstream_artifacts: Dict[str, Any],
        global_context: Dict[str, Any],
    ) -> DAGTaskNode:
        """Executes an individual task node using the subagent dispatcher."""
        task.status = "running"
        task.started_at = time.time()
        if task.worktree_isolation:
            task.worktree_path = f"/tmp/worktrees/{task.task_id}_{task.assigned_role}"

        # Combine parameters with upstream artifacts
        execution_context = {
            "global_context": global_context,
            "upstream_artifacts": upstream_artifacts,
            "worktree_path": task.worktree_path,
        }

        async with self.semaphore:
            try:
                if self.subagent_dispatcher:
                    res = await self.subagent_dispatcher(task, execution_context)
                else:
                    # Default mock execution
                    await asyncio.sleep(0.005)
                    res = f"Completed {task.name} ({task.task_id}) via {task.assigned_role}"

                task.result = res
                task.status = "completed"
                task.completed_at = time.time()
            except Exception as e:
                logger.error(f"Task '{task.name}' ({task.task_id}) execution failed: {e}")
                task.status = "failed"
                task.error = str(e)
                task.completed_at = time.time()

        return task

    async def route_and_execute_dag(
        self,
        plan: Union[List[Dict[str, Any]], List[DAGTaskNode]],
        global_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolves DAG dependencies into parallel execution waves and runs them concurrently.
        Propagates intermediate artifacts between dependent task stages.
        """
        # Parse inputs
        task_nodes: List[DAGTaskNode] = []
        for item in plan:
            if isinstance(item, DAGTaskNode):
                task_nodes.append(item)
            elif isinstance(item, dict):
                task_nodes.append(DAGTaskNode.from_dict(item))

        if not task_nodes:
            return {
                "status": "completed",
                "total_tasks": 0,
                "completed_count": 0,
                "failed_count": 0,
                "waves_count": 0,
                "results": {},
            }

        # 1. Compute execution waves
        waves = self.compute_execution_waves(task_nodes)
        global_context = global_context or {}

        artifacts: Dict[str, Any] = {}
        failed_task_ids: Set[str] = set()

        # 2. Execute wave by wave
        for wave_idx, wave in enumerate(waves):
            logger.info(f"Executing DAG Wave {wave_idx + 1}/{len(waves)} with {len(wave)} concurrent task(s)")

            # Check for tasks with failed dependencies
            runnable_tasks: List[DAGTaskNode] = []
            for t in wave:
                has_failed_dep = any(dep in failed_task_ids for dep in t.dependencies)
                if has_failed_dep:
                    t.status = "skipped"
                    t.error = "Prerequisite dependency failed."
                    failed_task_ids.add(t.task_id)
                else:
                    runnable_tasks.append(t)

            if runnable_tasks:
                tasks_coros = [
                    self._execute_single_task(
                        task=t,
                        upstream_artifacts={dep: artifacts.get(dep) for dep in t.dependencies if dep in artifacts},
                        global_context=global_context,
                    )
                    for t in runnable_tasks
                ]

                results = await asyncio.gather(*tasks_coros)
                for completed_task in results:
                    if completed_task.status == "completed":
                        artifacts[completed_task.task_id] = completed_task.result
                    else:
                        failed_task_ids.add(completed_task.task_id)

        # 3. Compile output summary
        total_completed = sum(1 for t in task_nodes if t.status == "completed")
        total_failed = sum(1 for t in task_nodes if t.status in ("failed", "skipped"))
        overall_status = "completed" if total_failed == 0 else "partial_failure"

        return {
            "status": overall_status,
            "total_tasks": len(task_nodes),
            "completed_count": total_completed,
            "failed_count": total_failed,
            "waves_count": len(waves),
            "artifacts": artifacts,
            "tasks": [t.to_dict() for t in task_nodes],
            "results": {t.task_id: t.result for t in task_nodes if t.status == "completed"},
        }
