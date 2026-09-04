"""
Hierarchical Delegation Telemetry Exporter v2.

Inspired by Magentic-One and Agent Teams: Captures, aggregates, and exports
telemetry data on parallel sub-agent communication for live visualization tools,
dashboards, and observability systems.
"""

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


class AgentMessageType(str, Enum):
    TASK_DELEGATION = "task_delegation"
    SUBTASK_RESULT = "subtask_result"
    INTER_AGENT_MESSAGE = "inter_agent_message"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    STATE_SYNC = "state_sync"


@dataclass
class AgentTelemetryEvent:
    """Represents a single captured communication event between hierarchical agents."""

    event_id: str
    timestamp: float
    session_id: str
    source_agent_id: str
    target_agent_id: str
    message_type: str
    payload_summary: str
    payload_size_bytes: int
    duration_ms: float = 0.0
    status: str = "completed"
    parent_agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTelemetryEvent":
        return cls(**data)


class HierarchicalDelegationTelemetryExporterV2:
    """
    Telemetry exporter that tracks inter-agent message traffic, delegation lifecycles,
    and topology graphs for live visualization tools.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        max_events: int = 5000,
        listeners: Optional[List[Callable[[Dict[str, Any]], Any]]] = None,
    ) -> None:
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        self.max_events = max_events
        self._events: deque[AgentTelemetryEvent] = deque(maxlen=max_events)
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = listeners or []
        self._active_delegations: Dict[str, Dict[str, Any]] = {}
        self._agent_registry: Dict[str, Dict[str, Any]] = {}
        self._communication_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._traffic_bytes_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def register_agent(
        self,
        agent_id: str,
        role: str = "worker",
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registers agent metadata in the topology tracker."""
        self._agent_registry[agent_id] = {
            "agent_id": agent_id,
            "role": role,
            "parent_id": parent_id,
            "registered_at": time.time(),
            "metadata": metadata or {},
        }

    def record_message(
        self,
        source_agent_id: str,
        target_agent_id: str,
        message_type: Union[AgentMessageType, str],
        payload: Any,
        parent_agent_id: Optional[str] = None,
        duration_ms: float = 0.0,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentTelemetryEvent:
        """Captures a message passed between sub-agents and broadcasts to subscribers."""
        now = time.time()
        m_type_val = message_type.value if isinstance(message_type, AgentMessageType) else str(message_type)

        payload_str = json.dumps(payload, default=str) if not isinstance(payload, str) else payload
        payload_size = len(payload_str.encode("utf-8"))
        summary = payload_str[:250] + ("..." if len(payload_str) > 250 else "")

        event = AgentTelemetryEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            timestamp=now,
            session_id=self.session_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            message_type=m_type_val,
            payload_summary=summary,
            payload_size_bytes=payload_size,
            duration_ms=duration_ms,
            status=status,
            parent_agent_id=parent_agent_id or self._agent_registry.get(source_agent_id, {}).get("parent_id"),
            metadata=metadata or {},
        )

        self._events.append(event)
        self._communication_matrix[source_agent_id][target_agent_id] += 1
        self._traffic_bytes_matrix[source_agent_id][target_agent_id] += payload_size

        event_dict = event.to_dict()
        for listener in self._listeners:
            try:
                listener(event_dict)
            except Exception as e:
                logger.warning(f"Error in telemetry event listener: {e}")

        return event

    def record_delegation_start(
        self,
        parent_agent_id: str,
        subagent_id: str,
        task: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Marks the start of a task delegation to a sub-agent."""
        delegation_id = f"del_{uuid.uuid4().hex}"
        start_time = time.time()

        self._active_delegations[delegation_id] = {
            "delegation_id": delegation_id,
            "parent_agent_id": parent_agent_id,
            "subagent_id": subagent_id,
            "task": task,
            "start_time": start_time,
            "metadata": metadata or {},
        }

        self.record_message(
            source_agent_id=parent_agent_id,
            target_agent_id=subagent_id,
            message_type=AgentMessageType.TASK_DELEGATION,
            payload={"task": task, "delegation_id": delegation_id},
            parent_agent_id=parent_agent_id,
            status="in_flight",
            metadata={"delegation_id": delegation_id, **(metadata or {})},
        )
        return delegation_id

    def record_delegation_complete(
        self,
        delegation_id: str,
        parent_agent_id: str,
        subagent_id: str,
        result: Any,
        duration_ms: Optional[float] = None,
        status: str = "completed",
    ) -> Optional[AgentTelemetryEvent]:
        """Marks the completion/result return of a delegated task."""
        del_info = self._active_delegations.pop(delegation_id, None)
        if duration_ms is None:
            if del_info:
                duration_ms = (time.time() - del_info["start_time"]) * 1000.0
            else:
                duration_ms = 0.0

        m_type = AgentMessageType.SUBTASK_RESULT if status == "completed" else AgentMessageType.ERROR_REPORT

        return self.record_message(
            source_agent_id=subagent_id,
            target_agent_id=parent_agent_id,
            message_type=m_type,
            payload={"result": result, "delegation_id": delegation_id},
            parent_agent_id=parent_agent_id,
            duration_ms=duration_ms,
            status=status,
            metadata={"delegation_id": delegation_id},
        )

    def export_events(
        self,
        since_timestamp: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Exports captured raw telemetry events matching filter criteria."""
        events = list(self._events)
        if since_timestamp is not None:
            events = [e for e in events if e.timestamp >= since_timestamp]
        if limit is not None:
            events = events[-limit:]
        return [e.to_dict() for e in events]

    def export_topology_graph(self) -> Dict[str, Any]:
        """
        Exports an interactive graph payload with nodes and links
        compatible with live visualization and canvas tools.
        """
        known_agents: Set[str] = set(self._agent_registry.keys())
        for src, targets in self._communication_matrix.items():
            known_agents.add(src)
            for tgt in targets.keys():
                known_agents.add(tgt)

        nodes = []
        for agent_id in sorted(known_agents):
            meta = self._agent_registry.get(agent_id, {})
            nodes.append({
                "id": agent_id,
                "label": agent_id,
                "role": meta.get("role", "subagent"),
                "parent_id": meta.get("parent_id"),
                "registered": agent_id in self._agent_registry,
            })

        links = []
        for src, targets in self._communication_matrix.items():
            for tgt, msg_count in targets.items():
                byte_count = self._traffic_bytes_matrix[src][tgt]
                links.append({
                    "source": src,
                    "target": tgt,
                    "message_count": msg_count,
                    "bytes_transferred": byte_count,
                })

        return {
            "session_id": self.session_id,
            "timestamp": time.time(),
            "nodes": nodes,
            "links": links,
            "total_nodes": len(nodes),
            "total_links": len(links),
        }

    def export_metrics_summary(self) -> Dict[str, Any]:
        """Calculates and exports performance metrics on sub-agent traffic."""
        total_msgs = len(self._events)
        total_bytes = sum(e.payload_size_bytes for e in self._events)
        total_durations = [e.duration_ms for e in self._events if e.duration_ms > 0]
        avg_duration = sum(total_durations) / len(total_durations) if total_durations else 0.0

        errors = sum(1 for e in self._events if e.status in ("error", "failed") or e.message_type == AgentMessageType.ERROR_REPORT.value)

        by_type: Dict[str, int] = defaultdict(int)
        for e in self._events:
            by_type[e.message_type] += 1

        return {
            "session_id": self.session_id,
            "total_messages": total_msgs,
            "total_bytes": total_bytes,
            "average_duration_ms": avg_duration,
            "error_count": errors,
            "error_rate": (errors / total_msgs) if total_msgs > 0 else 0.0,
            "message_distribution": dict(by_type),
            "active_delegations_count": len(self._active_delegations),
        }

    def subscribe(self, listener: Callable[[Dict[str, Any]], Any]) -> None:
        """Subscribes a callback listener for live message streams."""
        self._listeners.append(listener)

    def clear(self) -> None:
        """Clears events and metrics buffer."""
        self._events.clear()
        self._active_delegations.clear()
        self._communication_matrix.clear()
        self._traffic_bytes_matrix.clear()
