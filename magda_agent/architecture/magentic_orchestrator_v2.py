"""
Magentic-One Pattern Agent Teams V2.

Inspired by Microsoft's Magentic-One multi-agent orchestration architecture:
Implements a central Orchestrator coordinating specialized sub-agents via a
thread-safe, lock-protected global Blackboard state that ensures race-condition-free
state sharing and concurrent progress.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class BlackboardEntry:
    """Individual state variable stored in the global blackboard."""

    key: str
    value: Any
    updated_by: str = "orchestrator"
    revision: int = 1
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThreadSafeBlackboardState:
    """
    Asyncio-lock protected, thread-safe global blackboard state for multi-agent teams.
    Eliminates race conditions during concurrent sub-agent reads and writes.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self._lock = asyncio.Lock()
        self._state: Dict[str, BlackboardEntry] = {}
        self._revision_counter: int = 0
        self._event_log: List[Dict[str, Any]] = []

        if initial_state:
            for k, v in initial_state.items():
                self._state[k] = BlackboardEntry(
                    key=k,
                    value=v,
                    updated_by="initializer",
                    revision=0,
                )

    async def get(self, key: str, default: Any = None) -> Any:
        """Fetch a value safely from the blackboard."""
        async with self._lock:
            entry = self._state.get(key)
            return entry.value if entry else default

    async def set(self, key: str, value: Any, agent_id: str = "orchestrator") -> int:
        """Set a value safely with revision increment."""
        async with self._lock:
            self._revision_counter += 1
            prev_rev = self._state[key].revision if key in self._state else 0
            new_rev = prev_rev + 1
            entry = BlackboardEntry(
                key=key,
                value=value,
                updated_by=agent_id,
                revision=new_rev,
                timestamp=time.time(),
            )
            self._state[key] = entry
            self._event_log.append({
                "action": "set",
                "key": key,
                "agent_id": agent_id,
                "revision": new_rev,
                "global_revision": self._revision_counter,
                "timestamp": entry.timestamp,
            })
            return new_rev

    async def atomic_update(
        self,
        key: str,
        update_fn: Callable[[Any], Any],
        agent_id: str = "orchestrator",
        default: Any = None,
    ) -> Any:
        """Atomically read, modify, and write a key under exclusive lock."""
        async with self._lock:
            self._revision_counter += 1
            current_val = self._state[key].value if key in self._state else default
            if inspect.iscoroutinefunction(update_fn):
                new_val = await update_fn(current_val)
            else:
                new_val = update_fn(current_val)

            prev_rev = self._state[key].revision if key in self._state else 0
            new_rev = prev_rev + 1
            entry = BlackboardEntry(
                key=key,
                value=new_val,
                updated_by=agent_id,
                revision=new_rev,
                timestamp=time.time(),
            )
            self._state[key] = entry
            self._event_log.append({
                "action": "atomic_update",
                "key": key,
                "agent_id": agent_id,
                "revision": new_rev,
                "global_revision": self._revision_counter,
                "timestamp": entry.timestamp,
            })
            return new_val

    async def get_snapshot(self) -> Dict[str, Any]:
        """Return a clean dictionary snapshot of all current blackboard values."""
        async with self._lock:
            return {k: entry.value for k, entry in self._state.items()}

    async def get_full_metadata_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return complete snapshot with revisions and author metadata."""
        async with self._lock:
            return {k: entry.to_dict() for k, entry in self._state.items()}

    async def append_to_list(self, key: str, item: Any, agent_id: str = "orchestrator") -> int:
        """Atomically append an item to a list on the blackboard."""
        def _append(curr):
            lst = list(curr) if isinstance(curr, list) else []
            lst.append(item)
            return lst

        await self.atomic_update(key, _append, agent_id=agent_id, default=[])
        async with self._lock:
            return len(self._state[key].value)

    async def get_event_log(self) -> List[Dict[str, Any]]:
        """Retrieve copy of all state update events."""
        async with self._lock:
            return list(self._event_log)


class MagenticSubagentV2:
    """Specialized sub-agent executing tasks in the Magentic-One orchestration pattern."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        handler: Optional[Callable[[str, ThreadSafeBlackboardState], Coroutine[Any, Any, Any]]] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.handler = handler

    async def execute_task(
        self,
        task_desc: str,
        blackboard: ThreadSafeBlackboardState,
    ) -> Dict[str, Any]:
        """Execute sub-agent logic against the shared blackboard."""
        start_t = time.perf_counter()
        if self.handler:
            if inspect.iscoroutinefunction(self.handler):
                result = await self.handler(task_desc, blackboard)
            else:
                result = self.handler(task_desc, blackboard)
        else:
            # Default behavior: record task completion on blackboard
            result = f"Completed '{task_desc}' by {self.name} ({self.role})"
            await blackboard.append_to_list("task_results", {
                "agent_id": self.agent_id,
                "role": self.role,
                "task": task_desc,
                "output": result,
            }, agent_id=self.agent_id)

        elapsed = (time.perf_counter() - start_t) * 1000.0
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "task": task_desc,
            "output": result,
            "duration_ms": elapsed,
        }


class MagenticOrchestratorV2:
    """
    Central Magentic-One Multi-Agent Orchestrator V2.

    Coordinates sub-agents through a thread-safe shared blackboard.
    """

    def __init__(
        self,
        subagents: Optional[List[MagenticSubagentV2]] = None,
        initial_blackboard: Optional[Dict[str, Any]] = None,
    ):
        self.blackboard = ThreadSafeBlackboardState(initial_state=initial_blackboard)
        self._subagents: Dict[str, MagenticSubagentV2] = {}

        if subagents:
            for sa in subagents:
                self.register_subagent(sa)

    def register_subagent(self, subagent: MagenticSubagentV2) -> None:
        """Register a sub-agent with the orchestrator."""
        self._subagents[subagent.agent_id] = subagent
        logger.info(f"Registered Magentic sub-agent '{subagent.name}' [{subagent.role}] ({subagent.agent_id})")

    def get_subagent(self, agent_id: str) -> Optional[MagenticSubagentV2]:
        """Fetch subagent by ID."""
        return self._subagents.get(agent_id)

    async def execute_parallel_subtasks(
        self,
        tasks: List[Tuple[str, str]],  # List of (agent_id, task_desc)
    ) -> List[Dict[str, Any]]:
        """
        Concurrently execute multiple subagent tasks against the shared blackboard
        without race conditions.
        """
        coros = []
        for agent_id, task_desc in tasks:
            sa = self._subagents.get(agent_id)
            if sa:
                coros.append(sa.execute_task(task_desc, self.blackboard))
            else:
                async def not_found(aid=agent_id, td=task_desc):
                    return {"agent_id": aid, "error": f"Subagent '{aid}' not registered", "task": td}
                coros.append(not_found())

        return await asyncio.gather(*coros)

    async def run_orchestration(
        self,
        goal: str,
        plan_steps: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full multi-agent orchestration loop.
        """
        await self.blackboard.set("goal", goal, agent_id="orchestrator")
        await self.blackboard.set("status", "IN_PROGRESS", agent_id="orchestrator")

        steps = plan_steps or [
            (aid, f"Contribute to goal: {goal}") for aid in self._subagents.keys()
        ]

        results = await self.execute_parallel_subtasks(steps)
        await self.blackboard.set("status", "COMPLETED", agent_id="orchestrator")
        final_state = await self.blackboard.get_snapshot()

        return {
            "goal": goal,
            "status": "COMPLETED",
            "results": results,
            "blackboard_snapshot": final_state,
        }

    def run_orchestration_sync(
        self,
        goal: str,
        plan_steps: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for orchestration."""
        return asyncio.run(self.run_orchestration(goal, plan_steps))
