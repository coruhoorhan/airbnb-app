"""
Agent Teams Distributed Tracing V9.

Inspired by Claude Agent SDK Agent Teams and OpenTelemetry W3C distributed tracing:
Propagates distributed trace context across sub-agents executing in isolated Git worktrees,
providing full visibility and causality correlation across parallel multi-agent tasks.
"""

import asyncio
import inspect
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


def generate_trace_id() -> str:
    """Generate 128-bit hex string for W3C trace ID."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate 64-bit hex string for W3C span ID."""
    return secrets.token_hex(8)


@dataclass
class TraceContext:
    """Represents a distributed W3C Trace Context propagating across sub-agent processes."""

    trace_id: str = field(default_factory=generate_trace_id)
    span_id: str = field(default_factory=generate_span_id)
    parent_span_id: Optional[str] = None
    trace_flags: str = "01"  # 01 = sampled
    baggage: Dict[str, str] = field(default_factory=dict)

    def to_w3c_traceparent(self) -> str:
        """Format as standard W3C traceparent header: 00-{trace_id}-{span_id}-{trace_flags}."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def from_w3c_traceparent(
        cls,
        header: str,
        baggage: Optional[Dict[str, str]] = None,
    ) -> "TraceContext":
        """Parse standard W3C traceparent header."""
        parts = header.strip().split("-")
        if len(parts) >= 4:
            return cls(
                trace_id=parts[1],
                span_id=parts[2],
                trace_flags=parts[3],
                baggage=baggage or {},
            )
        return cls()

    def inject_env(self, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Inject trace context into environment dictionary for sub-agent worktrees."""
        env = dict(base_env or {})
        env["TRACEPARENT"] = self.to_w3c_traceparent()
        env["MAGDA_TRACE_ID"] = self.trace_id
        env["MAGDA_SPAN_ID"] = self.span_id
        if self.parent_span_id:
            env["MAGDA_PARENT_SPAN_ID"] = self.parent_span_id
        if self.baggage:
            env["MAGDA_TRACE_BAGGAGE"] = json.dumps(self.baggage)
        return env

    @classmethod
    def extract_from_env(cls, env: Dict[str, str]) -> Optional["TraceContext"]:
        """Extract trace context from environment variables."""
        tp = env.get("TRACEPARENT")
        if tp:
            baggage = {}
            raw_b = env.get("MAGDA_TRACE_BAGGAGE")
            if raw_b:
                try:
                    baggage = json.loads(raw_b)
                except Exception:
                    pass
            ctx = cls.from_w3c_traceparent(tp, baggage=baggage)
            ctx.parent_span_id = env.get("MAGDA_PARENT_SPAN_ID")
            return ctx

        tid = env.get("MAGDA_TRACE_ID")
        sid = env.get("MAGDA_SPAN_ID")
        if tid and sid:
            return cls(
                trace_id=tid,
                span_id=sid,
                parent_span_id=env.get("MAGDA_PARENT_SPAN_ID"),
            )
        return None


@dataclass
class SpanRecord:
    """Represents a recorded execution span for a sub-agent task."""

    span_id: str
    trace_id: str
    name: str
    parent_span_id: Optional[str] = None
    agent_id: Optional[str] = None
    worktree_path: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "UNSET"  # OK, ERROR, UNSET
    error_message: Optional[str] = None

    def end(self, status: str = "OK", error: Optional[str] = None) -> None:
        """Mark span as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        self.status = status
        self.error_message = error

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentTeamsDistributedTracerV9:
    """
    Agent Teams Distributed Tracer V9.

    Orchestrates OpenTelemetry-compatible tracing across team sub-agents and worktrees.
    """

    def __init__(self, service_name: str = "magda_agent_teams"):
        self.service_name = service_name
        self._spans: Dict[str, SpanRecord] = {}
        self._trace_to_spans: Dict[str, List[str]] = {}

    def start_root_trace(
        self,
        name: str = "agent_team_root",
        baggage: Optional[Dict[str, str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Tuple[TraceContext, SpanRecord]:
        """Start a new root trace context."""
        ctx = TraceContext(
            trace_id=generate_trace_id(),
            span_id=generate_span_id(),
            parent_span_id=None,
            baggage=baggage or {},
        )

        span = SpanRecord(
            span_id=ctx.span_id,
            trace_id=ctx.trace_id,
            name=name,
            parent_span_id=None,
            start_time=time.time(),
            attributes=attributes or {},
        )

        self._record_span(span)
        return ctx, span

    def create_subagent_span(
        self,
        parent_context: TraceContext,
        agent_id: str,
        span_name: str,
        worktree_path: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Tuple[TraceContext, SpanRecord]:
        """
        Spawn a child trace context and span for a sub-agent executing in an isolated worktree.
        """
        child_span_id = generate_span_id()
        child_baggage = dict(parent_context.baggage)
        child_baggage["agent_id"] = agent_id
        if worktree_path:
            child_baggage["worktree_path"] = worktree_path

        child_ctx = TraceContext(
            trace_id=parent_context.trace_id,
            span_id=child_span_id,
            parent_span_id=parent_context.span_id,
            trace_flags=parent_context.trace_flags,
            baggage=child_baggage,
        )

        attrs = dict(attributes or {})
        attrs["service.name"] = self.service_name
        attrs["agent.id"] = agent_id
        if worktree_path:
            attrs["agent.worktree_path"] = worktree_path

        span = SpanRecord(
            span_id=child_span_id,
            trace_id=parent_context.trace_id,
            name=span_name,
            parent_span_id=parent_context.span_id,
            agent_id=agent_id,
            worktree_path=worktree_path,
            start_time=time.time(),
            attributes=attrs,
        )

        self._record_span(span)
        return child_ctx, span

    def _record_span(self, span: SpanRecord) -> None:
        self._spans[span.span_id] = span
        if span.trace_id not in self._trace_to_spans:
            self._trace_to_spans[span.trace_id] = []
        self._trace_to_spans[span.trace_id].append(span.span_id)

    def end_span(
        self,
        span_id: str,
        status: str = "OK",
        error: Optional[str] = None,
    ) -> Optional[SpanRecord]:
        """Mark span complete."""
        span = self._spans.get(span_id)
        if span:
            span.end(status=status, error=error)
        return span

    def get_spans_for_trace(self, trace_id: str) -> List[SpanRecord]:
        """Get all spans associated with a given trace_id."""
        span_ids = self._trace_to_spans.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def build_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Build hierarchical representation of all spans in a trace."""
        spans = self.get_spans_for_trace(trace_id)
        if not spans:
            return {}

        nodes = {s.span_id: {**s.to_dict(), "children": []} for s in spans}
        root_nodes = []

        for sid, node in nodes.items():
            parent_id = node.get("parent_span_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                root_nodes.append(node)

        return {
            "trace_id": trace_id,
            "root_spans": root_nodes,
            "total_spans": len(spans),
        }

    def export_all_spans(self) -> List[Dict[str, Any]]:
        """Export all recorded spans as JSON serializable list."""
        return [s.to_dict() for s in self._spans.values()]

    def clear_traces(self) -> None:
        """Clear all stored traces and spans."""
        self._spans.clear()
        self._trace_to_spans.clear()
