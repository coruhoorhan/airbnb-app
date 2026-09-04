"""
MCPKernel Taint Tracking Sandbox V3.

Inspired by MCPKernel runtime safety standards: Provides a robust runtime
sandbox wrapper for MCP tool execution that tracks tainted inputs (e.g., untrusted
user strings, web scrapes, external payloads) and strictly blocks them from reaching
sensitive tool arguments (e.g., file paths, shell commands, SQL queries, system scripts).
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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

try:
    from magda_agent.safety.taint import (
        PolicyViolationError as BasePolicyViolationError,
        SandboxExecutionEnvironment,
        TaintTracker,
        TaintedData as BaseTaintedData,
        TaintedString as BaseTaintedString,
        is_tainted as base_is_tainted,
        mark_tainted as base_mark_tainted,
        sanitize as base_sanitize,
    )
except (ImportError, ModuleNotFoundError):
    import importlib.util
    from pathlib import Path

    file_path = Path(__file__).resolve().parent / "taint.py"
    if file_path.exists():
        spec = importlib.util.spec_from_file_location("taint", file_path)
        _taint_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_taint_mod)
        BasePolicyViolationError = _taint_mod.PolicyViolationError
        SandboxExecutionEnvironment = _taint_mod.SandboxExecutionEnvironment
        TaintTracker = _taint_mod.TaintTracker
        BaseTaintedData = _taint_mod.TaintedData
        BaseTaintedString = _taint_mod.TaintedString
        base_is_tainted = _taint_mod.is_tainted
        base_mark_tainted = _taint_mod.mark_tainted
        base_sanitize = _taint_mod.sanitize
    else:
        class BasePolicyViolationError(Exception):
            pass

        class BaseTaintedData:
            def __init__(self, value: Any):
                self.value = value

        class BaseTaintedString(BaseTaintedData, str):
            def __new__(cls, value: str):
                return str.__new__(cls, value)

        def base_mark_tainted(s: Any) -> Any:
            if isinstance(s, str) and not isinstance(s, BaseTaintedString):
                return BaseTaintedString(s)
            elif isinstance(s, list):
                return [base_mark_tainted(item) for item in s]
            elif isinstance(s, dict):
                return {base_mark_tainted(k): base_mark_tainted(v) for k, v in s.items()}
            return s

        def base_is_tainted(s: Any) -> bool:
            if isinstance(s, BaseTaintedData):
                return True
            if isinstance(s, list):
                return any(base_is_tainted(item) for item in s)
            if isinstance(s, dict):
                return any(base_is_tainted(k) or base_is_tainted(v) for k, v in s.items())
            return False

        def base_sanitize(s: Any) -> Any:
            if isinstance(s, BaseTaintedData):
                return base_sanitize(getattr(s, "value", str(s)))
            elif isinstance(s, list):
                return [base_sanitize(item) for item in s]
            elif isinstance(s, dict):
                return {base_sanitize(k): base_sanitize(v) for k, v in s.items()}
            return s

logger = logging.getLogger(__name__)


class TaintLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaintPolicyAction(str, Enum):
    BLOCK = "block"
    SANITIZE = "sanitize"
    AUDIT_ONLY = "audit_only"


class MCPKernelTaintViolationError(BasePolicyViolationError):
    """Raised when tainted data is passed to a sensitive argument in violation of policy."""

    def __init__(
        self,
        tool_name: str,
        argument_name: str,
        reason: str,
        taint_origin: str = "unknown",
        taint_level: str = "high",
    ):
        super().__init__(
            f"Taint policy violation in tool '{tool_name}' on sensitive argument '{argument_name}': "
            f"{reason} (origin={taint_origin}, level={taint_level})"
        )
        self.tool_name = tool_name
        self.argument_name = argument_name
        self.reason = reason
        self.taint_origin = taint_origin
        self.taint_level = taint_level


@dataclass
class TaintMetadata:
    """Metadata detailing origin and propagation of tainted data."""

    origin: str = "untrusted_input"
    level: TaintLevel = TaintLevel.HIGH
    timestamp: float = field(default_factory=time.time)
    propagation_path: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value if isinstance(self.level, TaintLevel) else str(self.level)
        return d


class TaintedData(BaseTaintedData):
    """Extended Base class for tainted data wrappers."""

    def __init__(self, value: Any, metadata: Optional[TaintMetadata] = None):
        super().__init__(value)
        self._taint_metadata = metadata or TaintMetadata()

    @property
    def taint_metadata(self) -> TaintMetadata:
        return self._taint_metadata

    @property
    def raw_value(self) -> Any:
        return self.value


class TaintedString(BaseTaintedString, TaintedData):
    """A string subclass carrying taint metadata."""

    def __new__(
        cls,
        value: Any,
        metadata: Optional[TaintMetadata] = None,
        origin: str = "untrusted_input",
        level: Union[TaintLevel, str] = TaintLevel.HIGH,
    ):
        obj = str.__new__(cls, str(value))
        if metadata is None:
            if isinstance(level, str):
                try:
                    level = TaintLevel(level.lower())
                except ValueError:
                    level = TaintLevel.HIGH
            metadata = TaintMetadata(origin=origin, level=level)
        obj.value = str(value)
        obj._taint_metadata = metadata
        return obj

    @property
    def taint_metadata(self) -> TaintMetadata:
        return self._taint_metadata

    @property
    def raw_value(self) -> str:
        return self.value


def mark_tainted(
    val: Any,
    origin: str = "untrusted_user_input",
    level: Union[TaintLevel, str] = TaintLevel.HIGH,
    tags: Optional[List[str]] = None,
) -> Any:
    """
    Recursively mark a value, list, dictionary, or set as tainted.
    """
    if isinstance(level, str):
        try:
            level = TaintLevel(level.lower())
        except ValueError:
            level = TaintLevel.HIGH

    meta = TaintMetadata(
        origin=origin,
        level=level,
        tags=tags or [],
        propagation_path=[origin],
    )

    if isinstance(val, str):
        return TaintedString(val, metadata=meta)

    if isinstance(val, dict):
        return {
            k: mark_tainted(v, origin=origin, level=level, tags=tags)
            for k, v in val.items()
        }

    if isinstance(val, list):
        return [mark_tainted(item, origin=origin, level=level, tags=tags) for item in val]

    if isinstance(val, tuple):
        return tuple(mark_tainted(item, origin=origin, level=level, tags=tags) for item in val)

    if isinstance(val, set):
        return {mark_tainted(item, origin=origin, level=level, tags=tags) for item in val}

    if hasattr(val, "_taint_metadata"):
        return val
    try:
        val._taint_metadata = meta
        return val
    except Exception:
        return val


def is_tainted(val: Any) -> bool:
    """
    Recursively check if a value or any nested element is tainted.
    """
    if val is None:
        return False

    if isinstance(val, (BaseTaintedData, TaintedData)) or hasattr(val, "_taint_metadata"):
        return True

    if isinstance(val, dict):
        return any(is_tainted(k) or is_tainted(v) for k, v in val.items())

    if isinstance(val, (list, tuple, set)):
        return any(is_tainted(item) for item in val)

    return base_is_tainted(val)


def get_taint_info(val: Any) -> Optional[TaintMetadata]:
    """Extract taint metadata from a tainted object or its nested children."""
    if isinstance(val, TaintedData) or hasattr(val, "_taint_metadata"):
        return getattr(val, "_taint_metadata", None) or getattr(val, "taint_metadata", None)

    if isinstance(val, BaseTaintedData):
        return TaintMetadata(origin="untrusted_input", level=TaintLevel.HIGH)

    if isinstance(val, dict):
        for k, v in val.items():
            info = get_taint_info(k) or get_taint_info(v)
            if info:
                return info

    if isinstance(val, (list, tuple, set)):
        for item in val:
            info = get_taint_info(item)
            if info:
                return info

    return None


def sanitize(val: Any) -> Any:
    """
    Recursively strip all taint marks from an object, returning standard primitives.
    """
    if val is None:
        return None

    if isinstance(val, BaseTaintedString) or isinstance(val, TaintedString):
        return str(val)

    if isinstance(val, (BaseTaintedData, TaintedData)):
        return sanitize(getattr(val, "value", str(val)))

    if isinstance(val, str):
        return str(val)

    if isinstance(val, dict):
        return {sanitize(k): sanitize(v) for k, v in val.items()}

    if isinstance(val, list):
        return [sanitize(item) for item in val]

    if isinstance(val, tuple):
        return tuple(sanitize(item) for item in val)

    if isinstance(val, set):
        return {sanitize(item) for item in val}

    if hasattr(val, "_taint_metadata"):
        try:
            delattr(val, "_taint_metadata")
        except Exception:
            pass

    return base_sanitize(val)


@dataclass
class TaintEvaluationResult:
    """Result of evaluating arguments for taint policy compliance."""

    is_allowed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    tainted_args: List[str] = field(default_factory=list)
    sanitized_arguments: Dict[str, Any] = field(default_factory=dict)
    decision: TaintPolicyAction = TaintPolicyAction.BLOCK


@dataclass
class SandboxExecutionResult:
    """Result of executing a tool inside the taint sandbox."""

    success: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    blocked_by_policy: bool = False
    evaluation: Optional[TaintEvaluationResult] = None
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: f"taint_audit_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "blocked_by_policy": self.blocked_by_policy,
            "execution_time_ms": self.execution_time_ms,
            "audit_id": self.audit_id,
        }


class MCPKernelTaintSandboxV3:
    """
    MCPKernel Taint Tracking Sandbox V3.

    Enforces runtime taint tracking policy across tool arguments.
    Sensitive arguments (file paths, shell commands, SQL queries, system scripts)
    cannot receive tainted inputs unless explicitly sanitized or bypassed by policy.
    """

    DEFAULT_SENSITIVE_ARG_PATTERNS = [
        r"^path$",
        r".*_path$",
        r"^filepath$",
        r"^file_name$",
        r"^filename$",
        r"^directory$",
        r"^dir$",
        r"^cmd$",
        r"^command$",
        r".*_command$",
        r"^exec$",
        r"^script$",
        r"^payload$",
        r"^query$",
        r"^sql$",
        r"^code$",
        r"^shell$",
        r"^url$",
        r"^destination$",
        r"^target$",
    ]

    DEFAULT_TOOL_SENSITIVE_ARGS = {
        "read_file": {"path", "filepath", "filename"},
        "write_file": {"path", "filepath", "filename"},
        "delete_file": {"path", "filepath"},
        "execute_code": {"code", "command", "script"},
        "system_execute_code": {"code", "command", "script"},
        "run_shell_command": {"command", "cmd"},
        "bash": {"command", "cmd"},
        "sql_query": {"query", "sql"},
        "fetch_url": {"url", "target"},
    }

    def __init__(
        self,
        default_action: TaintPolicyAction = TaintPolicyAction.BLOCK,
        sensitive_arg_patterns: Optional[List[str]] = None,
        tool_sensitive_args: Optional[Dict[str, Set[str]]] = None,
        allow_low_taint: bool = False,
    ):
        self.default_action = default_action
        self.sensitive_arg_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (sensitive_arg_patterns or self.DEFAULT_SENSITIVE_ARG_PATTERNS)
        ]
        self.tool_sensitive_args = tool_sensitive_args or {
            k: set(v) for k, v in self.DEFAULT_TOOL_SENSITIVE_ARGS.items()
        }
        self.allow_low_taint = allow_low_taint
        self._audit_trail: List[SandboxExecutionResult] = []

    def register_tool_sensitive_args(
        self,
        tool_name: str,
        sensitive_args: Set[str],
    ) -> None:
        """Register or extend sensitive arguments for a specific tool."""
        if tool_name not in self.tool_sensitive_args:
            self.tool_sensitive_args[tool_name] = set()
        self.tool_sensitive_args[tool_name].update(sensitive_args)

    def is_sensitive_argument(self, tool_name: str, arg_name: str) -> bool:
        """Determine whether an argument is considered sensitive."""
        # Check explicit tool mapping
        if tool_name in self.tool_sensitive_args:
            if arg_name in self.tool_sensitive_args[tool_name]:
                return True

        # Check regex patterns
        for pattern in self.sensitive_arg_patterns:
            if pattern.match(arg_name):
                return True

        return False

    def evaluate_taint(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> TaintEvaluationResult:
        """
        Inspect arguments for tainted values in sensitive positions.
        """
        violations: List[Dict[str, Any]] = []
        tainted_arg_names: List[str] = []

        for arg_name, arg_val in arguments.items():
            if is_tainted(arg_val):
                tainted_arg_names.append(arg_name)
                info = get_taint_info(arg_val)

                # Check if it's sensitive
                if self.is_sensitive_argument(tool_name, arg_name):
                    level = info.level if info else TaintLevel.HIGH
                    if self.allow_low_taint and level == TaintLevel.LOW:
                        continue

                    violations.append({
                        "tool_name": tool_name,
                        "argument_name": arg_name,
                        "taint_origin": info.origin if info else "unknown",
                        "taint_level": level.value if isinstance(level, TaintLevel) else str(level),
                        "reason": f"Tainted value from '{info.origin if info else 'unknown'}' passed to sensitive argument '{arg_name}'",
                    })

        is_allowed = (
            len(violations) == 0
            or self.default_action in (TaintPolicyAction.AUDIT_ONLY, TaintPolicyAction.SANITIZE)
        )

        sanitized_args = {}
        if self.default_action == TaintPolicyAction.SANITIZE:
            sanitized_args = sanitize(arguments)
        else:
            sanitized_args = arguments

        return TaintEvaluationResult(
            is_allowed=is_allowed,
            violations=violations,
            tainted_args=tainted_arg_names,
            sanitized_arguments=sanitized_args,
            decision=self.default_action if violations else TaintPolicyAction.BLOCK,
        )

    def execute(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> SandboxExecutionResult:
        """
        Execute tool within the taint tracking sandbox synchronously.
        """
        start_t = time.perf_counter()
        evaluation = self.evaluate_taint(tool_name, arguments)

        if not evaluation.is_allowed:
            first_viol = evaluation.violations[0]
            err_msg = (
                f"Blocked execution of tool '{tool_name}': {first_viol['reason']}"
            )
            logger.warning(err_msg)
            res = SandboxExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=err_msg,
                blocked_by_policy=True,
                evaluation=evaluation,
                execution_time_ms=(time.perf_counter() - start_t) * 1000.0,
            )
            self._audit_trail.append(res)
            return res

        args_to_use = (
            evaluation.sanitized_arguments
            if self.default_action == TaintPolicyAction.SANITIZE
            else arguments
        )

        try:
            raw_result = tool_func(**args_to_use)
            elapsed = (time.perf_counter() - start_t) * 1000.0

            # If inputs were tainted, propagate taint tag to result if string
            if evaluation.tainted_args and isinstance(raw_result, str):
                final_result = mark_tainted(
                    raw_result,
                    origin=f"derived_from_{tool_name}",
                    level=TaintLevel.MEDIUM,
                )
            else:
                final_result = raw_result

            res = SandboxExecutionResult(
                success=True,
                tool_name=tool_name,
                result=final_result,
                error=None,
                blocked_by_policy=False,
                evaluation=evaluation,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = SandboxExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=str(e),
                blocked_by_policy=False,
                evaluation=evaluation,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    async def execute_async(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> SandboxExecutionResult:
        """
        Execute tool within the taint tracking sandbox asynchronously.
        """
        start_t = time.perf_counter()
        evaluation = self.evaluate_taint(tool_name, arguments)

        if not evaluation.is_allowed:
            first_viol = evaluation.violations[0]
            err_msg = (
                f"Blocked execution of tool '{tool_name}': {first_viol['reason']}"
            )
            logger.warning(err_msg)
            res = SandboxExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=err_msg,
                blocked_by_policy=True,
                evaluation=evaluation,
                execution_time_ms=(time.perf_counter() - start_t) * 1000.0,
            )
            self._audit_trail.append(res)
            return res

        args_to_use = (
            evaluation.sanitized_arguments
            if self.default_action == TaintPolicyAction.SANITIZE
            else arguments
        )

        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_result = await tool_func(**args_to_use)
            else:
                raw_result = tool_func(**args_to_use)
            elapsed = (time.perf_counter() - start_t) * 1000.0

            if evaluation.tainted_args and isinstance(raw_result, str):
                final_result = mark_tainted(
                    raw_result,
                    origin=f"derived_from_{tool_name}",
                    level=TaintLevel.MEDIUM,
                )
            else:
                final_result = raw_result

            res = SandboxExecutionResult(
                success=True,
                tool_name=tool_name,
                result=final_result,
                error=None,
                blocked_by_policy=False,
                evaluation=evaluation,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = SandboxExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=str(e),
                blocked_by_policy=False,
                evaluation=evaluation,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    def get_audit_trail(self) -> List[SandboxExecutionResult]:
        """Retrieve execution audit trail."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear execution audit trail."""
        self._audit_trail.clear()
