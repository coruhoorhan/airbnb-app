"""A2A Message Taint Sandbox Integration."""

from typing import Any, Dict
from magda_agent.security.mcp_kernel_taint import mark_tainted, is_tainted, sanitize, PolicyViolationError

class A2ATaintError(PolicyViolationError):
    """Raised when an A2A message contains unsafe or tainted data."""
    pass

def process_a2a_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes an incoming A2A delegate message.
    Taints the message to prevent it from executing unsafe operations directly.
    """
    return mark_tainted(message)

def _has_injection(payload: Any) -> bool:
    """Checks for prompt injections or malicious commands."""
    s = str(payload).lower()
    dangerous_patterns = ["rm -rf", "system(", "exec(", "eval(", "drop table", "ignore previous instructions"]
    for pattern in dangerous_patterns:
        if pattern in s:
            return True
    return False

def validate_a2a_execution(payload: Any) -> Any:
    """
    Validates a payload before local execution.
    If the payload is tainted AND contains dangerous patterns, it raises an A2ATaintError.
    Otherwise, returns the sanitized payload.
    """
    if is_tainted(payload) and _has_injection(payload):
        raise A2ATaintError("A2A payload is tainted and contains dangerous patterns.")
    return sanitize(payload)
