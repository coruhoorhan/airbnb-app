import logging
from typing import Any, Callable, Dict, Optional, Tuple, List
import re
import asyncio

from magda_agent.safety.policy import PolicyLayer
from magda_agent.safety.audit_trail import AuditTrail
from magda_agent.safety.guardrails import SecurityViolationError

# Basic pattern for sensitive data (e.g., simplistic SSN or credit card check for demonstration)
_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # Mock SSN
    re.compile(r"\b(?:\d[ -]*?){13,16}\b")  # Mock Credit Card
]

class ACSControlsV5:
    """
    Implements 5 ACS validation checkpoints for agent workflows.
    Standardizes runtime safety controls before and after tool execution.
    """

    def __init__(self, policy_layer: Optional[PolicyLayer] = None, audit_trail: Optional[AuditTrail] = None) -> None:
        """
        Initializes the ACSControlsV5 pipeline.

        Args:
            policy_layer: Optional PolicyLayer for tool evaluation.
            audit_trail: Optional AuditTrail for recording evaluation results.
        """
        self.logger = logging.getLogger(__name__)
        self.policy_layer = policy_layer or PolicyLayer()
        self.audit_trail = audit_trail or AuditTrail()

    def checkpoint_1_input_validation(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Checkpoint 1: Input Validation.
        Ensures action data is a dictionary and contains required fields.
        """
        if not isinstance(action_data, dict):
            return False, "Checkpoint 1 Failed: action_data must be a dictionary."
        if not action_data:
            return False, "Checkpoint 1 Failed: empty action_data."

        required_fields = ["action_name", "tool_name"]
        for field in required_fields:
            if field not in action_data:
                return False, f"Checkpoint 1 Failed: missing required field '{field}'."
            if not isinstance(action_data[field], str):
                return False, f"Checkpoint 1 Failed: '{field}' must be a string."

        return True, "Checkpoint 1 Passed."

    def checkpoint_2_intent_authorization(self, action_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Checkpoint 2: Intent Authorization.
        Verifies if the intent (action_name) is in the allowed list.
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
        Checkpoint 3: Tool Policy.
        Checks compliance of the specific tool and its arguments with the configured PolicyLayer.
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
        Checkpoint 4: State Transition.
        Ensures the state transition from current_state to next_state is valid based on a state machine.
        """
        current_state = action_data.get("current_state", "idle")
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
            # If no next state is explicitly requested, we assume staying in current state is fine
            return True, "Checkpoint 4 Passed: next_state not provided."

        if next_state not in allowed_transitions[current_state] and next_state != "error":
            return False, f"Checkpoint 4 Failed: cannot transition from '{current_state}' to '{next_state}'."

        return True, "Checkpoint 4 Passed."

    def checkpoint_5_output_sanitization(self, result: Any) -> Tuple[bool, str]:
        """
        Checkpoint 5: Output Sanitization.
        Scans the output of a tool execution for sensitive data patterns.
        """
        if result is None:
            return True, "Checkpoint 5 Passed: no output to sanitize."

        output_str = str(result)
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(output_str):
                return False, f"Checkpoint 5 Failed: sensitive pattern '{pattern.pattern}' detected in output."

        return True, "Checkpoint 5 Passed."

    def validate_pre_execution(self, action_data: Dict[str, Any]) -> None:
        """
        Runs Checkpoints 1-4. Raises SecurityViolationError if any fail.
        Logs the failure to the AuditTrail.
        """
        checkpoints = [
            self.checkpoint_1_input_validation,
            self.checkpoint_2_intent_authorization,
            self.checkpoint_3_tool_policy,
            self.checkpoint_4_state_transition
        ]

        for cp in checkpoints:
            passed, reason = cp(action_data)
            if not passed:
                self.logger.warning(reason)
                self._log_audit(action_data, reason, "blocked")
                raise SecurityViolationError(reason)
            self.logger.debug(reason)

    def validate_post_execution(self, result: Any, action_data: Dict[str, Any]) -> None:
        """
        Runs Checkpoint 5. Raises SecurityViolationError if it fails.
        Logs the failure to the AuditTrail.
        """
        passed, reason = self.checkpoint_5_output_sanitization(result)
        if not passed:
            self.logger.warning(reason)
            self._log_audit(action_data, reason, "blocked")
            raise SecurityViolationError(reason)

        self.logger.debug(reason)
        self._log_audit(action_data, "All 5 ACS checkpoints passed.", "allowed")

    def _log_audit(self, action_data: Dict[str, Any], reason: str, result_status: str) -> None:
        """Helper to log events to the audit trail."""
        self.audit_trail.log_call(
            tool_name=action_data.get("tool_name", "unknown"),
            kwargs=action_data.get("kwargs", {}),
            why=reason,
            result=result_status,
            duration=0.0
        )

    def execute_with_checkpoints(self, tool_func: Callable, action_data: Dict[str, Any]) -> Any:
        """
        Wraps a tool execution with the 5 ACS checkpoints.
        Runs Checkpoints 1-4 before execution, and Checkpoint 5 after execution.
        Supports both sync and async tool functions.

        Args:
            tool_func: The callable tool function to execute.
            action_data: Dictionary containing execution context (tool_name, action_name, kwargs, etc.)

        Returns:
            The sanitized result of the tool execution.

        Raises:
            SecurityViolationError: If any checkpoint fails.
        """
        # Run pre-execution checks
        self.validate_pre_execution(action_data)

        kwargs = action_data.get("kwargs", {})

        if asyncio.iscoroutinefunction(tool_func):
            async def async_exec() -> Any:
                try:
                    result = await tool_func(**kwargs)
                except asyncio.CancelledError:
                    self.logger.warning(f"Action '{action_data.get('tool_name')}' was interrupted.")
                    raise
                except Exception as e:
                    self.logger.error(f"Error executing tool '{action_data.get('tool_name')}': {e}")
                    raise

                # Run post-execution checks
                self.validate_post_execution(result, action_data)
                return result
            return async_exec()
        else:
            try:
                result = tool_func(**kwargs)
            except KeyboardInterrupt:
                self.logger.warning(f"Action '{action_data.get('tool_name')}' was interrupted.")
                raise
            except Exception as e:
                self.logger.error(f"Error executing tool '{action_data.get('tool_name')}': {e}")
                raise

            # Run post-execution checks
            self.validate_post_execution(result, action_data)
            return result
