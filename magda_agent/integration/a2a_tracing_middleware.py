from typing import Dict, Optional
import logging
from magda_agent.integration.a2a_tracing import A2ATracer

class A2ATracingMiddleware:
    """
    Middleware component for A2A communication to inject and extract OpenTelemetry trace IDs.
    Ensures trace context is propagated across distributed agent meshes.
    """

    @staticmethod
    def inject_trace_id(headers: Dict[str, str]) -> Dict[str, str]:
        """
        Injects the current active trace ID into outgoing request headers.
        If no trace ID is active in the current context, a new one is generated.

        Args:
            headers: The outgoing headers dictionary.

        Returns:
            Dict[str, str]: The headers dictionary with the trace ID injected.
        """
        injected_headers = headers.copy()
        try:
            injected_headers = A2ATracer.inject_headers(injected_headers)
            trace_id = A2ATracer.get_current_trace_id()
            if trace_id:
                logging.debug(f"[A2A Middleware] Injected trace ID {trace_id} into headers.")
        except Exception as e:
            logging.error(f"[A2A Middleware] Failed to inject trace ID: {e}")
        return injected_headers

    @staticmethod
    def extract_trace_id(headers: Dict[str, str]) -> Optional[str]:
        """
        Extracts the trace ID from incoming request headers and sets it in the current context.

        Args:
            headers: The incoming headers dictionary.

        Returns:
            Optional[str]: The extracted trace ID, or None if not found.
        """
        try:
            trace_id = A2ATracer.extract_from_headers(headers)
            if trace_id:
                A2ATracer.set_trace_id(trace_id)
                logging.debug(f"[A2A Middleware] Extracted and set trace ID {trace_id} from headers.")
            return trace_id
        except Exception as e:
            logging.error(f"[A2A Middleware] Failed to extract trace ID: {e}")
            return None
