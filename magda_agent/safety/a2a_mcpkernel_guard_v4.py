"""
MCPKernel A2A Guardrail Runtime Checkpoint V4.

Inspired by MCPKernel taint tracking sandbox and A2A peer delegation standards:
Extends A2A tool execution hooks to evaluate peer payload parameters dynamically
through safety checkpoints, detecting tainted peer data and strictly blocking
unsafe execution.
"""

import asyncio
import inspect
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

try:
    from magda_agent.safety.taint import (
        is_tainted,
        mark_tainted,
        sanitize,
    )
except (ImportError, ModuleNotFoundError):
    import importlib.util
    from pathlib import Path

    file_path = Path(__file__).resolve().parent / "taint.py"
    if file_path.exists():
        spec = importlib.util.spec_from_file_location("taint", file_path)
        _taint_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_taint_mod)
        is_tainted = _taint_mod.is_tainted
        mark_tainted = _taint_mod.mark_tainted
        sanitize = _taint_mod.sanitize
    else:
        def mark_tainted(val: Any, *args, **kwargs) -> Any:
            return val

        def is_tainted(val: Any) -> bool:
            return False

        def sanitize(val: Any) -> Any:
            return val

logger = logging.getLogger(__name__)


class A2AGuardCheckpoint(str, Enum):
    PEER_AUTHENTICATION = "peer_authentication"
    TAINT_EVALUATION = "taint_evaluation"
    SENSITIVE_ARG_POLICY = "sensitive_arg_policy"
    CAPABILITY_BOUNDARY = "capability_boundary"


class A2AGuardrailViolationError(Exception):
    """Raised when an A2A peer tool execution violates runtime guardrail checkpoints."""

    def __init__(self, checkpoint: A2AGuardCheckpoint, tool_name: str, sender_id: str, reason: str):
        super().__init__(
            f"A2A MCPKernel Guardrail V4 blocked peer '{sender_id}' calling '{tool_name}' "
            f"at [{checkpoint.value}]: {reason}"
        )
        self.checkpoint = checkpoint
        self.tool_name = tool_name
        self.sender_id = sender_id
        self.reason = reason


@dataclass
class A2AToolCallPayload:
    """Standardized tool call payload traversing A2A peer delegation mesh."""

    delegation_id: str = field(default_factory=lambda: f"del_{uuid.uuid4().hex[:8]}")
    sender_agent_id: str = "unknown_peer"
    target_tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    is_peer_trusted: bool = False
    security_tier: str = "standard"  # enterprise, standard, sandboxed, untrusted
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AToolCallPayload":
        return cls(
            delegation_id=data.get("delegation_id") or f"del_{uuid.uuid4().hex[:8]}",
            sender_agent_id=data.get("sender_agent_id", "unknown_peer"),
            target_tool_name=data.get("target_tool_name") or data.get("tool_name", ""),
            arguments=dict(data.get("arguments") or {}),
            is_peer_trusted=bool(data.get("is_peer_trusted", False)),
            security_tier=data.get("security_tier", "standard"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class A2AGuardCheckpointResult:
    """Outcome of evaluating an A2A tool call against safety checkpoints."""

    is_allowed: bool
    blocked: bool
    failed_checkpoint: Optional[A2AGuardCheckpoint] = None
    reason: Optional[str] = None
    tainted_parameters: List[str] = field(default_factory=list)
    audit_id: str = field(default_factory=lambda: f"a2a_guard_{uuid.uuid4().hex[:8]}")
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_allowed": self.is_allowed,
            "blocked": self.blocked,
            "failed_checkpoint": self.failed_checkpoint.value if self.failed_checkpoint else None,
            "reason": self.reason,
            "tainted_parameters": self.tainted_parameters,
            "audit_id": self.audit_id,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class A2AExecutionResponse:
    """Result of intercepting and executing a peer tool call."""

    success: bool
    tool_name: str
    sender_id: str
    result: Any = None
    error: Optional[str] = None
    blocked_by_guard: bool = False
    checkpoint_result: Optional[A2AGuardCheckpointResult] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "sender_id": self.sender_id,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "blocked_by_guard": self.blocked_by_guard,
            "duration_ms": self.duration_ms,
        }


class A2AMCPKernelExecutionHookV4:
    """
    A2A MCPKernel Execution Hook V4.

    Evaluates peer tool delegations against runtime safety checkpoints:
    1. Authenticates peer trust level.
    2. Tags and evaluates tainted parameter variables from peer payloads.
    3. Blocks tainted peer variables from reaching sensitive parameters.
    4. Enforces capability boundaries.
    """

    DEFAULT_SENSITIVE_ARGS = {
        "path", "filepath", "filename", "directory", "dir",
        "cmd", "command", "exec", "script", "payload", "query", "sql", "code", "url",
    }

    DEFAULT_SENSITIVE_TOOLS = {
        "read_file", "write_file", "delete_file",
        "system_execute_code", "execute_code", "bash", "run_shell_command",
        "sql_query", "fetch_url",
    }

    def __init__(
        self,
        trusted_peer_ids: Optional[Set[str]] = None,
        sensitive_args: Optional[Set[str]] = None,
        sensitive_tools: Optional[Set[str]] = None,
        strict_taint_blocking: bool = True,
    ):
        self.trusted_peer_ids = trusted_peer_ids or set()
        self.sensitive_args = sensitive_args or set(self.DEFAULT_SENSITIVE_ARGS)
        self.sensitive_tools = sensitive_tools or set(self.DEFAULT_SENSITIVE_TOOLS)
        self.strict_taint_blocking = strict_taint_blocking
        self._audit_trail: List[A2AExecutionResponse] = []

    def is_argument_sensitive(self, tool_name: str, arg_name: str) -> bool:
        """Check if an argument is classified as sensitive."""
        if arg_name.lower() in self.sensitive_args:
            return True
        if tool_name in self.sensitive_tools and any(s in arg_name.lower() for s in ["path", "cmd", "command", "file", "code"]):
            return True
        return False

    def evaluate_peer_tool_call(
        self,
        payload: Union[A2AToolCallPayload, Dict[str, Any]],
    ) -> A2AGuardCheckpointResult:
        """
        Evaluate incoming peer tool call against all safety checkpoints.
        """
        start_t = time.perf_counter()
        if isinstance(payload, dict):
            payload = A2AToolCallPayload.from_dict(payload)

        # 1. Peer Authentication Checkpoint
        is_trusted = payload.is_peer_trusted or (payload.sender_agent_id in self.trusted_peer_ids)

        # 2. Taint Evaluation & Sensitive Argument Policy Checkpoint
        tainted_args: List[str] = []
        for arg_name, arg_val in payload.arguments.items():
            # Check if value is already marked tainted or originated from an untrusted peer
            val_tainted = is_tainted(arg_val)

            # Untrusted/sandboxed peers automatically taint parameters
            if not is_trusted and payload.security_tier in ("untrusted", "sandboxed", "standard"):
                val_tainted = True

            if val_tainted:
                tainted_args.append(arg_name)
                # If tainted value reaches sensitive argument -> Block!
                if self.is_argument_sensitive(payload.target_tool_name, arg_name) and self.strict_taint_blocking:
                    dur = (time.perf_counter() - start_t) * 1000.0
                    reason = (
                        f"Tainted parameter '{arg_name}' from peer '{payload.sender_agent_id}' "
                        f"cannot be passed to sensitive argument in tool '{payload.target_tool_name}'"
                    )
                    return A2AGuardCheckpointResult(
                        is_allowed=False,
                        blocked=True,
                        failed_checkpoint=A2AGuardCheckpoint.SENSITIVE_ARG_POLICY,
                        reason=reason,
                        tainted_parameters=tainted_args,
                        execution_time_ms=dur,
                    )

        # 3. Capability Boundary Checkpoint
        if payload.security_tier == "untrusted" and payload.target_tool_name in self.sensitive_tools:
            dur = (time.perf_counter() - start_t) * 1000.0
            reason = f"Untrusted peer '{payload.sender_agent_id}' cannot execute restricted tool '{payload.target_tool_name}'"
            return A2AGuardCheckpointResult(
                is_allowed=False,
                blocked=True,
                failed_checkpoint=A2AGuardCheckpoint.CAPABILITY_BOUNDARY,
                reason=reason,
                tainted_parameters=tainted_args,
                execution_time_ms=dur,
            )

        dur = (time.perf_counter() - start_t) * 1000.0
        return A2AGuardCheckpointResult(
            is_allowed=True,
            blocked=False,
            failed_checkpoint=None,
            reason="All A2A MCPKernel safety checkpoints passed.",
            tainted_parameters=tainted_args,
            execution_time_ms=dur,
        )

    def intercept_and_execute(
        self,
        payload: Union[A2AToolCallPayload, Dict[str, Any]],
        tool_func: Callable[..., Any],
    ) -> A2AExecutionResponse:
        """
        Intercept peer tool call synchronously, running evaluation checkpoints before execution.
        """
        start_t = time.perf_counter()
        if isinstance(payload, dict):
            payload = A2AToolCallPayload.from_dict(payload)

        check_res = self.evaluate_peer_tool_call(payload)

        if not check_res.is_allowed or check_res.blocked:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"A2A Guardrail Checkpoint Block: {check_res.reason}"
            logger.warning(err_msg)
            res = A2AExecutionResponse(
                success=False,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                error=err_msg,
                blocked_by_guard=True,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        # Sanitize arguments for execution if safe
        clean_args = sanitize(payload.arguments)

        try:
            raw_result = tool_func(**clean_args)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = A2AExecutionResponse(
                success=True,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                result=raw_result,
                blocked_by_guard=False,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = A2AExecutionResponse(
                success=False,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                error=str(ex),
                blocked_by_guard=False,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    async def intercept_and_execute_async(
        self,
        payload: Union[A2AToolCallPayload, Dict[str, Any]],
        tool_func: Callable[..., Any],
    ) -> A2AExecutionResponse:
        """
        Intercept peer tool call asynchronously, running evaluation checkpoints before execution.
        """
        start_t = time.perf_counter()
        if isinstance(payload, dict):
            payload = A2AToolCallPayload.from_dict(payload)

        check_res = self.evaluate_peer_tool_call(payload)

        if not check_res.is_allowed or check_res.blocked:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"A2A Guardrail Checkpoint Block: {check_res.reason}"
            logger.warning(err_msg)
            res = A2AExecutionResponse(
                success=False,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                error=err_msg,
                blocked_by_guard=True,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        clean_args = sanitize(payload.arguments)

        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_result = await tool_func(**clean_args)
            else:
                raw_result = tool_func(**clean_args)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = A2AExecutionResponse(
                success=True,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                result=raw_result,
                blocked_by_guard=False,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = A2AExecutionResponse(
                success=False,
                tool_name=payload.target_tool_name,
                sender_id=payload.sender_agent_id,
                error=str(ex),
                blocked_by_guard=False,
                checkpoint_result=check_res,
                duration_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    def get_audit_trail(self) -> List[A2AExecutionResponse]:
        """Retrieve audit history."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit history."""
        self._audit_trail.clear()
