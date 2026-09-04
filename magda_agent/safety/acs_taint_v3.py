"""ACS Guardrails Taint Tracking V3 module.

Inspired by MCPKernel/ACS patterns: Implement a taint-tracking guardrail layer
that prevents sensitive execution output from being inadvertently re-executed or broadcast via A2A.
"""

import inspect
import logging
from typing import Any, Callable, Dict, Optional, Set

from magda_agent.safety.policy import PolicyLayer
from magda_agent.safety.taint_tracking_v2 import (
    PolicyViolationError,
    TaintTrackerV2,
    SandboxExecutionEnvironmentV2,
    is_tainted,
    sanitize,
)


class ACSTaintViolationError(PolicyViolationError):
    """Raised when tainted data violates ACS guardrail policy during execution or A2A broadcast."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ACSTaintGuardrailV3:
    """ACS Taint Tracking Guardrail V3 layer.

    Intercepts tool execution and A2A broadcasting to enforce taint checks,
    preventing tainted or sensitive outputs from being re-executed or broadcast.
    """

    def __init__(
        self,
        policy_layer: Optional[PolicyLayer] = None,
        tracker: Optional[TaintTrackerV2] = None,
        sensitive_tools: Optional[Set[str]] = None,
        block_tainted_a2a_broadcast: bool = True,
    ) -> None:
        """Initialize ACSTaintGuardrailV3.

        Args:
            policy_layer: Optional policy layer instance for evaluating tool permissions.
            tracker: Optional TaintTrackerV2 instance for tracking taint origins.
            sensitive_tools: Optional set of tool names that are considered sensitive.
            block_tainted_a2a_broadcast: Whether to block tainted payloads from A2A broadcasting.
        """
        self.logger = logging.getLogger(__name__)
        self.policy_layer = policy_layer or PolicyLayer()
        self.tracker = tracker or TaintTrackerV2()
        self.sandbox = SandboxExecutionEnvironmentV2(self.tracker)
        self.sensitive_tools = set(sensitive_tools) if sensitive_tools is not None else set()
        self.block_tainted_a2a_broadcast = block_tainted_a2a_broadcast

    def taint_data(self, data: Any, origin: str) -> Any:
        """Mark external data or sensitive execution output as tainted.

        Args:
            data: Data to taint.
            origin: Origin identifier of the tainted data.

        Returns:
            Tainted data wrapper object.
        """
        return self.tracker.taint(data, origin)

    def is_tainted(self, data: Any) -> bool:
        """Check if data or nested data structures contain tainted items.

        Args:
            data: Data to check.

        Returns:
            True if data is tainted, False otherwise.
        """
        return self.tracker.is_tainted(data)

    def get_origins(self, data: Any) -> Set[str]:
        """Get taint origin identifiers associated with the data.

        Args:
            data: Tainted data to inspect.

        Returns:
            Set of origin strings.
        """
        return self.tracker.get_origins(data)

    def sanitize(self, data: Any) -> Any:
        """Sanitize tainted data back into normal python primitives.

        Args:
            data: Data to sanitize.

        Returns:
            Sanitized untainted data.
        """
        return self.tracker.sanitize(data)

    def validate_tool_execution(self, tool_name: str, kwargs: Dict[str, Any]) -> None:
        """Validate tool execution parameters against taint policy and policy layer.

        Args:
            tool_name: Name of the tool to execute.
            kwargs: Keyword arguments for the tool.

        Raises:
            ACSTaintViolationError: If tool is sensitive and receives tainted input,
                or if policy layer denies execution.
        """
        # Check if sensitive tool receives tainted input (prevents re-executing tainted output)
        if tool_name in self.sensitive_tools or self.is_tainted(kwargs):
            if self.is_tainted(kwargs):
                origins = self.get_origins(kwargs)
                msg = f"Tainted payload blocked from re-execution in tool '{tool_name}' (origins: {origins})."
                self.logger.warning(msg)
                raise ACSTaintViolationError(
                    msg, details={"tool_name": tool_name, "origins": list(origins)}
                )

        # Check policy layer rules
        allow, explanation = self.policy_layer.evaluate(tool_name, **kwargs)
        if not allow:
            msg = f"Tool execution for '{tool_name}' blocked by policy layer: {explanation}"
            self.logger.warning(msg)
            raise ACSTaintViolationError(
                msg, details={"tool_name": tool_name, "explanation": explanation}
            )

    def validate_a2a_broadcast(self, payload: Any, target_agent_id: Optional[str] = None) -> None:
        """Validate payload before broadcasting via A2A protocol.

        Args:
            payload: Message or data payload to be broadcast over A2A.
            target_agent_id: Optional ID of recipient agent.

        Raises:
            ACSTaintViolationError: If payload contains tainted data and block_tainted_a2a_broadcast is True.
        """
        if self.block_tainted_a2a_broadcast and self.is_tainted(payload):
            origins = self.get_origins(payload)
            msg = f"Tainted payload blocked from A2A broadcast to target '{target_agent_id}' (origins: {origins})."
            self.logger.warning(msg)
            raise ACSTaintViolationError(
                msg, details={"target_agent_id": target_agent_id, "origins": list(origins)}
            )

    def execute_tool(self, tool_func: Callable[..., Any], tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool function wrapped with ACS V3 taint tracking guardrails.

        Args:
            tool_func: Tool function to execute.
            tool_name: Identifier name of the tool.
            **kwargs: Arguments to pass to the tool.

        Returns:
            Result of tool execution, tainted if any inputs were tainted.
        """
        self.validate_tool_execution(tool_name, kwargs)

        if inspect.iscoroutinefunction(tool_func):
            async def async_wrapper() -> Any:
                return await self.sandbox.execute_async(tool_func, **kwargs)
            return async_wrapper()

        return self.sandbox.execute(tool_func, **kwargs)

    def broadcast_a2a_payload(
        self, broadcast_func: Callable[..., Any], payload: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Safely broadcast an A2A message payload after validating it against taint checks.

        Args:
            broadcast_func: Function responsible for performing the A2A broadcast.
            payload: Payload data to broadcast.
            *args: Additional positional arguments for broadcast_func.
            **kwargs: Additional keyword arguments for broadcast_func.

        Returns:
            Result of broadcast_func execution.
        """
        target_agent = kwargs.get("target_agent_id") or kwargs.get("agent_id")
        self.validate_a2a_broadcast(payload, target_agent_id=target_agent)
        return broadcast_func(payload, *args, **kwargs)
