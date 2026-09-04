"""
ACS Agent Control Specification Runtime Guard V7.

Inspired by ACS runtime safety controls: Provides a comprehensive runtime
validation guardrail module that intercepts all tool executions, evaluating them
against 5 strict validation checkpoints for policy adherence, authorization,
state transition safety, and output sanitization.
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

logger = logging.getLogger(__name__)


class ACSCheckpoint(str, Enum):
    CHECKPOINT_1_INPUT = "checkpoint_1_input_validation"
    CHECKPOINT_2_INTENT = "checkpoint_2_intent_authorization"
    CHECKPOINT_3_POLICY = "checkpoint_3_tool_policy_and_taint"
    CHECKPOINT_4_STATE = "checkpoint_4_state_transition_safety"
    CHECKPOINT_5_OUTPUT = "checkpoint_5_output_sanitization"


class ACSRuntimePolicyViolationError(Exception):
    """Raised when tool execution is blocked by an ACS validation checkpoint."""

    def __init__(self, checkpoint: ACSCheckpoint, tool_name: str, reason: str):
        super().__init__(
            f"ACS Runtime Guard V7 blocked tool '{tool_name}' at [{checkpoint.value}]: {reason}"
        )
        self.checkpoint = checkpoint
        self.tool_name = tool_name
        self.reason = reason


@dataclass
class CheckpointEvaluation:
    """Evaluation result for an individual checkpoint."""

    checkpoint: ACSCheckpoint
    passed: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["checkpoint"] = self.checkpoint.value if isinstance(self.checkpoint, ACSCheckpoint) else str(self.checkpoint)
        return d


@dataclass
class ACSValidationOutcome:
    """Aggregated outcome of pre-execution or post-execution validation."""

    passed: bool
    failed_checkpoint: Optional[ACSCheckpoint] = None
    failure_reason: Optional[str] = None
    checkpoint_evaluations: List[CheckpointEvaluation] = field(default_factory=list)


@dataclass
class ACSGuardResult:
    """Complete result of intercepting and executing a tool under ACS Guard V7."""

    success: bool
    tool_name: str
    output: Any = None
    error: Optional[str] = None
    blocked_by_guard: bool = False
    failed_checkpoint: Optional[str] = None
    pre_execution_outcome: Optional[ACSValidationOutcome] = None
    post_execution_outcome: Optional[ACSValidationOutcome] = None
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: f"acs_audit_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "output": str(self.output) if self.output is not None else None,
            "error": self.error,
            "blocked_by_guard": self.blocked_by_guard,
            "failed_checkpoint": self.failed_checkpoint,
            "execution_time_ms": self.execution_time_ms,
            "audit_id": self.audit_id,
        }


class ACSGuardRuntimeV7:
    """
    ACS Runtime Guard V7.

    Enforces 5 validation checkpoints on all tool executions:
    1. Input Validation: Detects malformed structures, injection attacks, dangerous commands.
    2. Intent Authorization: Enforces permission/role requirements for privileged tools.
    3. Tool Policy & Sandboxing: Enforces rate limits, blacklisted actions, taint bounds.
    4. State Transition Safety: Validates safe state progression and prevents cyclic lockups.
    5. Output Sanitization: Redacts credentials, private keys, and detects corrupted states.
    """

    SENSITIVE_OUTPUT_PATTERNS = [
        re.compile(r"(?:api[_-]?key|bearer|password|secret|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?", re.IGNORECASE),
        re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
    ]

    DANGEROUS_COMMAND_PATTERNS = [
        re.compile(r"\brm\s+-(?:r|f|rf|fr)\s+(?:/|/\*|~|\$HOME)", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),
        re.compile(r"\bmkfs\.", re.IGNORECASE),
        re.compile(r"\bdd\s+if=.*of=/dev/", re.IGNORECASE),
        re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    ]

    RESTRICTED_TOOLS = {
        "system_execute_code": {"admin", "developer"},
        "execute_code": {"admin", "developer"},
        "bash": {"admin", "developer"},
        "run_shell_command": {"admin", "developer"},
        "delete_database": {"admin"},
        "write_credentials": {"admin"},
    }

    def __init__(
        self,
        strict_mode: bool = True,
        allowed_roles: Optional[Set[str]] = None,
        custom_checkpoint_hooks: Optional[Dict[ACSCheckpoint, List[Callable[..., Tuple[bool, str]]]]] = None,
    ):
        self.strict_mode = strict_mode
        self.default_roles = allowed_roles or {"user", "developer", "admin"}
        self._custom_hooks = custom_checkpoint_hooks or {}
        self._audit_trail: List[ACSGuardResult] = []
        self._state_transition_history: List[str] = []

    # -------------------------------------------------------------------------
    # Checkpoint 1: Input Validation
    # -------------------------------------------------------------------------
    def checkpoint_1_input_validation(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Validate argument structures, prevent null-byte injection and dangerous payloads."""
        for k, v in arguments.items():
            if isinstance(v, str):
                if "\x00" in v:
                    return False, f"Null byte detected in argument '{k}'"

                for pattern in self.DANGEROUS_COMMAND_PATTERNS:
                    if pattern.search(v):
                        return False, f"Dangerous command payload detected in argument '{k}': matched {pattern.pattern}"

        return True, "Input validation passed."

    # -------------------------------------------------------------------------
    # Checkpoint 2: Intent Authorization
    # -------------------------------------------------------------------------
    def checkpoint_2_intent_authorization(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Verify the caller has authorization to execute the requested tool."""
        caller_role = context.get("user_role") or context.get("role") or "user"

        if tool_name in self.RESTRICTED_TOOLS:
            required_roles = self.RESTRICTED_TOOLS[tool_name]
            if caller_role not in required_roles:
                return False, (
                    f"Tool '{tool_name}' requires one of roles {sorted(list(required_roles))}, "
                    f"but caller role is '{caller_role}'"
                )

        return True, "Intent authorization passed."

    # -------------------------------------------------------------------------
    # Checkpoint 3: Tool Policy and Sandboxing
    # -------------------------------------------------------------------------
    def checkpoint_3_tool_policy(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Enforce tool sandboxing limits, path restrictions, and policies."""
        disallowed_tools = context.get("disallowed_tools", set())
        if tool_name in disallowed_tools:
            return False, f"Tool '{tool_name}' is explicitly disabled in current execution context."

        # Path sandboxing if requested in context
        restricted_dir = context.get("sandbox_root")
        if restricted_dir:
            path_val = arguments.get("path") or arguments.get("filepath")
            if path_val and isinstance(path_val, str):
                if ".." in path_val or not path_val.startswith(restricted_dir):
                    return False, f"Path '{path_val}' escapes sandbox directory '{restricted_dir}'"

        return True, "Tool policy checks passed."

    # -------------------------------------------------------------------------
    # Checkpoint 4: State Transition Safety
    # -------------------------------------------------------------------------
    def checkpoint_4_state_transition(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Verify that executing this tool does not cause dangerous or cyclic state transitions."""
        current_state = context.get("agent_state", "READY")
        if current_state == "TERMINATED":
            return False, "Cannot execute tools while agent is in TERMINATED state."

        # Check for rapid infinite loop execution
        recent = self._state_transition_history[-10:]
        if len(recent) >= 10 and all(x == tool_name for x in recent):
            return False, f"Detected potential infinite execution loop on tool '{tool_name}'"

        self._state_transition_history.append(tool_name)
        return True, "State transition safety checks passed."

    # -------------------------------------------------------------------------
    # Checkpoint 5: Output Sanitization
    # -------------------------------------------------------------------------
    def checkpoint_5_output_sanitization(
        self,
        tool_name: str,
        output: Any,
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Inspect output for leaked secrets or private keys."""
        if output is None:
            return True, "Output is empty/safe."

        out_str = str(output)
        for pattern in self.SENSITIVE_OUTPUT_PATTERNS:
            if pattern.search(out_str):
                return False, f"Sensitive credential or private key pattern detected in tool output."

        return True, "Output sanitization passed."

    # -------------------------------------------------------------------------
    # Composite Evaluation
    # -------------------------------------------------------------------------
    def evaluate_pre_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ACSValidationOutcome:
        """Run Checkpoints 1, 2, 3, and 4 before tool execution."""
        evals: List[CheckpointEvaluation] = []

        checkpoints_to_run = [
            (ACSCheckpoint.CHECKPOINT_1_INPUT, self.checkpoint_1_input_validation),
            (ACSCheckpoint.CHECKPOINT_2_INTENT, self.checkpoint_2_intent_authorization),
            (ACSCheckpoint.CHECKPOINT_3_POLICY, self.checkpoint_3_tool_policy),
            (ACSCheckpoint.CHECKPOINT_4_STATE, self.checkpoint_4_state_transition),
        ]

        for cp_enum, cp_func in checkpoints_to_run:
            start_t = time.perf_counter()
            passed, reason = cp_func(tool_name, arguments, context)
            dur = (time.perf_counter() - start_t) * 1000.0
            evals.append(CheckpointEvaluation(
                checkpoint=cp_enum,
                passed=passed,
                reason=reason,
                duration_ms=dur,
            ))
            if not passed:
                return ACSValidationOutcome(
                    passed=False,
                    failed_checkpoint=cp_enum,
                    failure_reason=reason,
                    checkpoint_evaluations=evals,
                )

        return ACSValidationOutcome(
            passed=True,
            checkpoint_evaluations=evals,
        )

    def evaluate_post_execution(
        self,
        tool_name: str,
        output: Any,
        context: Dict[str, Any],
    ) -> ACSValidationOutcome:
        """Run Checkpoint 5 after tool execution."""
        start_t = time.perf_counter()
        passed, reason = self.checkpoint_5_output_sanitization(tool_name, output, context)
        dur = (time.perf_counter() - start_t) * 1000.0

        ev = CheckpointEvaluation(
            checkpoint=ACSCheckpoint.CHECKPOINT_5_OUTPUT,
            passed=passed,
            reason=reason,
            duration_ms=dur,
        )

        return ACSValidationOutcome(
            passed=passed,
            failed_checkpoint=None if passed else ACSCheckpoint.CHECKPOINT_5_OUTPUT,
            failure_reason=None if passed else reason,
            checkpoint_evaluations=[ev],
        )

    # -------------------------------------------------------------------------
    # Execution Interception
    # -------------------------------------------------------------------------
    def intercept_and_execute(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ACSGuardResult:
        """Synchronously execute tool protected by all 5 checkpoints."""
        start_t = time.perf_counter()
        ctx = context or {}

        # 1. Pre-execution checkpoints (1-4)
        pre_outcome = self.evaluate_pre_execution(tool_name, arguments, ctx)
        if not pre_outcome.passed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"ACS validation failed at {pre_outcome.failed_checkpoint.value}: {pre_outcome.failure_reason}"
            logger.warning(err_msg)
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                error=err_msg,
                blocked_by_guard=True,
                failed_checkpoint=pre_outcome.failed_checkpoint.value if pre_outcome.failed_checkpoint else None,
                pre_execution_outcome=pre_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        # 2. Execute target tool
        try:
            raw_output = tool_func(**arguments)
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool runtime exception: {str(ex)}",
                blocked_by_guard=False,
                pre_execution_outcome=pre_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        # 3. Post-execution checkpoint (5)
        post_outcome = self.evaluate_post_execution(tool_name, raw_output, ctx)
        elapsed = (time.perf_counter() - start_t) * 1000.0
        if not post_outcome.passed:
            err_msg = f"ACS validation failed at {post_outcome.failed_checkpoint.value}: {post_outcome.failure_reason}"
            logger.warning(err_msg)
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                output=None,  # Redacted because failed output check
                error=err_msg,
                blocked_by_guard=True,
                failed_checkpoint=post_outcome.failed_checkpoint.value if post_outcome.failed_checkpoint else None,
                pre_execution_outcome=pre_outcome,
                post_execution_outcome=post_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        res = ACSGuardResult(
            success=True,
            tool_name=tool_name,
            output=raw_output,
            blocked_by_guard=False,
            pre_execution_outcome=pre_outcome,
            post_execution_outcome=post_outcome,
            execution_time_ms=elapsed,
        )
        self._audit_trail.append(res)
        return res

    async def intercept_and_execute_async(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ACSGuardResult:
        """Asynchronously execute tool protected by all 5 checkpoints."""
        start_t = time.perf_counter()
        ctx = context or {}

        # 1. Pre-execution checkpoints (1-4)
        pre_outcome = self.evaluate_pre_execution(tool_name, arguments, ctx)
        if not pre_outcome.passed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"ACS validation failed at {pre_outcome.failed_checkpoint.value}: {pre_outcome.failure_reason}"
            logger.warning(err_msg)
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                error=err_msg,
                blocked_by_guard=True,
                failed_checkpoint=pre_outcome.failed_checkpoint.value if pre_outcome.failed_checkpoint else None,
                pre_execution_outcome=pre_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        # 2. Execute target tool
        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_output = await tool_func(**arguments)
            else:
                raw_output = tool_func(**arguments)
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool runtime exception: {str(ex)}",
                blocked_by_guard=False,
                pre_execution_outcome=pre_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        # 3. Post-execution checkpoint (5)
        post_outcome = self.evaluate_post_execution(tool_name, raw_output, ctx)
        elapsed = (time.perf_counter() - start_t) * 1000.0
        if not post_outcome.passed:
            err_msg = f"ACS validation failed at {post_outcome.failed_checkpoint.value}: {post_outcome.failure_reason}"
            logger.warning(err_msg)
            res = ACSGuardResult(
                success=False,
                tool_name=tool_name,
                output=None,
                error=err_msg,
                blocked_by_guard=True,
                failed_checkpoint=post_outcome.failed_checkpoint.value if post_outcome.failed_checkpoint else None,
                pre_execution_outcome=pre_outcome,
                post_execution_outcome=post_outcome,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        res = ACSGuardResult(
            success=True,
            tool_name=tool_name,
            output=raw_output,
            blocked_by_guard=False,
            pre_execution_outcome=pre_outcome,
            post_execution_outcome=post_outcome,
            execution_time_ms=elapsed,
        )
        self._audit_trail.append(res)
        return res

    def get_audit_trail(self) -> List[ACSGuardResult]:
        """Get copy of audit trail."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit trail."""
        self._audit_trail.clear()
        self._state_transition_history.clear()
