"""
Claude Subagent Dependency Graph V2.

Inspired by Claude Agent SDK Task system with dependency graphs:
Provides a robust DAG execution and validation engine for sub-agent teams,
calculating topological sort orders, parallel task stages, detecting cyclic deadlocks,
and tracking incremental execution state.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class DependencyGraphError(Exception):
    """Raised when dependency graph validation fails or cycles are detected."""
    pass


@dataclass
class SubagentTaskNode:
    """Represents a discrete task node in the sub-agent dependency graph."""

    id: str
    name: str = ""
    dependencies: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentTaskNode":
        t_id = str(data.get("id") or data.get("task_id") or f"task_{uuid.uuid4().hex[:8]}")
        return cls(
            id=t_id,
            name=str(data.get("name") or data.get("title") or t_id),
            dependencies=[str(d) for d in (data.get("dependencies") or [])],
            assigned_agent=data.get("assigned_agent") or data.get("agent_id"),
            status=str(data.get("status") or "pending"),
            output=data.get("output"),
            error=data.get("error"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class DependencyGraphValidationResult:
    """Outcome of validating a sub-agent task dependency graph."""

    is_valid: bool
    has_cycles: bool = False
    topological_order: List[str] = field(default_factory=list)
    parallel_waves: List[List[str]] = field(default_factory=list)
    missing_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ClaudeSubagentDependencyGraphV2:
    """
    Claude Subagent Dependency Graph V2.

    Validates, optimizes, and coordinates the execution order of subagent tasks.
    """

    def __init__(self):
        self._tasks: Dict[str, SubagentTaskNode] = {}
        self._completed_ids: Set[str] = set()
        self._failed_ids: Set[str] = set()

    def add_task(
        self,
        task_id: str,
        name: str = "",
        dependencies: Optional[List[str]] = None,
        assigned_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubagentTaskNode:
        """Add an individual task node to the graph."""
        node = SubagentTaskNode(
            id=task_id,
            name=name or task_id,
            dependencies=list(dependencies or []),
            assigned_agent=assigned_agent,
            metadata=metadata or {},
        )
        self._tasks[task_id] = node
        return node

    def add_tasks(self, tasks: List[Union[SubagentTaskNode, Dict[str, Any]]]) -> None:
        """Add a batch of tasks to the graph."""
        for t in tasks:
            if isinstance(t, SubagentTaskNode):
                self._tasks[t.id] = t
            elif isinstance(t, dict):
                node = SubagentTaskNode.from_dict(t)
                self._tasks[node.id] = node

    def get_task(self, task_id: str) -> Optional[SubagentTaskNode]:
        """Fetch task node by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[SubagentTaskNode]:
        """Fetch all registered task nodes."""
        return list(self._tasks.values())

    def validate_graph(self) -> DependencyGraphValidationResult:
        """
        Validate graph structure:
        - Detect missing dependencies
        - Detect cyclic dependencies
        - Calculate topological execution order and parallel stages
        """
        errors = []
        missing = defaultdict(list)

        # 1. Check for missing dependencies
        for tid, task in self._tasks.items():
            for dep in task.dependencies:
                if dep not in self._tasks:
                    missing[tid].append(dep)
                    errors.append(f"Task '{tid}' references non-existent dependency '{dep}'.")

        # 2. Build adjacency graph and compute in-degrees for Kahn's algorithm
        adj = defaultdict(list)
        in_degree = {tid: 0 for tid in self._tasks}

        for tid, task in self._tasks.items():
            for dep in task.dependencies:
                if dep in self._tasks:
                    adj[dep].append(tid)
                    in_degree[tid] += 1

        # Kahn's algorithm with wave generation
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        topological_order = []
        waves = []

        visited_count = 0
        while queue:
            wave = []
            level_size = len(queue)
            for _ in range(level_size):
                curr = queue.popleft()
                wave.append(curr)
                topological_order.append(curr)
                visited_count += 1

                for nxt in adj[curr]:
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        queue.append(nxt)
            waves.append(wave)

        has_cycles = visited_count < len(self._tasks)
        if has_cycles:
            errors.append(
                f"Cyclic dependency detected: only {visited_count}/{len(self._tasks)} tasks could be ordered."
            )

        is_valid = len(errors) == 0 and not has_cycles

        return DependencyGraphValidationResult(
            is_valid=is_valid,
            has_cycles=has_cycles,
            topological_order=topological_order if is_valid else [],
            parallel_waves=waves if is_valid else [],
            missing_dependencies=dict(missing),
            errors=errors,
        )

    def get_next_executable_tasks(
        self,
        completed_ids: Optional[Set[str]] = None,
    ) -> List[SubagentTaskNode]:
        """
        Return tasks ready for execution (all dependencies completed, not currently done/failed).
        """
        done = completed_ids if completed_ids is not None else self._completed_ids
        executable = []

        for tid, task in self._tasks.items():
            if tid in done or task.status in ("completed", "failed", "in_progress"):
                continue

            # Check if all dependencies are in completed set
            if all(dep in done for dep in task.dependencies):
                executable.append(task)

        return executable

    def mark_task_in_progress(self, task_id: str) -> None:
        """Set task state to in_progress."""
        if task_id in self._tasks:
            self._tasks[task_id].status = "in_progress"

    def mark_task_completed(self, task_id: str, output: Any = None) -> None:
        """Mark task as successfully finished."""
        if task_id in self._tasks:
            self._tasks[task_id].status = "completed"
            self._tasks[task_id].output = output
            self._completed_ids.add(task_id)

    def mark_task_failed(self, task_id: str, error: str = "") -> None:
        """Mark task as failed."""
        if task_id in self._tasks:
            self._tasks[task_id].status = "failed"
            self._tasks[task_id].error = error
            self._failed_ids.add(task_id)

    def is_complete(self) -> bool:
        """Check if all tasks in graph are completed."""
        return len(self._completed_ids) == len(self._tasks) and len(self._tasks) > 0

    async def execute_subagent_pipeline_async(
        self,
        subagent_executor: Callable[[SubagentTaskNode], Coroutine[Any, Any, Any]],
    ) -> Dict[str, Any]:
        """
        Execute sub-agent pipeline respecting dependency graph waves concurrently.
        """
        val = self.validate_graph()
        if not val.is_valid:
            raise DependencyGraphError(f"Cannot execute invalid dependency graph: {val.errors}")

        results = {}

        for wave in val.parallel_waves:
            # Execute tasks in current wave concurrently
            async def run_task(tid: str):
                task = self._tasks[tid]
                self.mark_task_in_progress(tid)
                try:
                    out = await subagent_executor(task)
                    self.mark_task_completed(tid, out)
                    return tid, out, None
                except Exception as ex:
                    self.mark_task_failed(tid, str(ex))
                    return tid, None, str(ex)

            wave_results = await asyncio.gather(*(run_task(tid) for tid in wave))
            for tid, out, err in wave_results:
                results[tid] = {"output": out, "error": err, "status": self._tasks[tid].status}

        return results

    def reset_execution_state(self) -> None:
        """Reset execution progress."""
        self._completed_ids.clear()
        self._failed_ids.clear()
        for t in self._tasks.values():
            t.status = "pending"
            t.output = None
            t.error = None
