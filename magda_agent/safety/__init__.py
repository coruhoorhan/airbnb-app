"""
Safety and governance package for Magda Agent.
"""

from magda_agent.safety.secret_redaction import SecretRedactor

try:
    from magda_agent.safety.acs import ACSWorkflowGuard, SecurityViolationError
except ImportError:
    ACSWorkflowGuard = None  # type: ignore[assignment, misc]
    SecurityViolationError = None  # type: ignore[assignment, misc]

try:
    from magda_agent.safety.runtime_governance import (
        GovernanceViolationError,
        RuntimeGovernanceLayer,
    )
except ImportError:
    RuntimeGovernanceLayer = None  # type: ignore[assignment, misc]
    GovernanceViolationError = None  # type: ignore[assignment, misc]

try:
    from magda_agent.safety.acs_guardrails import (
        ACSGuardrailsV2,
        GuardrailViolationError,
    )
except ImportError:
    ACSGuardrailsV2 = None  # type: ignore[assignment, misc]
    GuardrailViolationError = None  # type: ignore[assignment, misc]

__all__ = [
    "ACSWorkflowGuard",
    "SecurityViolationError",
    "RuntimeGovernanceLayer",
    "GovernanceViolationError",
    "ACSGuardrailsV2",
    "GuardrailViolationError",
    "SecretRedactor",
]
