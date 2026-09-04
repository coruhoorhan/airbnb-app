import uuid
import time
from typing import Dict, Any, List, Optional
import json

class A2ATracerV6:
    """
    Enhanced enterprise tracing and distributed monitoring support for A2A delegated tasks.

    This module provides tracing capabilities by generating trace IDs, span IDs,
    tracking distributed A2A execution status, and supporting parent-child trace
    correlation across delegated tasks in the agent mesh.
    """

    def __init__(self) -> None:
        """
        Initializes the A2ATracerV6 with an empty dictionary of traces and active delegations.
        """
        self.traces: Dict[str, Dict[str, Any]] = {}
        self.delegated_tasks: Dict[str, str] = {} # Maps task_id to trace_id

    def start_trace(self, task_name: str, parent_trace_id: Optional[str] = None) -> str:
        """
        Starts a new trace for a given task, optionally linked to a parent trace.

        Args:
            task_name: The name of the task being traced.
            parent_trace_id: The optional parent trace ID for distributed correlation.

        Returns:
            The generated trace ID.
        """
        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = {
            "task_name": task_name,
            "parent_trace_id": parent_trace_id,
            "start_time": time.time(),
            "end_time": None,
            "status": "in_progress",
            "spans": [],
            "monitoring_events": []
        }
        return trace_id

    def end_trace(self, trace_id: str, status: str = "completed") -> None:
        """
        Ends an existing trace.

        Args:
            trace_id: The ID of the trace to end.
            status: The final status of the trace (e.g., 'completed', 'failed', 'timeout').

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        self.traces[trace_id]["end_time"] = time.time()
        self.traces[trace_id]["status"] = status

    def add_span(self, trace_id: str, span_name: str, duration_ms: float) -> str:
        """
        Adds a span to an existing trace.

        Args:
            trace_id: The ID of the trace.
            span_name: The name of the span or operation.
            duration_ms: The duration of the operation in milliseconds.

        Returns:
            The generated span ID.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        span_id = str(uuid.uuid4())
        span = {
            "span_id": span_id,
            "span_name": span_name,
            "duration_ms": duration_ms,
            "timestamp": time.time()
        }
        self.traces[trace_id]["spans"].append(span)
        return span_id

    def log_monitoring_event(self, trace_id: str, event_type: str, details: Dict[str, Any]) -> None:
        """
        Logs a distributed monitoring event associated with a trace.

        Args:
            trace_id: The ID of the trace.
            event_type: Type of the event (e.g., 'network_latency', 'node_failure').
            details: Additional details about the event.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        event = {
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details
        }
        self.traces[trace_id]["monitoring_events"].append(event)

    def attach_delegated_task(self, trace_id: str, task_id: str) -> None:
        """
        Attaches an A2A delegated task to a trace for tracking.

        Args:
            trace_id: The ID of the trace.
            task_id: The delegated task ID.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")
        self.delegated_tasks[task_id] = trace_id

    def get_trace_for_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the trace associated with a specific delegated task.

        Args:
            task_id: The ID of the delegated task.

        Returns:
            The trace dictionary, or None if not found.
        """
        trace_id = self.delegated_tasks.get(task_id)
        if not trace_id:
            return None
        return self.traces.get(trace_id)

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """
        Retrieves the details of a trace.

        Args:
            trace_id: The ID of the trace.

        Returns:
            A dictionary containing the trace details.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        return self.traces[trace_id]

    def export_traces(self) -> str:
        """
        Exports all traces as a JSON string.

        Returns:
            A JSON string representing all traces.
        """
        return json.dumps(self.traces)
