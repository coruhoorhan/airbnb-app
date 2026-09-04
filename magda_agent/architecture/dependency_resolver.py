"""
Hierarchical Planner Subagent Dependency Resolver.

Extracts and optimizes logic for grouping independent parallel tasks to be passed
to Magentic-One and hierarchical subagents based on DAG topological sort.
"""

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class PlannerTask:
    """Represents a discrete task item produced by the hierarchical planner."""

    id: str
    title: str = ""
    dependencies: List[str] = field(default_factory=list)
    assigned_subagent: Optional[str] = None
    estimated_duration: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlannerTask":
        t_id = str(data.get("id") or data.get("task_id") or "")
        title = str(data.get("title") or data.get("name") or data.get("description") or t_id)
        deps = list(data.get("dependencies") or data.get("deps") or [])
        subagent = data.get("assigned_subagent") or data.get("subagent") or data.get("role") or data.get("worker")
        duration = float(data.get("estimated_duration", data.get("duration", 1.0)))
        meta = data.get("metadata") or {}

        return cls(
            id=t_id,
            title=title,
            dependencies=deps,
            assigned_subagent=subagent,
            estimated_duration=duration,
            metadata=meta,
        )


class SubagentDependencyResolver:
    """
    Resolves dependency graphs for hierarchical planners, performing topological
    sorting, cycle validation, and parallel execution batching for Magentic-One subagents.
    """

    @classmethod
    def normalize_tasks(cls, tasks: List[Union[Dict[str, Any], PlannerTask]]) -> List[PlannerTask]:
        """Normalizes heterogeneous input into a list of PlannerTask objects."""
        normalized: List[PlannerTask] = []
        for t in tasks:
            if isinstance(t, PlannerTask):
                normalized.append(t)
            elif isinstance(t, dict):
                normalized.append(PlannerTask.from_dict(t))
        return normalized

    @classmethod
    def resolve_dependencies(
        cls,
        tasks: List[Union[Dict[str, Any], PlannerTask]],
    ) -> List[PlannerTask]:
        """
        Topologically sorts the tasks DAG using Kahn's algorithm.
        Raises ValueError if a cycle is detected.
        """
        task_list = cls.normalize_tasks(tasks)
        if not task_list:
            return []

        task_map: Dict[str, PlannerTask] = {t.id: t for t in task_list}
        in_degree: Dict[str, int] = {t.id: 0 for t in task_list}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        for t in task_list:
            for dep in t.dependencies:
                if dep in task_map:
                    adj_list[dep].append(t.id)
                    in_degree[t.id] += 1
                else:
                    logger.warning(f"Dependency '{dep}' for task '{t.id}' not found in task graph.")

        queue: deque[str] = deque([node for node, deg in in_degree.items() if deg == 0])
        sorted_tasks: List[PlannerTask] = []

        while queue:
            node_id = queue.popleft()
            sorted_tasks.append(task_map[node_id])

            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_tasks) != len(task_map):
            raise ValueError("Cycle detected in planner task dependencies")

        return sorted_tasks

    @classmethod
    def group_independent_tasks(
        cls,
        tasks: List[Union[Dict[str, Any], PlannerTask]],
    ) -> List[List[PlannerTask]]:
        """
        Groups independent tasks into parallel execution batches/tiers.
        All tasks within batch k can be safely executed concurrently by subagents.
        """
        task_list = cls.normalize_tasks(tasks)
        if not task_list:
            return []

        task_map: Dict[str, PlannerTask] = {t.id: t for t in task_list}
        in_degree: Dict[str, int] = {t.id: len([d for d in t.dependencies if d in task_map]) for t in task_list}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        for t in task_list:
            for dep in t.dependencies:
                if dep in task_map:
                    adj_list[dep].append(t.id)

        batches: List[List[PlannerTask]] = []
        current_batch_ids = [t_id for t_id, deg in in_degree.items() if deg == 0]
        processed_count = 0

        while current_batch_ids:
            batch_tasks = [task_map[t_id] for t_id in current_batch_ids]
            batches.append(batch_tasks)
            processed_count += len(batch_tasks)

            next_batch_ids: List[str] = []
            for node_id in current_batch_ids:
                for neighbor in adj_list[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_batch_ids.append(neighbor)

            current_batch_ids = next_batch_ids

        if processed_count != len(task_map):
            raise ValueError("Cycle detected in planner task dependencies during batching")

        return batches

    @classmethod
    def get_next_executable_tasks(
        cls,
        tasks: List[Union[Dict[str, Any], PlannerTask]],
        completed_task_ids: Set[str],
    ) -> List[PlannerTask]:
        """
        Returns all tasks that are currently unblocked (all prerequisites completed)
        and have not yet been completed themselves.
        """
        task_list = cls.normalize_tasks(tasks)
        executable: List[PlannerTask] = []

        for t in task_list:
            if t.id in completed_task_ids:
                continue

            all_deps_satisfied = all(dep in completed_task_ids for dep in t.dependencies)
            if all_deps_satisfied:
                executable.append(t)

        return executable

    @classmethod
    def calculate_critical_path(
        cls,
        tasks: List[Union[Dict[str, Any], PlannerTask]],
    ) -> Tuple[List[str], float]:
        """
        Calculates the critical path (longest dependency chain) and total minimum duration.
        """
        sorted_tasks = cls.resolve_dependencies(tasks)
        if not sorted_tasks:
            return [], 0.0

        task_map = {t.id: t for t in sorted_tasks}
        earliest_finish: Dict[str, float] = {}
        predecessor_on_path: Dict[str, Optional[str]] = {}

        for t in sorted_tasks:
            max_prev_finish = 0.0
            best_prev = None
            for dep in t.dependencies:
                if dep in earliest_finish and earliest_finish[dep] > max_prev_finish:
                    max_prev_finish = earliest_finish[dep]
                    best_prev = dep

            earliest_finish[t.id] = max_prev_finish + t.estimated_duration
            predecessor_on_path[t.id] = best_prev

        # Find sink task with maximum finish time
        end_task_id = max(earliest_finish, key=lambda k: earliest_finish[k])
        total_duration = earliest_finish[end_task_id]

        # Reconstruct path
        path = []
        curr: Optional[str] = end_task_id
        while curr:
            path.append(curr)
            curr = predecessor_on_path.get(curr)

        path.reverse()
        return path, total_duration
