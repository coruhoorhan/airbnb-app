"""
MCP Tool Runtime Execution Policy Sandbox V4.

Provides a tight runtime policy evaluator sandbox to intercept action tools,
evaluating parameters, detecting dangerous mutations/side-effects, enforcing
sandboxing invariants, and logging audit trails.
"""

import asyncio
import concurrent.futures
import inspect
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class PolicyActionType(str, Enum):
    READ_ONLY = "read_only"
    MUTATION = "mutation"
    SYSTEM_COMMAND = "system_command"
    NETWORK_REQUEST = "network_request"
    SENSITIVE_ACCESS = "sensitive_access"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_VERIFICATION = "require_verification"
    SIMULATE_ONLY = "simulate_only"


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    decision: PolicyDecision
    reason: str
    rule_name: str
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (critical)
    side_effects_detected: List[str] = field(default_factory=list)


@dataclass
class SandboxExecutionResult:
    success: bool
    result: Any
    error: Optional[str]
    evaluation: PolicyEvaluationResult
    tool_name: str
    simulated: bool = False
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class MCPPolicyViolationError(Exception):
    """Raised when an MCP tool execution violates runtime safety policy."""
    pass


class MCPUnverifiedActionError(Exception):
    """Raised when an action tool requires verification token or confirmation before execution."""
    pass


class MCPSandboxExecutionError(Exception):
    """Raised when a tool raises an unhandled error inside the sandbox."""
    pass


class BasePolicyRule(ABC):
    """Abstract base class for sandbox policy rules."""

    @abstractmethod
    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """Evaluates whether the tool call conforms to policy."""
        pass


class ActionToolInterceptorRule(BasePolicyRule):
    """
    Identifies state-mutating action tools and verifies whether they carry
    unverified side-effects or lack requisite confirmation.
    """

    DEFAULT_ACTION_VERBS = {
        "write", "create", "delete", "remove", "drop", "destroy", "update",
        "patch", "post", "put", "send", "execute", "exec", "run", "deploy",
        "mutate", "terminate", "kill", "restart", "reboot", "truncate"
    }

    def __init__(
        self,
        action_verbs: Optional[Set[str]] = None,
        blocked_action_tools: Optional[Set[str]] = None,
        require_verification_for: Optional[Set[str]] = None,
    ) -> None:
        self.action_verbs = action_verbs or self.DEFAULT_ACTION_VERBS
        self.blocked_action_tools = blocked_action_tools or set()
        self.require_verification_for = require_verification_for or set()

    def _is_action_tool(self, tool_name: str) -> bool:
        t_lower = tool_name.lower()
        if any(verb in t_lower for verb in self.action_verbs):
            return True
        return False

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        t_lower = tool_name.lower()
        context = context or {}

        if t_lower in self.blocked_action_tools:
            return PolicyEvaluationResult(
                allowed=False,
                decision=PolicyDecision.BLOCK,
                reason=f"Action tool '{tool_name}' is explicitly blacklisted.",
                rule_name="ActionToolInterceptorRule",
                risk_score=1.0,
                side_effects_detected=["blacklisted_tool_invocation"],
            )

        is_action = self._is_action_tool(tool_name)
        if not is_action:
            return PolicyEvaluationResult(
                allowed=True,
                decision=PolicyDecision.ALLOW,
                reason=f"Tool '{tool_name}' classified as read-only / inquiry.",
                rule_name="ActionToolInterceptorRule",
                risk_score=0.1,
            )

        side_effects = [f"state_mutation_by_{tool_name}"]

        # Check if action requires explicit verification
        if t_lower in self.require_verification_for or any(v in t_lower for v in ["destroy", "drop", "truncate", "kill"]):
            verification_token = context.get("verification_token")
            is_verified = context.get("is_verified", False)
            if not verification_token and not is_verified:
                return PolicyEvaluationResult(
                    allowed=False,
                    decision=PolicyDecision.REQUIRE_VERIFICATION,
                    reason=f"High-impact action tool '{tool_name}' requires explicit verification.",
                    rule_name="ActionToolInterceptorRule",
                    risk_score=0.85,
                    side_effects_detected=side_effects,
                )

        return PolicyEvaluationResult(
            allowed=True,
            decision=PolicyDecision.ALLOW,
            reason=f"Action tool '{tool_name}' permitted under standard policy.",
            rule_name="ActionToolInterceptorRule",
            risk_score=0.4,
            side_effects_detected=side_effects,
        )


class PathSandboxingRule(BasePolicyRule):
    """
    Prevents unauthorized file system traversals, tampering with sensitive
    system paths, credentials, and environment configuration.
    """

    CRITICAL_PATH_PATTERNS = [
        r"^/etc(?:/.*)?$",
        r"^/root/\.ssh(?:/.*)?$",
        r"^/sys(?:/.*)?$",
        r"^/proc(?:/.*)?$",
        r"^/dev(?:/.*)?$",
        r"(?:^|/)(?:[\w.-]*\.env(?:\.[\w-]+)*|\.env)$",
        r"(?:^|/)id_rsa(?:[\.\w-]*)$",
        r"(?:^|/)id_ed25519(?:[\.\w-]*)$",
    ]

    def __init__(
        self,
        allowed_root_prefixes: Optional[List[str]] = None,
        blocked_path_patterns: Optional[List[str]] = None,
    ) -> None:
        self.allowed_root_prefixes = allowed_root_prefixes or []
        self.blocked_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (blocked_path_patterns or self.CRITICAL_PATH_PATTERNS)
        ]

    def _extract_paths_from_args(self, args: Dict[str, Any]) -> List[str]:
        paths = []
        for k, v in args.items():
            if isinstance(v, str):
                if any(kw in k.lower() for kw in ["path", "file", "dir", "dest", "src", "target"]):
                    paths.append(v)
                elif "/" in v or "\\" in v or v.endswith(".env") or ".env" in v:
                    paths.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and ("/" in item or "\\" in item or ".env" in item):
                        paths.append(item)
        return paths

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        paths = self._extract_paths_from_args(args)
        if not paths:
            return PolicyEvaluationResult(
                allowed=True,
                decision=PolicyDecision.ALLOW,
                reason="No path parameters detected in tool call.",
                rule_name="PathSandboxingRule",
                risk_score=0.0,
            )

        for p in paths:
            normalized = os.path.normpath(p)
            for pattern in self.blocked_patterns:
                if pattern.search(normalized) or pattern.search(p):
                    return PolicyEvaluationResult(
                        allowed=False,
                        decision=PolicyDecision.BLOCK,
                        reason=f"Path '{p}' matches prohibited system pattern '{pattern.pattern}'.",
                        rule_name="PathSandboxingRule",
                        risk_score=0.95,
                        side_effects_detected=[f"unauthorized_path_access:{p}"],
                    )

            if self.allowed_root_prefixes:
                is_within_allowed = any(
                    normalized.startswith(os.path.normpath(prefix))
                    for prefix in self.allowed_root_prefixes
                )
                if not is_within_allowed:
                    return PolicyEvaluationResult(
                        allowed=False,
                        decision=PolicyDecision.BLOCK,
                        reason=f"Path '{p}' is outside allowed root boundaries.",
                        rule_name="PathSandboxingRule",
                        risk_score=0.8,
                        side_effects_detected=[f"path_boundary_violation:{p}"],
                    )

        return PolicyEvaluationResult(
            allowed=True,
            decision=PolicyDecision.ALLOW,
            reason="All path parameters conform to path sandboxing policy.",
            rule_name="PathSandboxingRule",
            risk_score=0.2,
        )


class CommandInjectionSanitizerRule(BasePolicyRule):
    """
    Scans command-line and shell parameters for destructive or malicious payloads.
    """

    DANGEROUS_PATTERNS = [
        (r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+/(?:\s|$|\*)", "Root directory destruction (rm -rf /)"),
        (r"\bmkfs\b", "Disk formatting command (mkfs)"),
        (r"\bdd\s+if=/dev/zero", "Disk zeroing command (dd if=/dev/zero)"),
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb pattern"),
        (r"\bcurl\b.*\|\s*(?:bash|sh)\b", "Piping remote script to shell"),
        (r"\bwget\b.*\|\s*(?:bash|sh)\b", "Piping remote script to shell"),
        (r"\bshutdown\b", "System shutdown command"),
        (r"\breboot\b", "System reboot command"),
        (r"\bchmod\s+-R\s+777\s+/(?:\s|$|\*)", "Indiscriminate root chmod 777"),
    ]

    def __init__(self, custom_dangerous_patterns: Optional[List[Tuple[str, str]]] = None) -> None:
        raw_patterns = custom_dangerous_patterns or self.DANGEROUS_PATTERNS
        self.patterns = [(re.compile(p, re.IGNORECASE), desc) for p, desc in raw_patterns]

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        commands = []
        for k, v in args.items():
            if isinstance(v, str):
                commands.append(v)

        for cmd in commands:
            for pattern, desc in self.patterns:
                if pattern.search(cmd):
                    return PolicyEvaluationResult(
                        allowed=False,
                        decision=PolicyDecision.BLOCK,
                        reason=f"Dangerous command pattern detected: {desc}",
                        rule_name="CommandInjectionSanitizerRule",
                        risk_score=1.0,
                        side_effects_detected=[f"dangerous_command:{desc}"],
                    )

        return PolicyEvaluationResult(
            allowed=True,
            decision=PolicyDecision.ALLOW,
            reason="Command parameters passed sanitization checks.",
            rule_name="CommandInjectionSanitizerRule",
            risk_score=0.1,
        )


class SSRFProtectionRule(BasePolicyRule):
    """
    Protects against Server-Side Request Forgery by blocking private, loopback,
    or AWS/cloud metadata IP ranges.
    """

    BLOCKED_HOST_PATTERNS = [
        r"^https?://(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/.*)?$",
        r"^https?://169\.254\.169\.254(?:/.*)?$",  # AWS/GCP metadata
        r"^https?://(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?(?:/.*)?$",
    ]

    def __init__(self, allowed_domains: Optional[List[str]] = None) -> None:
        self.allowed_domains = allowed_domains or []
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.BLOCKED_HOST_PATTERNS]

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        urls = []
        for k, v in args.items():
            if isinstance(v, str) and ("http://" in v or "https://" in v):
                urls.append(v)

        for u in urls:
            for pat in self.patterns:
                if pat.search(u):
                    return PolicyEvaluationResult(
                        allowed=False,
                        decision=PolicyDecision.BLOCK,
                        reason=f"SSRF violation: URL '{u}' targets private network or metadata service.",
                        rule_name="SSRFProtectionRule",
                        risk_score=0.95,
                        side_effects_detected=[f"ssrf_attempt:{u}"],
                    )

        return PolicyEvaluationResult(
            allowed=True,
            decision=PolicyDecision.ALLOW,
            reason="Network URLs verified safe.",
            rule_name="SSRFProtectionRule",
            risk_score=0.1,
        )


class DynamicCustomRule(BasePolicyRule):
    """Allows defining custom programmatic evaluator rules."""

    def __init__(
        self,
        name: str,
        eval_fn: Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], Tuple[bool, str]],
    ) -> None:
        self.name = name
        self.eval_fn = eval_fn

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        allowed, reason = self.eval_fn(tool_name, args, context)
        return PolicyEvaluationResult(
            allowed=allowed,
            decision=PolicyDecision.ALLOW if allowed else PolicyDecision.BLOCK,
            reason=reason,
            rule_name=self.name,
            risk_score=0.1 if allowed else 0.9,
        )


class MCPPolicySandboxV4:
    """
    Tight runtime policy evaluator sandbox to intercept action tools
    and prevent unverified side-effects.
    """

    def __init__(
        self,
        rules: Optional[List[BasePolicyRule]] = None,
        audit_trail: Optional[Any] = None,
        strict_mode: bool = True,
    ) -> None:
        self.strict_mode = strict_mode
        self.audit_trail = audit_trail
        self.rules: List[BasePolicyRule] = rules if rules is not None else [
            ActionToolInterceptorRule(),
            PathSandboxingRule(),
            CommandInjectionSanitizerRule(),
            SSRFProtectionRule(),
        ]
        self._audit_logs: List[Dict[str, Any]] = []

    def add_rule(self, rule: BasePolicyRule) -> None:
        """Adds a policy rule to the sandbox engine."""
        self.rules.append(rule)

    def evaluate_policy(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluates all registered rules against the tool call.
        Returns the strictest decision (BLOCK > REQUIRE_VERIFICATION > ALLOW).
        """
        aggregated_side_effects: List[str] = []
        max_risk = 0.0

        for rule in self.rules:
            try:
                res = rule.evaluate(tool_name, args, context)
            except Exception as e:
                logger.error(f"Rule {getattr(rule, 'rule_name', rule.__class__.__name__)} raised error: {e}")
                if self.strict_mode:
                    return PolicyEvaluationResult(
                        allowed=False,
                        decision=PolicyDecision.BLOCK,
                        reason=f"Rule evaluation error: {e}",
                        rule_name=rule.__class__.__name__,
                        risk_score=1.0,
                    )
                continue

            if res.side_effects_detected:
                aggregated_side_effects.extend(res.side_effects_detected)

            if res.risk_score > max_risk:
                max_risk = res.risk_score

            if not res.allowed:
                # Immediate block or verification requirement
                res.side_effects_detected = aggregated_side_effects
                return res

        return PolicyEvaluationResult(
            allowed=True,
            decision=PolicyDecision.ALLOW,
            reason="All runtime safety policies satisfied.",
            rule_name="PolicyEngineAggregate",
            risk_score=max_risk,
            side_effects_detected=aggregated_side_effects,
        )

    def _log_audit_entry(
        self,
        tool_name: str,
        args: Dict[str, Any],
        eval_result: PolicyEvaluationResult,
        status: str,
        output: Any,
        duration_ms: float,
        audit_id: str,
    ) -> None:
        entry = {
            "audit_id": audit_id,
            "timestamp": time.time(),
            "tool_name": tool_name,
            "args": args,
            "allowed": eval_result.allowed,
            "decision": eval_result.decision.value,
            "rule_name": eval_result.rule_name,
            "reason": eval_result.reason,
            "risk_score": eval_result.risk_score,
            "side_effects": eval_result.side_effects_detected,
            "status": status,
            "output": str(output)[:1000] if output is not None else None,
            "duration_ms": duration_ms,
        }
        self._audit_logs.append(entry)

        if self.audit_trail:
            try:
                if hasattr(self.audit_trail, "log"):
                    self.audit_trail.log(
                        tool_name=tool_name,
                        args=args,
                        result=output if eval_result.allowed else f"BLOCKED: {eval_result.reason}",
                        status=status,
                        why=eval_result.reason,
                    )
                elif hasattr(self.audit_trail, "record"):
                    self.audit_trail.record(entry)
            except Exception as e:
                logger.warning(f"Failed to propagate log to external audit trail: {e}")

    async def execute_tool(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        simulate: bool = False,
    ) -> SandboxExecutionResult:
        """
        Intercepts and executes an MCP tool asynchronously within policy bounds.
        """
        args = args or {}
        context = context or {}
        start_time = time.perf_counter()
        audit_id = str(uuid.uuid4())

        eval_result = self.evaluate_policy(tool_name, args, context)

        if not eval_result.allowed:
            duration = (time.perf_counter() - start_time) * 1000
            self._log_audit_entry(
                tool_name=tool_name,
                args=args,
                eval_result=eval_result,
                status="blocked",
                output=eval_result.reason,
                duration_ms=duration,
                audit_id=audit_id,
            )

            if eval_result.decision == PolicyDecision.REQUIRE_VERIFICATION:
                error_msg = f"Execution blocked: {eval_result.reason}"
                return SandboxExecutionResult(
                    success=False,
                    result=None,
                    error=error_msg,
                    evaluation=eval_result,
                    tool_name=tool_name,
                    execution_time_ms=duration,
                    audit_id=audit_id,
                )
            else:
                error_msg = f"Policy violation: {eval_result.reason}"
                return SandboxExecutionResult(
                    success=False,
                    result=None,
                    error=error_msg,
                    evaluation=eval_result,
                    tool_name=tool_name,
                    execution_time_ms=duration,
                    audit_id=audit_id,
                )

        if simulate:
            duration = (time.perf_counter() - start_time) * 1000
            simulated_out = f"[SIMULATION] Tool '{tool_name}' evaluated valid with no direct execution."
            self._log_audit_entry(
                tool_name=tool_name,
                args=args,
                eval_result=eval_result,
                status="simulated",
                output=simulated_out,
                duration_ms=duration,
                audit_id=audit_id,
            )
            return SandboxExecutionResult(
                success=True,
                result=simulated_out,
                error=None,
                evaluation=eval_result,
                tool_name=tool_name,
                simulated=True,
                execution_time_ms=duration,
                audit_id=audit_id,
            )

        try:
            if inspect.iscoroutinefunction(tool_func):
                res = await tool_func(**args)
            else:
                res = tool_func(**args)

            duration = (time.perf_counter() - start_time) * 1000
            self._log_audit_entry(
                tool_name=tool_name,
                args=args,
                eval_result=eval_result,
                status="success",
                output=res,
                duration_ms=duration,
                audit_id=audit_id,
            )
            return SandboxExecutionResult(
                success=True,
                result=res,
                error=None,
                evaluation=eval_result,
                tool_name=tool_name,
                execution_time_ms=duration,
                audit_id=audit_id,
            )
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._log_audit_entry(
                tool_name=tool_name,
                args=args,
                eval_result=eval_result,
                status="error",
                output=str(e),
                duration_ms=duration,
                audit_id=audit_id,
            )
            return SandboxExecutionResult(
                success=False,
                result=None,
                error=f"Runtime error during tool execution: {e}",
                evaluation=eval_result,
                tool_name=tool_name,
                execution_time_ms=duration,
                audit_id=audit_id,
            )

    def execute_tool_sync(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        simulate: bool = False,
    ) -> SandboxExecutionResult:
        """
        Synchronous wrapper for tool execution within policy sandbox.
        Handles both standalone execution and nested event loop invocation safely.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.execute_tool(
                            tool_func=tool_func,
                            tool_name=tool_name,
                            args=args,
                            context=context,
                            simulate=simulate,
                        )
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.execute_tool(
                    tool_func=tool_func,
                    tool_name=tool_name,
                    args=args,
                    context=context,
                    simulate=simulate,
                )
            )

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        """Returns the internal audit log entries."""
        return list(self._audit_logs)

    def clear_audit_logs(self) -> None:
        """Clears internal audit history."""
        self._audit_logs.clear()
