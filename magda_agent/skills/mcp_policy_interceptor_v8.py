"""
MCP Action Tool Policy Interceptor V8.

Inspired by MCP action tool expansion and ACS runtime safety standards:
Provides a centralized runtime policy interceptor tailored for dynamic MCP action
tools, strictly validating payloads, catching tainted input data, and blocking
policy-violating execution.
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

    file_path = Path(__file__).resolve().parent.parent / "safety" / "taint.py"
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


class MCPPolicyInterceptAction(str, Enum):
    ALLOW = "allow"
    BLOCK_TAINTED = "block_tainted"
    BLOCK_FORBIDDEN = "block_forbidden"
    BLOCK_INVALID = "block_invalid"


class MCPActionToolPolicyViolationError(Exception):
    """Raised when an MCP action tool call violates runtime interception policy."""

    def __init__(self, tool_name: str, action: MCPPolicyInterceptAction, reason: str):
        super().__init__(
            f"MCP Action Tool Policy Interceptor V8 blocked '{tool_name}' [{action.value}]: {reason}"
        )
        self.tool_name = tool_name
        self.action = action
        self.reason = reason


@dataclass
class MCPActionPolicyInterceptOutcome:
    """Outcome of intercepting and executing an MCP action tool call."""

    success: bool
    allowed: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    action: MCPPolicyInterceptAction = MCPPolicyInterceptAction.ALLOW
    taint_detected: bool = False
    tainted_fields: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: f"mcp_v8_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "allowed": self.allowed,
            "tool_name": self.tool_name,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "action": self.action.value if isinstance(self.action, MCPPolicyInterceptAction) else str(self.action),
            "taint_detected": self.taint_detected,
            "tainted_fields": self.tainted_fields,
            "execution_time_ms": self.execution_time_ms,
            "audit_id": self.audit_id,
        }


class MCPActionToolPolicyInterceptorV8:
    """
    MCP Action Tool Policy Interceptor V8.

    Centralized interceptor enforcing strict payload validation, taint filtering,
    and action safety rules for dynamic MCP tools.
    """

    DEFAULT_SENSITIVE_ARGS = {
        "path", "filepath", "filename", "directory", "cmd", "command",
        "script", "exec", "query", "sql", "code", "payload", "url",
    }

    DEFAULT_FORBIDDEN_TOOLS = {
        "format_disk", "kill_system", "drop_all_tables",
    }

    def __init__(
        self,
        forbidden_tools: Optional[Set[str]] = None,
        sensitive_arguments: Optional[Set[str]] = None,
        block_all_tainted_inputs: bool = True,
    ):
        self.forbidden_tools = set(forbidden_tools or self.DEFAULT_FORBIDDEN_TOOLS)
        self.sensitive_arguments = set(sensitive_arguments or self.DEFAULT_SENSITIVE_ARGS)
        self.block_all_tainted_inputs = block_all_tainted_inputs

        self._registered_tools: Dict[str, Callable[..., Any]] = {}
        self._custom_validators: Dict[str, List[Callable[[Dict[str, Any]], Tuple[bool, str]]]] = {}
        self._audit_trail: List[MCPActionPolicyInterceptOutcome] = []

    def register_tool(
        self,
        tool_name: str,
        func: Callable[..., Any],
    ) -> None:
        """Register a dynamic tool function with the interceptor."""
        self._registered_tools[tool_name] = func

    def add_custom_validator(
        self,
        tool_name: str,
        validator: Callable[[Dict[str, Any]], Tuple[bool, str]],
    ) -> None:
        """Add custom programmatic argument validator for a tool."""
        if tool_name not in self._custom_validators:
            self._custom_validators[tool_name] = []
        self._custom_validators[tool_name].append(validator)

    def evaluate_payload(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, MCPPolicyInterceptAction, str, List[str]]:
        """
        Evaluate arguments for taint, forbidden actions, or malformed data.
        Returns (is_allowed, action, reason, tainted_fields).
        """
        # 1. Check forbidden tools
        if tool_name in self.forbidden_tools:
            return (
                False,
                MCPPolicyInterceptAction.BLOCK_FORBIDDEN,
                f"Action tool '{tool_name}' is blacklisted by runtime policy.",
                [],
            )

        # 2. Check taint on arguments
        tainted_fields = []
        for k, v in arguments.items():
            if is_tainted(v):
                tainted_fields.append(k)

        if tainted_fields:
            # Check if any tainted arg is sensitive or if strict blocking is active
            has_sensitive_taint = any(
                f.lower() in self.sensitive_arguments or any(s in f.lower() for s in ["path", "cmd", "file", "code"])
                for f in tainted_fields
            )
            if self.block_all_tainted_inputs or has_sensitive_taint:
                reason = f"Tainted input data detected in argument(s): {tainted_fields}"
                return False, MCPPolicyInterceptAction.BLOCK_TAINTED, reason, tainted_fields

        # 3. Custom tool validators
        if tool_name in self._custom_validators:
            for val_fn in self._custom_validators[tool_name]:
                ok, reason = val_fn(arguments)
                if not ok:
                    return False, MCPPolicyInterceptAction.BLOCK_INVALID, reason, tainted_fields

        return True, MCPPolicyInterceptAction.ALLOW, "Payload passed all policy checks.", tainted_fields

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_func: Optional[Callable[..., Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPActionPolicyInterceptOutcome:
        """Synchronously intercept and execute tool."""
        start_t = time.perf_counter()
        target_fn = tool_func or self._registered_tools.get(tool_name)

        if target_fn is None:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"Tool '{tool_name}' not found in interceptor registry."
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=False,
                tool_name=tool_name,
                error=err_msg,
                action=MCPPolicyInterceptAction.BLOCK_INVALID,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        is_allowed, action, reason, tainted_fields = self.evaluate_payload(tool_name, arguments, context)

        if not is_allowed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            logger.warning(f"MCP Action Tool Interceptor V8 blocked '{tool_name}': {reason}")
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=False,
                tool_name=tool_name,
                error=reason,
                action=action,
                taint_detected=len(tainted_fields) > 0,
                tainted_fields=tainted_fields,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        clean_args = sanitize(arguments)

        try:
            raw_result = target_fn(**clean_args)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = MCPActionPolicyInterceptOutcome(
                success=True,
                allowed=True,
                tool_name=tool_name,
                result=raw_result,
                action=MCPPolicyInterceptAction.ALLOW,
                taint_detected=False,
                tainted_fields=[],
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=True,
                tool_name=tool_name,
                error=str(ex),
                action=MCPPolicyInterceptAction.ALLOW,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    async def execute_async(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_func: Optional[Callable[..., Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPActionPolicyInterceptOutcome:
        """Asynchronously intercept and execute tool."""
        start_t = time.perf_counter()
        target_fn = tool_func or self._registered_tools.get(tool_name)

        if target_fn is None:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"Tool '{tool_name}' not found in interceptor registry."
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=False,
                tool_name=tool_name,
                error=err_msg,
                action=MCPPolicyInterceptAction.BLOCK_INVALID,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        is_allowed, action, reason, tainted_fields = self.evaluate_payload(tool_name, arguments, context)

        if not is_allowed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            logger.warning(f"MCP Action Tool Interceptor V8 blocked '{tool_name}': {reason}")
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=False,
                tool_name=tool_name,
                error=reason,
                action=action,
                taint_detected=len(tainted_fields) > 0,
                tainted_fields=tainted_fields,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        clean_args = sanitize(arguments)

        try:
            if inspect.iscoroutinefunction(target_fn):
                raw_result = await target_fn(**clean_args)
            else:
                raw_result = target_fn(**clean_args)

            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = MCPActionPolicyInterceptOutcome(
                success=True,
                allowed=True,
                tool_name=tool_name,
                result=raw_result,
                action=MCPPolicyInterceptAction.ALLOW,
                taint_detected=False,
                tainted_fields=[],
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = MCPActionPolicyInterceptOutcome(
                success=False,
                allowed=True,
                tool_name=tool_name,
                error=str(ex),
                action=MCPPolicyInterceptAction.ALLOW,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    def get_audit_trail(self) -> List[MCPActionPolicyInterceptOutcome]:
        """Retrieve recorded audit history."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit history."""
        self._audit_trail.clear()
