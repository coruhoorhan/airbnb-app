import uuid
import time
from typing import Dict, Any, List, Optional
import json

class A2ATracerV5:
    """
    Enterprise tracing and monitoring support for A2A delegated tasks.

    This module provides tracing capabilities by generating trace IDs, span IDs,
    and recording events with their start and end times to monitor A2A delegations.
    """

    def __init__(self) -> None:
        """
        Initializes the A2ATracerV5 with an empty dictionary of traces.
        """
        self.traces: Dict[str, Dict[str, Any]] = {}

    def start_trace(self, task_name: str) -> str:
        """
        Starts a new trace for a given task.

        Args:
            task_name: The name of the task being traced.

        Returns:
            The generated trace ID.
        """
        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = {
            "task_name": task_name,
            "start_time": time.time(),
            "end_time": None,
            "status": "in_progress",
            "spans": []
        }
        return trace_id

    def end_trace(self, trace_id: str, status: str = "completed") -> None:
        """
        Ends an existing trace.

        Args:
            trace_id: The ID of the trace to end.
            status: The final status of the trace (e.g., 'completed', 'failed').

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
