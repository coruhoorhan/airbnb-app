import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from magda_agent.safety.acs_guard import ACSGuard, SecurityViolationError
from magda_agent.safety.audit_trail import AuditTrail

CHECKPOINT_METADATA = [
    {"checkpoint_id": 1, "name": "Input Validation", "stage": "input"},
    {"checkpoint_id": 2, "name": "Intent Authorization", "stage": "input"},
    {"checkpoint_id": 3, "name": "Tool Policy", "stage": "execution"},
    {"checkpoint_id": 4, "name": "State Transition", "stage": "execution"},
    {"checkpoint_id": 5, "name": "Output Sanitization", "stage": "output"},
]

class ACSStructuredLogger:
    """
    Structured logging for ACS (Agent Control Specification) validation checkpoints.
    Captures fine-grained evaluation logs for each checkpoint and exports them to centralized audit trail and logger.
    """

    def __init__(
        self,
        acs_guard: Optional[ACSGuard] = None,
        audit_trail: Optional[AuditTrail] = None,
        logger: Optional[logging.Logger] = None
    ) -> None:
        """
        Initializes the ACSStructuredLogger.

        Args:
            acs_guard: ACSGuard instance containing validation checkpoints.
            audit_trail: AuditTrail instance for recording logs.
            logger: Standard logging.Logger instance.
        """
        self.acs_guard = acs_guard or ACSGuard()
        self.audit_trail = audit_trail or AuditTrail()
        self.logger = logger or logging.getLogger(__name__)

    def evaluate_checkpoints(self, workflow_data: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Evaluates workflow_data through each ACS checkpoint, producing structured log entries.

        Args:
            workflow_data: Dictionary containing action/workflow parameters.

        Returns:
            Tuple of (overall_passed, list_of_structured_log_entries).
        """
        logs: List[Dict[str, Any]] = []
        overall_passed = True
        tool_name = workflow_data.get("tool") or workflow_data.get("tool_name", "unknown")
        action_name = workflow_data.get("action") or workflow_data.get("action_name", "unknown")
        kwargs = workflow_data.get("kwargs", {})

        checkpoints = getattr(self.acs_guard, "checkpoints", [])
        if not checkpoints:
            # Fallback if acs_guard uses methods instead of ACSCheckpoint list
            checkpoints_funcs = [
                getattr(self.acs_guard, "checkpoint_1_input_validation", None),
                getattr(self.acs_guard, "checkpoint_2_intent_authorization", None),
                getattr(self.acs_guard, "checkpoint_3_tool_policy", None),
                getattr(self.acs_guard, "checkpoint_4_state_transition", None),
                getattr(self.acs_guard, "checkpoint_5_output_sanitization", None),
            ]
            checkpoints_funcs = [f for f in checkpoints_funcs if f is not None]

        for idx, meta in enumerate(CHECKPOINT_METADATA):
            checkpoint_id = meta["checkpoint_id"]
            name = meta["name"]
            stage = meta["stage"]
            timestamp = time.time()

            passed = False
            reason = "Validation failed"

            if hasattr(self.acs_guard, "checkpoints") and idx < len(self.acs_guard.checkpoints):
                cp = self.acs_guard.checkpoints[idx]
                passed, reason = cp.validate(workflow_data)
            elif idx < len(checkpoints_funcs):
                passed, reason = checkpoints_funcs[idx](workflow_data)

            status = "passed" if passed else "failed"

            log_entry = {
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": name,
                "stage": stage,
                "status": status,
                "reason": reason,
                "action": action_name,
                "tool_name": tool_name,
                "kwargs": kwargs,
                "timestamp": timestamp
            }

            logs.append(log_entry)

            # Log structured entry via python logging
            log_str = json.dumps(log_entry)
            if passed:
                self.logger.debug(f"ACS Structured Log: {log_str}")
            else:
                self.logger.warning(f"ACS Structured Log: {log_str}")

            # Export to audit trail
            self.audit_trail.log_call(
                tool_name=tool_name,
                kwargs={"checkpoint": name, "stage": stage, **kwargs},
                why=reason,
                result="allowed" if passed else "blocked",
                duration=0.0
            )

            if not passed:
                overall_passed = False

        return overall_passed, logs

    def intercept_and_log(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates checkpoints with structured logging and raises SecurityViolationError on failure.

        Args:
            workflow_data: Dictionary containing action/workflow parameters.

        Returns:
            The input workflow_data if all checkpoints pass.

        Raises:
            SecurityViolationError: If any ACS checkpoint fails.
        """
        overall_passed, logs = self.evaluate_checkpoints(workflow_data)
        if not overall_passed:
            failed_reasons = [f"Checkpoint {l['checkpoint_id']} ({l['checkpoint_name']}): {l['reason']}" for l in logs if l["status"] == "failed"]
            combined_reason = "; ".join(failed_reasons)
            raise SecurityViolationError(f"Action blocked by ACS checkpoints: {combined_reason}")

        return workflow_data
