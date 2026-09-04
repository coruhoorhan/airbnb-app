"""
ACS Compliance Policy Guardrails V7.

Inspired by ACS safety and compliance trends: Implements a centralized,
declarative compliance policy validation layer that evaluates tool calls
and workflows dynamically prior to tool execution and output dispatch.
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


class PolicyRuleType(str, Enum):
    DENYLIST = "denylist"
    ALLOWLIST = "allowlist"
    ARG_VALIDATION = "arg_validation"
    ROLE_BASED = "role_based"
    DATA_PRIVACY = "data_privacy"
    CUSTOM = "custom"


class ACSCompliancePolicyViolationError(Exception):
    """Raised when an action violates an ACS compliance policy rule."""

    def __init__(self, tool_name: str, rule_id: str, reason: str, feedback: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"ACS Compliance Guardrails V7 Violation on tool '{tool_name}' [Rule: {rule_id}]: {reason}"
        )
        self.tool_name = tool_name
        self.rule_id = rule_id
        self.reason = reason
        self.feedback = feedback or {}


@dataclass
class CompliancePolicyRule:
    """Represents an individual compliance policy rule."""

    rule_id: str
    name: str
    rule_type: PolicyRuleType
    target_tools: Set[str] = field(default_factory=lambda: {"*"})
    evaluator: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Tuple[bool, str]]] = None
    severity: str = "high"  # critical, high, medium, low
    description: str = ""

    def applies_to(self, tool_name: str) -> bool:
        return "*" in self.target_tools or tool_name in self.target_tools


@dataclass
class ComplianceEvaluationReport:
    """Report summarizing policy evaluation prior to tool execution."""

    allowed: bool
    tool_name: str
    violated_rules: List[Dict[str, Any]] = field(default_factory=list)
    passed_rules: List[str] = field(default_factory=list)
    decision_reason: str = "All compliance rules passed."
    audit_id: str = field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:8]}")
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "tool_name": self.tool_name,
            "violated_rules": self.violated_rules,
            "passed_rules": self.passed_rules,
            "decision_reason": self.decision_reason,
            "audit_id": self.audit_id,
            "evaluated_at": self.evaluated_at,
        }


class ACSGuardrailsV7:
    """
    ACS Compliance Policy Guardrails V7.

    Centralized pre-execution compliance policy engine that intercepts tool calls,
    validating arguments, caller roles, and data boundaries.
    """

    DEFAULT_FORBIDDEN_COMMANDS = [
        r"\brm\s+-(?:r|f|rf|fr)\s+(?:/|/\*|~|\$HOME)",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
        r"\bmkfs\.",
        r"\bdd\s+if=.*of=/dev/",
    ]

    DEFAULT_SENSITIVE_PATTERNS = [
        r"(?:api[_-]?key|bearer|password|secret|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?",
        r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
    ]

    def __init__(self, enable_defaults: bool = True):
        self._rules: Dict[str, CompliancePolicyRule] = {}
        self._audit_trail: List[ComplianceEvaluationReport] = []

        if enable_defaults:
            self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register baseline enterprise compliance policy rules."""
        # 1. Dangerous command injection rule
        cmd_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEFAULT_FORBIDDEN_COMMANDS]

        def eval_cmd(tool_name: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[bool, str]:
            for k, v in args.items():
                if isinstance(v, str):
                    for pat in cmd_patterns:
                        if pat.search(v):
                            return False, f"Dangerous command pattern '{pat.pattern}' detected in argument '{k}'"
            return True, "No dangerous command pattern detected."

        self.add_policy_rule(CompliancePolicyRule(
            rule_id="RULE_NO_DESTRUCTIVE_COMMANDS",
            name="Prevent Destructive Shell Commands",
            rule_type=PolicyRuleType.DENYLIST,
            target_tools={"bash", "run_shell_command", "system_execute_code", "execute_code"},
            evaluator=eval_cmd,
            severity="critical",
        ))

        # 2. Role permission rule
        def eval_role(tool_name: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[bool, str]:
            role = ctx.get("role") or ctx.get("user_role") or "user"
            restricted = {"system_execute_code", "execute_code", "delete_database"}
            if tool_name in restricted and role not in ("admin", "developer"):
                return False, f"Caller role '{role}' is not authorized to execute restricted tool '{tool_name}'"
            return True, "Role authorization verified."

        self.add_policy_rule(CompliancePolicyRule(
            rule_id="RULE_RBAC_AUTHORIZATION",
            name="Role-Based Access Control",
            rule_type=PolicyRuleType.ROLE_BASED,
            target_tools={"*"},
            evaluator=eval_role,
            severity="high",
        ))

    def add_policy_rule(self, rule: CompliancePolicyRule) -> None:
        """Add or update a compliance policy rule."""
        self._rules[rule.rule_id] = rule

    def remove_policy_rule(self, rule_id: str) -> bool:
        """Remove a compliance policy rule by ID."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def evaluate_policy(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceEvaluationReport:
        """
        Evaluate tool execution against all applicable compliance rules.
        """
        ctx = context or {}
        violations: List[Dict[str, Any]] = []
        passed: List[str] = []

        for rule in self._rules.values():
            if rule.applies_to(tool_name):
                if rule.evaluator:
                    try:
                        is_ok, reason = rule.evaluator(tool_name, arguments, ctx)
                        if not is_ok:
                            violations.append({
                                "rule_id": rule.rule_id,
                                "name": rule.name,
                                "severity": rule.severity,
                                "reason": reason,
                            })
                        else:
                            passed.append(rule.rule_id)
                    except Exception as ex:
                        violations.append({
                            "rule_id": rule.rule_id,
                            "name": rule.name,
                            "severity": rule.severity,
                            "reason": f"Evaluator error: {str(ex)}",
                        })
                else:
                    passed.append(rule.rule_id)

        allowed = len(violations) == 0
        decision_reason = (
            "All compliance rules passed."
            if allowed
            else f"Compliance policy violations: {'; '.join(v['reason'] for v in violations)}"
        )

        report = ComplianceEvaluationReport(
            allowed=allowed,
            tool_name=tool_name,
            violated_rules=violations,
            passed_rules=passed,
            decision_reason=decision_reason,
        )
        self._audit_trail.append(report)
        return report

    def execute_with_guardrails(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a tool wrapped with dynamic compliance guardrail evaluations.
        Raises ACSCompliancePolicyViolationError if any rule is violated.
        """
        report = self.evaluate_policy(tool_name, arguments, context)
        if not report.allowed:
            first_v = report.violated_rules[0]
            logger.warning(f"Blocked by ACS Guardrails V7: {first_v['reason']}")
            raise ACSCompliancePolicyViolationError(
                tool_name=tool_name,
                rule_id=first_v["rule_id"],
                reason=first_v["reason"],
                feedback={"violated_rules": report.violated_rules},
            )

        return tool_func(**arguments)

    async def execute_with_guardrails_async(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Asynchronously execute a tool wrapped with dynamic compliance guardrail evaluations.
        """
        report = self.evaluate_policy(tool_name, arguments, context)
        if not report.allowed:
            first_v = report.violated_rules[0]
            logger.warning(f"Blocked by ACS Guardrails V7: {first_v['reason']}")
            raise ACSCompliancePolicyViolationError(
                tool_name=tool_name,
                rule_id=first_v["rule_id"],
                reason=first_v["reason"],
                feedback={"violated_rules": report.violated_rules},
            )

        if inspect.iscoroutinefunction(tool_func):
            return await tool_func(**arguments)
        return tool_func(**arguments)

    def get_audit_trail(self) -> List[ComplianceEvaluationReport]:
        """Retrieve audit history."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit history."""
        self._audit_trail.clear()
