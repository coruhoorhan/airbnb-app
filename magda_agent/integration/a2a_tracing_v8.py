import uuid
import time
import json
import random
from typing import Dict, Any, List, Optional

class A2ATracerV8:
    """
    Enterprise tracing and distributed monitoring support for A2A delegated tasks v8.

    This module provides tracing capabilities by generating trace IDs, span IDs,
    tracking distributed A2A execution status, and supporting parent-child trace
    correlation across delegated tasks in the agent mesh. It also includes
    probabilistic sampling and context injection/extraction for distributed tracing.
    """

    def __init__(self, sample_rate: float = 1.0) -> None:
        """
        Initializes the A2ATracerV8.

        Args:
            sample_rate: The probability (0.0 to 1.0) that a trace will be sampled.
        """
        self.traces: Dict[str, Dict[str, Any]] = {}
        self.delegated_tasks: Dict[str, str] = {} # Maps task_id to trace_id
        self.sample_rate = sample_rate

    def should_sample(self) -> bool:
        """
        Determines whether a new trace should be sampled based on the sample_rate.

        Returns:
            bool: True if the trace should be sampled, False otherwise.
        """
        return random.random() <= self.sample_rate

    def start_trace(self, task_name: str, parent_trace_id: Optional[str] = None) -> Optional[str]:
        """
        Starts a new trace for a given task, optionally linked to a parent trace.
        Obeys the configured sample rate.

        Args:
            task_name: The name of the task being traced.
            parent_trace_id: The optional parent trace ID for distributed correlation.

        Returns:
            The generated trace ID if sampled, else None.
        """
        if not self.should_sample() and not parent_trace_id:
            # If there's a parent trace, we usually want to continue it.
            # If not sampled and no parent, we don't start a trace.
            return None

        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = {
            "task_name": task_name,
            "parent_trace_id": parent_trace_id,
            "start_time": time.time(),
            "end_time": None,
            "status": "in_progress",
            "spans": [],
            "monitoring_events": [],
            "baggage": {}
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

    def inject_context(self, trace_id: str, carrier: Dict[str, Any]) -> None:
        """
        Injects the trace context into a carrier (e.g., HTTP headers or JSON-RPC context)
        to propagate it across distributed boundaries.

        Args:
            trace_id: The ID of the trace.
            carrier: The dictionary to inject the context into.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        carrier["x-a2a-trace-id"] = trace_id
        baggage = self.traces[trace_id].get("baggage", {})
        if baggage:
            carrier["x-a2a-baggage"] = json.dumps(baggage)

    def extract_context(self, carrier: Dict[str, Any]) -> Optional[str]:
        """
        Extracts the trace context from a carrier.

        Args:
            carrier: The dictionary containing the context.

        Returns:
            The extracted trace ID if present, else None.
        """
        trace_id = carrier.get("x-a2a-trace-id")
        return trace_id

    def set_baggage(self, trace_id: str, key: str, value: Any) -> None:
        """
        Sets a baggage item for a trace, which will be propagated across services.

        Args:
            trace_id: The ID of the trace.
            key: The baggage key.
            value: The baggage value.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        self.traces[trace_id]["baggage"][key] = value

    def get_baggage(self, trace_id: str, key: str) -> Optional[Any]:
        """
        Gets a baggage item for a trace.

        Args:
            trace_id: The ID of the trace.
            key: The baggage key.

        Returns:
            The baggage value, or None if not found.

        Raises:
            KeyError: If the trace_id does not exist.
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace ID {trace_id} not found.")

        return self.traces[trace_id]["baggage"].get(key)

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
