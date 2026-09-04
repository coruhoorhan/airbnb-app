"""
A2A Peer Delegation Routing V2.

Inspired by Agent-to-Agent (A2A) protocol trends: Evaluates task complexity,
matches required capabilities against a peer agent network using Agent Cards,
and orchestrates reliable peer task delegation.
"""

import asyncio
import inspect
import json
import logging
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class TaskComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ComplexityEvaluationResult:
    """Outcome of evaluating task complexity."""

    score: float  # 0.0 to 1.0
    level: TaskComplexityLevel
    reasons: List[str] = field(default_factory=list)
    estimated_steps: int = 1
    requires_specialized_peer: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value if isinstance(self.level, TaskComplexityLevel) else str(self.level)
        return d


@dataclass
class TaskSpec:
    """Specification of a task to be evaluated and routed."""

    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0
    priority: int = 1
    max_delegation_depth: int = 3
    complexity_override: Optional[TaskComplexityLevel] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.complexity_override, TaskComplexityLevel):
            d["complexity_override"] = self.complexity_override.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSpec":
        override = data.get("complexity_override")
        if isinstance(override, str):
            try:
                override = TaskComplexityLevel(override.lower())
            except ValueError:
                override = None
        return cls(
            task_id=data.get("task_id") or f"task_{uuid.uuid4().hex[:8]}",
            title=data.get("title", ""),
            description=data.get("description", ""),
            required_capabilities=data.get("required_capabilities", []),
            context=data.get("context", {}),
            estimated_tokens=data.get("estimated_tokens", 0),
            priority=data.get("priority", 1),
            max_delegation_depth=data.get("max_delegation_depth", 3),
            complexity_override=override,
        )


@dataclass
class PeerAgentCard:
    """Represents a peer sub-agent's identity and capabilities in the A2A network."""

    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    max_complexity: TaskComplexityLevel = TaskComplexityLevel.HIGH
    endpoints: Dict[str, str] = field(default_factory=dict)
    workload_score: float = 0.0  # 0.0 (idle) to 1.0 (overloaded)
    status: str = "online"  # online, busy, offline
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_complexity"] = (
            self.max_complexity.value
            if isinstance(self.max_complexity, TaskComplexityLevel)
            else str(self.max_complexity)
        )
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PeerAgentCard":
        max_c = data.get("max_complexity", "high")
        if isinstance(max_c, str):
            try:
                max_c = TaskComplexityLevel(max_c.lower())
            except ValueError:
                max_c = TaskComplexityLevel.HIGH
        return cls(
            agent_id=data["agent_id"],
            name=data.get("name", data["agent_id"]),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            max_complexity=max_c,
            endpoints=data.get("endpoints", {}),
            workload_score=float(data.get("workload_score", 0.0)),
            status=data.get("status", "online"),
            metadata=data.get("metadata", {}),
        )

    def has_capability(self, required_cap: str) -> bool:
        req = required_cap.strip().lower()
        for cap in self.capabilities:
            c = cap.strip().lower()
            if req == c or req in c or c in req:
                return True
        return False


@dataclass
class A2APeerDelegationPayload:
    """Standardized task delegation payload traversing A2A mesh network."""

    delegation_id: str = field(default_factory=lambda: f"del_{uuid.uuid4().hex[:10]}")
    sender_id: str = "magda_primary"
    target_agent_id: str = ""
    task: TaskSpec = field(default_factory=TaskSpec)
    complexity_evaluation: Optional[ComplexityEvaluationResult] = None
    created_at: float = field(default_factory=time.time)
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "sender_id": self.sender_id,
            "target_agent_id": self.target_agent_id,
            "task": self.task.to_dict(),
            "complexity_evaluation": (
                self.complexity_evaluation.to_dict() if self.complexity_evaluation else None
            ),
            "created_at": self.created_at,
            "signature": self.signature,
            "metadata": self.metadata,
        }


@dataclass
class DelegationResult:
    """Result of delegating a task to a peer agent."""

    success: bool
    delegation_id: str
    target_agent_id: str
    payload: A2APeerDelegationPayload
    response_data: Any = None
    error: Optional[str] = None
    matched_capabilities: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "delegation_id": self.delegation_id,
            "target_agent_id": self.target_agent_id,
            "response_data": self.response_data,
            "error": self.error,
            "matched_capabilities": self.matched_capabilities,
            "execution_time_ms": self.execution_time_ms,
        }


class TaskComplexityEvaluator:
    """Evaluates task description, required capabilities, and context complexity."""

    HIGH_COMPLEXITY_KEYWORDS = {
        "refactor", "architecture", "distributed", "consensus", "migration",
        "optimization", "security", "taint", "multi-step", "concurrency",
        "deep learning", "synthesis", "benchmark", "sandbox", "compiler",
    }

    MEDIUM_COMPLEXITY_KEYWORDS = {
        "crud", "endpoint", "parser", "validator", "unit test", "query",
        "api integration", "filter", "transform", "caching", "routing",
    }

    def evaluate(self, task: TaskSpec) -> ComplexityEvaluationResult:
        if task.complexity_override:
            level = task.complexity_override
            score_map = {
                TaskComplexityLevel.LOW: 0.2,
                TaskComplexityLevel.MEDIUM: 0.5,
                TaskComplexityLevel.HIGH: 0.8,
                TaskComplexityLevel.CRITICAL: 1.0,
            }
            return ComplexityEvaluationResult(
                score=score_map.get(level, 0.5),
                level=level,
                reasons=["Complexity override specified in task"],
                requires_specialized_peer=level in (TaskComplexityLevel.HIGH, TaskComplexityLevel.CRITICAL),
            )

        score = 0.1
        reasons = []
        text = f"{task.title} {task.description}".lower()

        # Check high complexity terms
        high_matches = [w for w in self.HIGH_COMPLEXITY_KEYWORDS if w in text]
        if high_matches:
            score += min(0.4, 0.15 * len(high_matches))
            reasons.append(f"Contains high-complexity terms: {', '.join(high_matches)}")

        # Check medium complexity terms
        med_matches = [w for w in self.MEDIUM_COMPLEXITY_KEYWORDS if w in text]
        if med_matches:
            score += min(0.2, 0.08 * len(med_matches))
            reasons.append(f"Contains medium-complexity terms: {', '.join(med_matches)}")

        # Required capabilities complexity
        cap_count = len(task.required_capabilities)
        if cap_count > 3:
            score += 0.2
            reasons.append(f"Multiple ({cap_count}) required capabilities")
        elif cap_count > 0:
            score += 0.1

        # Token length / context complexity
        if task.estimated_tokens > 4000:
            score += 0.2
            reasons.append(f"Large estimated context ({task.estimated_tokens} tokens)")
        elif task.estimated_tokens > 1000:
            score += 0.1

        if len(task.context) > 5:
            score += 0.1
            reasons.append(f"Broad contextual parameters ({len(task.context)} items)")

        score = min(1.0, max(0.0, score))

        if score >= 0.75:
            level = TaskComplexityLevel.CRITICAL
            steps = 5
            requires_spec = True
        elif score >= 0.5:
            level = TaskComplexityLevel.HIGH
            steps = 4
            requires_spec = True
        elif score >= 0.25:
            level = TaskComplexityLevel.MEDIUM
            steps = 2
            requires_spec = False
        else:
            level = TaskComplexityLevel.LOW
            steps = 1
            requires_spec = False

        return ComplexityEvaluationResult(
            score=round(score, 2),
            level=level,
            reasons=reasons or ["Standard baseline complexity"],
            estimated_steps=steps,
            requires_specialized_peer=requires_spec,
        )


class A2APeerDelegationRouterV2:
    """
    A2A Peer Delegation Routing Engine V2.

    Evaluates tasks and delegates them to registered peer sub-agents via Agent Cards.
    """

    def __init__(
        self,
        sender_id: str = "magda_primary",
        complexity_evaluator: Optional[TaskComplexityEvaluator] = None,
    ):
        self.sender_id = sender_id
        self.complexity_evaluator = complexity_evaluator or TaskComplexityEvaluator()
        self._peer_registry: Dict[str, PeerAgentCard] = {}
        self._delegation_history: List[DelegationResult] = []

    def register_peer(self, peer: Union[PeerAgentCard, Dict[str, Any]]) -> None:
        """Register a peer agent card in the routing mesh."""
        if isinstance(peer, dict):
            peer = PeerAgentCard.from_dict(peer)
        self._peer_registry[peer.agent_id] = peer
        logger.info(f"Registered peer agent '{peer.name}' ({peer.agent_id}) with caps: {peer.capabilities}")

    def unregister_peer(self, agent_id: str) -> bool:
        """Remove a peer agent from the registry."""
        if agent_id in self._peer_registry:
            del self._peer_registry[agent_id]
            return True
        return False

    def get_peer(self, agent_id: str) -> Optional[PeerAgentCard]:
        """Fetch a registered peer by ID."""
        return self._peer_registry.get(agent_id)

    def list_peers(self) -> List[PeerAgentCard]:
        """Return all registered peer agent cards."""
        return list(self._peer_registry.values())

    def evaluate_task_complexity(
        self,
        task: Union[TaskSpec, Dict[str, Any], str],
    ) -> ComplexityEvaluationResult:
        """Evaluate complexity of a given task."""
        if isinstance(task, str):
            task_spec = TaskSpec(description=task)
        elif isinstance(task, dict):
            task_spec = TaskSpec.from_dict(task)
        else:
            task_spec = task

        return self.complexity_evaluator.evaluate(task_spec)

    def match_peer(
        self,
        task: Union[TaskSpec, Dict[str, Any]],
    ) -> Optional[Tuple[PeerAgentCard, List[str]]]:
        """
        Find the best matching peer agent for a task based on capabilities,
        complexity suitability, and current workload.
        """
        if isinstance(task, dict):
            task = TaskSpec.from_dict(task)

        complexity = self.evaluate_task_complexity(task)
        required_caps = task.required_capabilities

        candidates: List[Tuple[float, PeerAgentCard, List[str]]] = []

        complexity_weights = {
            TaskComplexityLevel.LOW: 1,
            TaskComplexityLevel.MEDIUM: 2,
            TaskComplexityLevel.HIGH: 3,
            TaskComplexityLevel.CRITICAL: 4,
        }

        task_comp_weight = complexity_weights.get(complexity.level, 2)

        for peer in self._peer_registry.values():
            if peer.status == "offline":
                continue

            peer_comp_weight = complexity_weights.get(peer.max_complexity, 3)
            # Peer must support at least this complexity level
            if peer_comp_weight < task_comp_weight:
                continue

            matched_caps = []
            if required_caps:
                matched_caps = [cap for cap in required_caps if peer.has_capability(cap)]
                # Must match all required capabilities if specified
                if len(matched_caps) < len(required_caps):
                    continue
            else:
                matched_caps = list(peer.capabilities)

            # Score candidate: capability match ratio + workload headroom
            cap_score = (len(matched_caps) / max(1, len(required_caps))) if required_caps else 1.0
            workload_headroom = 1.0 - min(1.0, max(0.0, peer.workload_score))
            total_score = (cap_score * 0.7) + (workload_headroom * 0.3)

            candidates.append((total_score, peer, matched_caps))

        if not candidates:
            return None

        # Sort by total score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]
        return best[1], best[2]

    def delegate_task(
        self,
        task: Union[TaskSpec, Dict[str, Any]],
        peer: Optional[PeerAgentCard] = None,
        transport_mock: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> DelegationResult:
        """
        Evaluate, route, and delegate task to a peer agent synchronously.
        """
        start_t = time.perf_counter()
        if isinstance(task, dict):
            task = TaskSpec.from_dict(task)

        complexity = self.evaluate_task_complexity(task)

        matched_caps: List[str] = []
        target_peer = peer
        if target_peer is None:
            match_res = self.match_peer(task)
            if match_res is None:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                err = f"No available peer matches required capabilities: {task.required_capabilities}"
                res = DelegationResult(
                    success=False,
                    delegation_id="",
                    target_agent_id="",
                    payload=A2APeerDelegationPayload(task=task, complexity_evaluation=complexity),
                    error=err,
                    execution_time_ms=elapsed,
                )
                self._delegation_history.append(res)
                return res
            target_peer, matched_caps = match_res
        else:
            matched_caps = [c for c in task.required_capabilities if target_peer.has_capability(c)]

        payload = A2APeerDelegationPayload(
            sender_id=self.sender_id,
            target_agent_id=target_peer.agent_id,
            task=task,
            complexity_evaluation=complexity,
            created_at=time.time(),
        )

        try:
            if transport_mock:
                response = transport_mock(payload.to_dict())
            else:
                response = {
                    "status": "acknowledged",
                    "agent_id": target_peer.agent_id,
                    "delegation_id": payload.delegation_id,
                    "task_id": task.task_id,
                    "result": f"Task '{task.title or task.task_id}' accepted by {target_peer.name}",
                }

            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = DelegationResult(
                success=True,
                delegation_id=payload.delegation_id,
                target_agent_id=target_peer.agent_id,
                payload=payload,
                response_data=response,
                matched_capabilities=matched_caps,
                execution_time_ms=elapsed,
            )
            self._delegation_history.append(res)
            return res

        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = DelegationResult(
                success=False,
                delegation_id=payload.delegation_id,
                target_agent_id=target_peer.agent_id,
                payload=payload,
                error=str(e),
                matched_capabilities=matched_caps,
                execution_time_ms=elapsed,
            )
            self._delegation_history.append(res)
            return res

    async def delegate_task_async(
        self,
        task: Union[TaskSpec, Dict[str, Any]],
        peer: Optional[PeerAgentCard] = None,
        transport_mock: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
    ) -> DelegationResult:
        """
        Evaluate, route, and delegate task to a peer agent asynchronously.
        """
        start_t = time.perf_counter()
        if isinstance(task, dict):
            task = TaskSpec.from_dict(task)

        complexity = self.evaluate_task_complexity(task)

        matched_caps: List[str] = []
        target_peer = peer
        if target_peer is None:
            match_res = self.match_peer(task)
            if match_res is None:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                err = f"No available peer matches required capabilities: {task.required_capabilities}"
                res = DelegationResult(
                    success=False,
                    delegation_id="",
                    target_agent_id="",
                    payload=A2APeerDelegationPayload(task=task, complexity_evaluation=complexity),
                    error=err,
                    execution_time_ms=elapsed,
                )
                self._delegation_history.append(res)
                return res
            target_peer, matched_caps = match_res
        else:
            matched_caps = [c for c in task.required_capabilities if target_peer.has_capability(c)]

        payload = A2APeerDelegationPayload(
            sender_id=self.sender_id,
            target_agent_id=target_peer.agent_id,
            task=task,
            complexity_evaluation=complexity,
            created_at=time.time(),
        )

        try:
            if transport_mock:
                if inspect.iscoroutinefunction(transport_mock):
                    response = await transport_mock(payload.to_dict())
                else:
                    response = transport_mock(payload.to_dict())
            else:
                await asyncio.sleep(0.01)
                response = {
                    "status": "acknowledged",
                    "agent_id": target_peer.agent_id,
                    "delegation_id": payload.delegation_id,
                    "task_id": task.task_id,
                    "result": f"Task '{task.title or task.task_id}' accepted by {target_peer.name}",
                }

            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = DelegationResult(
                success=True,
                delegation_id=payload.delegation_id,
                target_agent_id=target_peer.agent_id,
                payload=payload,
                response_data=response,
                matched_capabilities=matched_caps,
                execution_time_ms=elapsed,
            )
            self._delegation_history.append(res)
            return res

        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = DelegationResult(
                success=False,
                delegation_id=payload.delegation_id,
                target_agent_id=target_peer.agent_id,
                payload=payload,
                error=str(e),
                matched_capabilities=matched_caps,
                execution_time_ms=elapsed,
            )
            self._delegation_history.append(res)
            return res

    def get_routing_metrics(self) -> Dict[str, Any]:
        """Summary of routing and delegation metrics."""
        total = len(self._delegation_history)
        successful = sum(1 for d in self._delegation_history if d.success)
        return {
            "total_registered_peers": len(self._peer_registry),
            "total_delegations": total,
            "successful_delegations": successful,
            "failed_delegations": total - successful,
            "peers": [p.to_dict() for p in self._peer_registry.values()],
        }
