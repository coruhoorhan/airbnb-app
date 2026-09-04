"""
Agent Teams Parallel Subagents V6 (Parallel Execution Manager).

Inspired by Agent Teams isolation trends: Implements a parallel execution manager
that spawns, isolates, and coordinates multiple sub-agents running concurrently
in their respective dedicated Git worktrees with strict environment variable isolation
and fault containment.
"""

import asyncio
import inspect
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class SubagentExecutionTaskV6:
    """Specification of a task to be executed by a sub-agent in an isolated worktree."""

    subagent_id: str
    task_name: str
    task_payload: Dict[str, Any] = field(default_factory=dict)
    worktree_path: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentExecutionTaskV6":
        return cls(
            subagent_id=str(data.get("subagent_id") or data.get("agent_id") or f"sub_{uuid.uuid4().hex[:6]}"),
            task_name=str(data.get("task_name") or data.get("title") or "unnamed_task"),
            task_payload=dict(data.get("task_payload") or data.get("payload") or {}),
            worktree_path=data.get("worktree_path"),
            env_vars=dict(data.get("env_vars") or {}),
            timeout_seconds=float(data.get("timeout_seconds", 60.0)),
            task_id=str(data.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"),
        )


@dataclass
class SubagentExecutionOutcomeV6:
    """Outcome of an isolated sub-agent task execution."""

    subagent_id: str
    task_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    worktree_path: str = ""
    isolated_env: Dict[str, str] = field(default_factory=dict)
    timed_out: bool = False
    execution_time_ms: float = 0.0
    task_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "task_name": self.task_name,
            "success": self.success,
            "output": str(self.output) if self.output is not None else None,
            "error": self.error,
            "worktree_path": self.worktree_path,
            "timed_out": self.timed_out,
            "execution_time_ms": self.execution_time_ms,
            "task_id": self.task_id,
        }


class AgentTeamsParallelExecutionManagerV6:
    """
    Parallel Execution Manager for Sub-Agents V6.

    Manages concurrent parallel sub-agent workers, allocating isolated worktree directories
    and environment contexts.
    """

    def __init__(
        self,
        base_worktree_dir: str = "/tmp/magda_parallel_worktrees_v6",
        max_parallel_subagents: int = 8,
        default_timeout_seconds: float = 60.0,
        cleanup_on_completion: bool = True,
    ):
        self.base_worktree_dir = base_worktree_dir
        self.max_parallel_subagents = max(1, max_parallel_subagents)
        self.default_timeout = default_timeout_seconds
        self.cleanup_on_completion = cleanup_on_completion

        os.makedirs(self.base_worktree_dir, exist_ok=True)
        self._active_worktrees: Dict[str, str] = {}
        self._total_executed = 0

    def allocate_worktree(self, subagent_id: str) -> str:
        """Create a dedicated isolated worktree directory for a sub-agent."""
        wt_path = os.path.join(self.base_worktree_dir, f"wt_{subagent_id}_{uuid.uuid4().hex[:6]}")
        os.makedirs(wt_path, exist_ok=True)
        self._active_worktrees[subagent_id] = wt_path
        return wt_path

    def cleanup_worktree(self, subagent_id: str) -> None:
        """Clean up and remove sub-agent worktree directory."""
        wt_path = self._active_worktrees.pop(subagent_id, None)
        if wt_path and os.path.exists(wt_path):
            shutil.rmtree(wt_path, ignore_errors=True)

    async def _execute_single_subagent(
        self,
        task: SubagentExecutionTaskV6,
        semaphore: asyncio.Semaphore,
        runner_fn: Optional[Callable[[SubagentExecutionTaskV6, str, Dict[str, str]], Any]] = None,
    ) -> SubagentExecutionOutcomeV6:
        """Execute an individual sub-agent within its isolated worktree under semaphore control."""
        start_t = time.perf_counter()
        wt_path = task.worktree_path or self.allocate_worktree(task.subagent_id)

        isolated_env = dict(task.env_vars)
        isolated_env["MAGDA_AGENT_ID"] = task.subagent_id
        isolated_env["MAGDA_WORKTREE_PATH"] = wt_path
        isolated_env["MAGDA_ISOLATED"] = "true"
        isolated_env["MAGDA_TASK_ID"] = task.task_id

        async with semaphore:
            try:
                if runner_fn:
                    if inspect.iscoroutinefunction(runner_fn):
                        coro = runner_fn(task, wt_path, isolated_env)
                        out = await asyncio.wait_for(coro, timeout=task.timeout_seconds)
                    else:
                        out = await asyncio.wait_for(
                            asyncio.to_thread(runner_fn, task, wt_path, isolated_env),
                            timeout=task.timeout_seconds,
                        )
                else:
                    # Default mock subagent execution: write a marker file in worktree
                    marker_file = os.path.join(wt_path, "execution.json")
                    with open(marker_file, "w") as f:
                        json.dump({"agent_id": task.subagent_id, "task": task.task_name}, f)
                    out = f"Subagent '{task.subagent_id}' completed '{task.task_name}' in {wt_path}"

                elapsed = (time.perf_counter() - start_t) * 1000.0
                outcome = SubagentExecutionOutcomeV6(
                    subagent_id=task.subagent_id,
                    task_name=task.task_name,
                    success=True,
                    output=out,
                    worktree_path=wt_path,
                    isolated_env=isolated_env,
                    execution_time_ms=elapsed,
                    task_id=task.task_id,
                )

            except asyncio.TimeoutError:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                outcome = SubagentExecutionOutcomeV6(
                    subagent_id=task.subagent_id,
                    task_name=task.task_name,
                    success=False,
                    error=f"Subagent execution timed out after {task.timeout_seconds}s",
                    worktree_path=wt_path,
                    isolated_env=isolated_env,
                    timed_out=True,
                    execution_time_ms=elapsed,
                    task_id=task.task_id,
                )

            except Exception as ex:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                outcome = SubagentExecutionOutcomeV6(
                    subagent_id=task.subagent_id,
                    task_name=task.task_name,
                    success=False,
                    error=str(ex),
                    worktree_path=wt_path,
                    isolated_env=isolated_env,
                    execution_time_ms=elapsed,
                    task_id=task.task_id,
                )

            finally:
                if self.cleanup_on_completion and not task.worktree_path:
                    self.cleanup_worktree(task.subagent_id)

            return outcome

    async def execute_parallel_tasks_async(
        self,
        tasks: List[Union[SubagentExecutionTaskV6, Dict[str, Any]]],
        runner_fn: Optional[Callable[[SubagentExecutionTaskV6, str, Dict[str, str]], Any]] = None,
    ) -> List[SubagentExecutionOutcomeV6]:
        """
        Execute multiple sub-agents in parallel across isolated worktrees.
        """
        if not tasks:
            return []

        norm_tasks: List[SubagentExecutionTaskV6] = []
        for t in tasks:
            if isinstance(t, SubagentExecutionTaskV6):
                norm_tasks.append(t)
            elif isinstance(t, dict):
                norm_tasks.append(SubagentExecutionTaskV6.from_dict(t))

        semaphore = asyncio.Semaphore(self.max_concurrency)
        self._total_executed += len(norm_tasks)

        coros = [self._execute_single_subagent(task, semaphore, runner_fn) for task in norm_tasks]
        results = await asyncio.gather(*coros)
        return list(results)

    def execute_parallel_tasks(
        self,
        tasks: List[Union[SubagentExecutionTaskV6, Dict[str, Any]]],
        runner_fn: Optional[Callable[[SubagentExecutionTaskV6, str, Dict[str, str]], Any]] = None,
    ) -> List[SubagentExecutionOutcomeV6]:
        """Synchronous wrapper for parallel execution."""
        return asyncio.run(self.execute_parallel_tasks_async(tasks, runner_fn))

    @property
    def max_concurrency(self) -> int:
        return self.max_parallel_subagents

    def get_stats(self) -> Dict[str, Any]:
        """Return execution manager statistics."""
        return {
            "max_concurrency": self.max_concurrency,
            "total_executed": self._total_executed,
            "active_worktrees_count": len(self._active_worktrees),
        }
