"""
Claude Agent SDK Hierarchical Planner V3.

Inspired by Claude Agent SDK multi-agent orchestration and task decomposition:
Implements a hierarchical planning engine that decomposes complex user objectives
into directed acyclic graphs (DAG) of sub-tasks with assigned agent roles, dependencies,
and parallel execution stages.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
import inspect
import json
import logging
import re
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class PlanSubTask:
    """Represents an individual sub-task in the hierarchical execution plan."""

    task_id: str
    title: str
    description: str = ""
    assigned_role: str = "coder"  # architect, coder, tester, researcher, reviewer
    dependencies: List[str] = field(default_factory=list)
    estimated_effort: float = 1.0
    status: str = "pending"  # pending, in_progress, completed, failed
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanSubTask":
        t_id = str(data.get("task_id") or data.get("id") or f"subtask_{uuid.uuid4().hex[:8]}")
        return cls(
            task_id=t_id,
            title=str(data.get("title") or t_id),
            description=str(data.get("description") or ""),
            assigned_role=str(data.get("assigned_role") or data.get("role") or "coder"),
            dependencies=[str(d) for d in (data.get("dependencies") or [])],
            estimated_effort=float(data.get("estimated_effort", 1.0)),
            status=str(data.get("status") or "pending"),
            output=data.get("output"),
            error=data.get("error"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class DecompositionPlan:
    """Represents a complete hierarchical decomposition plan."""

    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    original_goal: str = ""
    subtasks: List[PlanSubTask] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    parallel_stages: List[List[str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_subtask(self, task_id: str) -> Optional[PlanSubTask]:
        for st in self.subtasks:
            if st.task_id == task_id:
                return st
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "original_goal": self.original_goal,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "topological_order": self.topological_order,
            "parallel_stages": self.parallel_stages,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class ClaudeHierarchicalPlannerV3:
    """
    Claude Agent SDK Hierarchical Planner V3.

    Decomposes top-level goals into a validated DAG of sub-agent tasks.
    """

    DEFAULT_ROLES = ["architect", "coder", "tester", "researcher", "reviewer", "security_auditor"]

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        available_roles: Optional[List[str]] = None,
    ):
        self.llm_client = llm_client
        self.available_roles = list(available_roles or self.DEFAULT_ROLES)
        self._plan_history: List[DecompositionPlan] = []

    def _topological_sort_and_stages(
        self,
        subtasks: List[PlanSubTask],
    ) -> Tuple[List[str], List[List[str]]]:
        """
        Validate DAG and compute topological ordering and parallel execution stages.
        """
        task_map = {st.task_id: st for st in subtasks}
        in_degree = {st.task_id: 0 for st in subtasks}
        adj = defaultdict(list)

        for st in subtasks:
            for dep in st.dependencies:
                if dep in task_map:
                    adj[dep].append(st.task_id)
                    in_degree[st.task_id] += 1

        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        topological_order = []
        stages = []
        visited = 0

        while queue:
            stage = []
            for _ in range(len(queue)):
                curr = queue.popleft()
                stage.append(curr)
                topological_order.append(curr)
                visited += 1

                for nxt in adj[curr]:
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        queue.append(nxt)
            stages.append(stage)

        if visited < len(subtasks):
            raise ValueError(f"Cycle detected in plan dependencies ({visited}/{len(subtasks)} tasks resolved)")

        return topological_order, stages

    async def decompose_goal_async(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecompositionPlan:
        """
        Decompose a high-level goal into a structured, validated DecompositionPlan.
        """
        subtasks: List[PlanSubTask] = []

        if self.llm_client:
            prompt = (
                f"You are a Claude Hierarchical Task Planner. Decompose this goal into subtasks with dependencies and assigned roles.\n"
                f"Goal: {goal}\n"
                f"Available roles: {self.available_roles}\n"
                f"Context: {json.dumps(context or {})}\n\n"
                "Return a JSON object: {\"subtasks\": [{\"task_id\": \"...\", \"title\": \"...\", \"description\": \"...\", \"assigned_role\": \"...\", \"dependencies\": [\"...\"]}]}"
            )
            try:
                if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                    raw = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "generate"):
                    raw = self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                    raw = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                else:
                    raw = ""

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    raw_tasks = parsed.get("subtasks", [])
                    subtasks = [PlanSubTask.from_dict(t) for t in raw_tasks if isinstance(t, dict)]
            except Exception as ex:
                logger.warning(f"LLM goal decomposition failed: {ex}. Using heuristic planner.")

        # Heuristic fallback decomposition
        if not subtasks:
            t1 = PlanSubTask(task_id="step_1_research", title=f"Analyze requirements for '{goal}'", assigned_role="researcher", dependencies=[])
            t2 = PlanSubTask(task_id="step_2_design", title="Architecture and API design", assigned_role="architect", dependencies=["step_1_research"])
            t3 = PlanSubTask(task_id="step_3_implement", title="Core implementation", assigned_role="coder", dependencies=["step_2_design"])
            t4 = PlanSubTask(task_id="step_4_test", title="Unit and integration testing", assigned_role="tester", dependencies=["step_3_implement"])
            t5 = PlanSubTask(task_id="step_5_review", title="Code review and security audit", assigned_role="reviewer", dependencies=["step_4_test"])
            subtasks = [t1, t2, t3, t4, t5]

        top_order, stages = self._topological_sort_and_stages(subtasks)

        plan = DecompositionPlan(
            original_goal=goal,
            subtasks=subtasks,
            topological_order=top_order,
            parallel_stages=stages,
            metadata=context or {},
        )
        self._plan_history.append(plan)
        return plan

    def decompose_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecompositionPlan:
        """Synchronous wrapper for goal decomposition."""
        return asyncio.run(self.decompose_goal_async(goal, context))

    def get_executable_subtasks(
        self,
        plan: DecompositionPlan,
        completed_task_ids: Optional[Set[str]] = None,
    ) -> List[PlanSubTask]:
        """
        Return subtasks ready for execution whose prerequisites are satisfied.
        """
        done = completed_task_ids if completed_task_ids is not None else {
            st.task_id for st in plan.subtasks if st.status == "completed"
        }

        executable = []
        for st in plan.subtasks:
            if st.task_id in done or st.status in ("completed", "failed", "in_progress"):
                continue

            if all(dep in done for dep in st.dependencies):
                executable.append(st)

        return executable

    def update_subtask_status(
        self,
        plan: DecompositionPlan,
        task_id: str,
        status: str,
        output: Any = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the status and result of a subtask within a plan."""
        st = plan.get_subtask(task_id)
        if not st:
            return False
        st.status = status
        st.output = output
        st.error = error
        return True

    def is_plan_complete(self, plan: DecompositionPlan) -> bool:
        """Check if all subtasks in plan are marked completed."""
        return len(plan.subtasks) > 0 and all(st.status == "completed" for st in plan.subtasks)

    def simulate_plan_execution(
        self,
        plan: DecompositionPlan,
        mock_executor: Optional[Callable[[PlanSubTask], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Simulate step-by-step resolution of the plan across parallel stages without invoking real agents.
        """
        results = {}
        for stage in plan.parallel_stages:
            for task_id in stage:
                st = plan.get_subtask(task_id)
                if not st:
                    continue

                st.status = "in_progress"
                if mock_executor:
                    out = mock_executor(st)
                else:
                    out = f"Simulated output from role '{st.assigned_role}' for '{st.title}'"

                self.update_subtask_status(plan, task_id, "completed", output=out)
                results[task_id] = {
                    "role": st.assigned_role,
                    "title": st.title,
                    "output": out,
                    "status": "completed",
                }

        return {
            "plan_id": plan.plan_id,
            "goal": plan.original_goal,
            "total_subtasks": len(plan.subtasks),
            "stages_executed": len(plan.parallel_stages),
            "results": results,
            "is_complete": self.is_plan_complete(plan),
        }
