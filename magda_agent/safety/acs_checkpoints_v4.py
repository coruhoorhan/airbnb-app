import logging
from typing import Dict, Any, Tuple, Optional
from magda_agent.safety.policy import PolicyLayer
from magda_agent.safety.audit_trail import AuditTrail
import re

_SENSITIVE_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret[_-]?key", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE)
]

class ACSCheckpointsV4:
    """
    Implements 5 ACS validation checkpoints for agentic workflows (v4).
    Ensures all actions pass through 5 checks before execution.
    """
    def __init__(self, policy_layer: Optional[PolicyLayer] = None, audit_trail: Optional[AuditTrail] = None) -> None:
        """Initializes the ACSCheckpointsV4 with a logger, policy layer, and audit trail."""
        self.logger = logging.getLogger(__name__)
        self.policy_layer = policy_layer or PolicyLayer()
        self.audit_trail = audit_trail or AuditTrail()

    def checkpoint_1_input_validation(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates raw input data for actions.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating pass/fail and a string reason.
        """
        if not action_data:
            return False, "Checkpoint 1 Failed: empty action data."
        if "action_name" not in action_data:
            return False, "Checkpoint 1 Failed: missing 'action_name'."
        return True, "Checkpoint 1 Passed."

    def checkpoint_2_intent_authorization(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies if the intent is authorized.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating pass/fail and a string reason.
        """
        action = action_data.get("action_name")
        allowed_intents = {
            "read", "write", "execute", "plan", "reflect", "delegate", "analyze", "chat", "test_action"
        }
        if action == "unauthorized_action":
            return False, f"Checkpoint 2 Failed: action '{action}' is explicitly blacklisted."
        if action not in allowed_intents:
            return False, f"Checkpoint 2 Failed: action '{action}' is not in allowed intents."
        return True, "Checkpoint 2 Passed."

    def checkpoint_3_tool_policy(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Checks compliance with tool policies.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating pass/fail and a string reason.
        """
        tool = action_data.get("tool_name")
        if tool == "forbidden_tool":
            return False, f"Checkpoint 3 Failed: tool '{tool}' is forbidden."

        kwargs = action_data.get("kwargs", {})
        allow, explanation = self.policy_layer.evaluate(tool, **kwargs)
        if not allow:
            return False, f"Checkpoint 3 Failed: {explanation}"

        return True, "Checkpoint 3 Passed."

    def checkpoint_4_state_transition(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Ensures the state transition is valid.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating pass/fail and a string reason.
        """
        current_state = action_data.get("state", "idle")
        next_state = action_data.get("next_state")

        allowed_transitions = {
            "idle": ["planning", "reflecting", "analyzing", "executing", "active"],
            "planning": ["executing", "idle"],
            "executing": ["evaluating", "idle"],
            "evaluating": ["idle", "planning"],
            "reflecting": ["idle"],
            "analyzing": ["idle", "planning"],
            "active": ["idle", "executing"],
            "error": ["idle"]
        }

        if current_state not in allowed_transitions:
            return False, f"Checkpoint 4 Failed: unknown current_state '{current_state}'."

        if not next_state:
            return True, "Checkpoint 4 Passed: next_state not provided."

        if next_state not in allowed_transitions[current_state] and next_state != "error":
            return False, f"Checkpoint 4 Failed: cannot transition from '{current_state}' to '{next_state}'."

        return True, "Checkpoint 4 Passed."

    def checkpoint_5_output_sanitization(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Sanitizes output data.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating pass/fail and a string reason.
        """
        output = action_data.get("output")
        if output is None:
            return True, "Checkpoint 5 Passed: no output to sanitize."

        output_str = str(output)
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(output_str):
                return False, f"Checkpoint 5 Failed: sensitive pattern '{pattern.pattern}' detected in output."

        return True, "Checkpoint 5 Passed."

    def validate_action(self, action_data: Dict[str, Any]) -> bool:
        """
        Runs all 5 checkpoints and returns True if all pass.

        Args:
            action_data (Dict[str, Any]): The action data to validate.

        Returns:
            bool: True if all checkpoints pass, False otherwise.
        """
        checkpoints = [
            self.checkpoint_1_input_validation,
            self.checkpoint_2_intent_authorization,
            self.checkpoint_3_tool_policy,
            self.checkpoint_4_state_transition,
            self.checkpoint_5_output_sanitization
        ]

        for checkpoint in checkpoints:
            passed, reason = checkpoint(action_data)
            if not passed:
                self.logger.warning(reason)
                return False

        return True

    def validate_pre_execution(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Runs INPUT and EXECUTION checkpoint stages and logs to audit trail on failure.

        Args:
            action_data: The dictionary containing action context and payload.

        Returns:
            A tuple of (is_passed, message).
        """
        checkpoints = [
            self.checkpoint_1_input_validation,
            self.checkpoint_2_intent_authorization,
            self.checkpoint_3_tool_policy,
            self.checkpoint_4_state_transition,
        ]
        for checkpoint in checkpoints:
            passed, reason = checkpoint(action_data)
            if not passed:
                self.logger.warning(reason)
                self.audit_trail.log_call(
                    tool_name=action_data.get("tool_name", "unknown"),
                    kwargs=action_data.get("kwargs", {}),
                    why=reason,
                    result="blocked",
                    duration=0.0
                )
                return False, reason
        return True, "Pre-execution checks passed"

    def validate_post_execution(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Runs OUTPUT checkpoint stage and logs to audit trail on failure.

        Args:
            action_data: The dictionary containing action context and payload.

        Returns:
            A tuple of (is_passed, message).
        """
        passed, reason = self.checkpoint_5_output_sanitization(action_data)
        if not passed:
            self.logger.warning(reason)
            self.audit_trail.log_call(
                tool_name=action_data.get("tool_name", "unknown"),
                kwargs=action_data.get("kwargs", {}),
                why=reason,
                result="blocked",
                duration=0.0
            )
            return False, reason
        return True, "Post-execution checks passed"
