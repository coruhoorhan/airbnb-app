"""
ACS Control Fallback Strategy v5.

Inspired by ACS runtime safety controls: Implements a graceful fallback strategy
when a tool's output validation is denied by state checks, falling back to neutral
responses, redaction, or registered domain-specific handlers.
"""

import asyncio
import concurrent.futures
import inspect
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class FallbackMode(str, Enum):
    NEUTRAL_MESSAGE = "neutral_message"
    REDACT_SENSITIVE = "redact_sensitive"
    CUSTOM_HANDLER = "custom_handler"
    CACHED_FALLBACK = "cached_fallback"
    SAFE_DEGRADATION = "safe_degradation"


@dataclass
class ACSExecutionOutcome:
    """Represents the outcome of a tool execution evaluated under ACS output state controls."""

    success: bool
    fallback_taken: bool
    output: Any
    validation_passed: bool
    denial_reason: Optional[str] = None
    fallback_mode_applied: Optional[str] = None
    tool_name: str = ""
    execution_time_ms: float = 0.0
    audit_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DefaultStateRules:
    """Built-in output state validation checks."""

    SENSITIVE_PATTERNS = [
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "Social Security Number detected"),
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "Credit Card Number detected"),
        (re.compile(r"(?:api[_-]?key|secret[_-]?token|bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE), "Secret API Token detected"),
        (re.compile(r"-----BEGIN (?:RSA|OPENSSH|PRIVATE) KEY-----", re.IGNORECASE), "Private Key Header detected"),
    ]

    FORBIDDEN_STATE_WORDS = {
        "DROP_TABLE_CONFIRMED",
        "GRANT_ALL_PRIVILEGES_SUCCESS",
        "OVERRIDE_SECURITY_ENABLED",
        "MALICIOUS_PAYLOAD_EXECUTED",
    }

    @classmethod
    def check_pii_and_secrets(cls, output: Any, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        text = str(output)
        for pattern, desc in cls.SENSITIVE_PATTERNS:
            if pattern.search(text):
                return False, f"State check failed: {desc} in output."
        return True, "Passed PII and secret checks."

    @classmethod
    def check_forbidden_state_indicators(cls, output: Any, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        text = str(output).upper()
        for word in cls.FORBIDDEN_STATE_WORDS:
            if word in text:
                return False, f"State check denied: Forbidden state mutation indicator '{word}' present in output."
        return True, "Passed state indicator checks."


class ACSControlFallbackStrategyV5:
    """
    ACS Runtime Safety Controller with graceful fallback strategies.
    Intercepts tool output post-execution, verifies state invariants, and applies
    neutral/redaction fallbacks on denied validation.
    """

    DEFAULT_NEUTRAL_RESPONSE = (
        "I am unable to return the specific output for this operation as it "
        "did not satisfy runtime state safety criteria. Please refine your query or contact support."
    )

    def __init__(
        self,
        default_fallback_mode: FallbackMode = FallbackMode.NEUTRAL_MESSAGE,
        custom_neutral_message: Optional[str] = None,
        audit_trail: Optional[Any] = None,
    ) -> None:
        self.default_fallback_mode = default_fallback_mode
        self.neutral_message = custom_neutral_message or self.DEFAULT_NEUTRAL_RESPONSE
        self.audit_trail = audit_trail
        self._custom_fallback_handlers: Dict[str, Callable[[Any, str, Dict[str, Any]], Any]] = {}
        self._state_rules: List[Tuple[str, Callable[[Any, Optional[Dict[str, Any]]], Tuple[bool, str]]]] = [
            ("PIIAndSecretsCheck", DefaultStateRules.check_pii_and_secrets),
            ("ForbiddenStateIndicatorsCheck", DefaultStateRules.check_forbidden_state_indicators),
        ]
        self._audit_history: List[Dict[str, Any]] = []

    def register_state_rule(
        self,
        rule_name: str,
        rule_fn: Callable[[Any, Optional[Dict[str, Any]]], Tuple[bool, str]],
    ) -> None:
        """Registers a custom output state validation rule."""
        self._state_rules.append((rule_name, rule_fn))

    def register_tool_fallback(
        self,
        tool_name: str,
        fallback_fn: Callable[[Any, str, Dict[str, Any]], Any],
    ) -> None:
        """Registers a specialized fallback handler for a particular tool."""
        self._custom_fallback_handlers[tool_name] = fallback_fn

    def validate_output_state(
        self,
        output: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Evaluates all registered state validation rules against tool output."""
        context = context or {}
        for rule_name, rule_fn in self._state_rules:
            try:
                passed, reason = rule_fn(output, context)
                if not passed:
                    logger.warning(f"Output validation denied by rule '{rule_name}': {reason}")
                    return False, f"[{rule_name}] {reason}"
            except Exception as e:
                logger.error(f"Rule '{rule_name}' raised error during validation: {e}")
                return False, f"Validation rule error in '{rule_name}': {e}"

        return True, "All ACS state validation checks passed."

    def apply_fallback(
        self,
        raw_output: Any,
        denial_reason: str,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
        mode: FallbackMode,
    ) -> Tuple[Any, str]:
        """Applies chosen fallback strategy on denied validation."""
        if tool_name in self._custom_fallback_handlers and mode == FallbackMode.CUSTOM_HANDLER:
            try:
                handler = self._custom_fallback_handlers[tool_name]
                fallback_res = handler(raw_output, denial_reason, args)
                return fallback_res, FallbackMode.CUSTOM_HANDLER.value
            except Exception as e:
                logger.error(f"Custom fallback handler for '{tool_name}' failed: {e}. Falling back to neutral response.")

        if mode == FallbackMode.REDACT_SENSITIVE:
            text = str(raw_output)
            for pattern, _ in DefaultStateRules.SENSITIVE_PATTERNS:
                text = pattern.sub("[REDACTED_BY_ACS]", text)
            return text, FallbackMode.REDACT_SENSITIVE.value

        if mode == FallbackMode.SAFE_DEGRADATION:
            return {
                "status": "partial_success",
                "warning": f"Output validation restricted: {denial_reason}",
                "safe_content": "Operation finished with safety guardrails applied.",
            }, FallbackMode.SAFE_DEGRADATION.value

        # Default: NEUTRAL_MESSAGE
        return self.neutral_message, FallbackMode.NEUTRAL_MESSAGE.value

    def _log_event(self, outcome: ACSExecutionOutcome) -> None:
        record = outcome.to_dict()
        self._audit_history.append(record)

        if self.audit_trail:
            try:
                if hasattr(self.audit_trail, "log"):
                    self.audit_trail.log(
                        tool_name=outcome.tool_name,
                        args=outcome.audit_metadata.get("args", {}),
                        result=outcome.output,
                        status="fallback" if outcome.fallback_taken else "success",
                        why=outcome.denial_reason or "State checks passed",
                    )
            except Exception as e:
                logger.warning(f"Failed to record event to external audit trail: {e}")

    async def execute_with_fallback(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        fallback_mode: Optional[FallbackMode] = None,
    ) -> ACSExecutionOutcome:
        """
        Executes the tool function asynchronously and applies ACS state check validation on output.
        If validation is denied, gracefully falls back according to the configured strategy.
        """
        args = args or {}
        context = context or {}
        mode = fallback_mode or self.default_fallback_mode
        start_time = time.perf_counter()

        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_output = await tool_func(**args)
            else:
                raw_output = tool_func(**args)
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Tool execution error in '{tool_name}': {e}")
            fallback_val, applied_mode = self.apply_fallback(
                raw_output=None,
                denial_reason=f"Tool raised execution exception: {e}",
                tool_name=tool_name,
                args=args,
                context=context,
                mode=mode,
            )
            outcome = ACSExecutionOutcome(
                success=True,
                fallback_taken=True,
                output=fallback_val,
                validation_passed=False,
                denial_reason=f"Execution error: {e}",
                fallback_mode_applied=applied_mode,
                tool_name=tool_name,
                execution_time_ms=duration,
                audit_metadata={"args": args, "context": context},
            )
            self._log_event(outcome)
            return outcome

        # State check output validation
        is_valid, reason = self.validate_output_state(raw_output, context)
        duration = (time.perf_counter() - start_time) * 1000.0

        if not is_valid:
            fallback_val, applied_mode = self.apply_fallback(
                raw_output=raw_output,
                denial_reason=reason,
                tool_name=tool_name,
                args=args,
                context=context,
                mode=mode,
            )
            outcome = ACSExecutionOutcome(
                success=True,
                fallback_taken=True,
                output=fallback_val,
                validation_passed=False,
                denial_reason=reason,
                fallback_mode_applied=applied_mode,
                tool_name=tool_name,
                execution_time_ms=duration,
                audit_metadata={"args": args, "context": context, "raw_denied_output": str(raw_output)[:300]},
            )
            self._log_event(outcome)
            return outcome

        outcome = ACSExecutionOutcome(
            success=True,
            fallback_taken=False,
            output=raw_output,
            validation_passed=True,
            denial_reason=None,
            fallback_mode_applied=None,
            tool_name=tool_name,
            execution_time_ms=duration,
            audit_metadata={"args": args, "context": context},
        )
        self._log_event(outcome)
        return outcome

    def execute_with_fallback_sync(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        fallback_mode: Optional[FallbackMode] = None,
    ) -> ACSExecutionOutcome:
        """Synchronous wrapper for ACS execution with graceful fallback."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.execute_with_fallback(
                            tool_func=tool_func,
                            tool_name=tool_name,
                            args=args,
                            context=context,
                            fallback_mode=fallback_mode,
                        )
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.execute_with_fallback(
                    tool_func=tool_func,
                    tool_name=tool_name,
                    args=args,
                    context=context,
                    fallback_mode=fallback_mode,
                )
            )

    def get_audit_history(self) -> List[Dict[str, Any]]:
        """Returns recorded execution outcomes."""
        return list(self._audit_history)
