from typing import Dict, Any, Tuple

class ACSStateTransitionV5:
    """
    Microsoft ACS state transition guardrail V5.
    Implements checkpoint 4 to validate state transitions within the cognitive architecture.
    """

    def checkpoint_4_state_transition(self, workflow_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Checkpoint 4: State Transition.
        Ensures the proposed state transition is valid within the cognitive architecture.

        Args:
            workflow_data: A dictionary containing 'current_state' and 'next_state'.

        Returns:
            A tuple containing a boolean indicating if the transition is allowed, and a string explanation.
        """
        current_state = workflow_data.get("current_state", "idle")
        next_state = workflow_data.get("next_state")

        if not next_state:
            return True, "State transition passed: next_state not provided."

        allowed_transitions = {
            "idle": ["planning", "reflecting", "analyzing", "executing"],
            "planning": ["executing", "idle"],
            "executing": ["evaluating", "idle"],
            "evaluating": ["idle", "planning"],
            "reflecting": ["idle"],
            "analyzing": ["idle", "planning"],
            "error": ["idle"]
        }

        if current_state not in allowed_transitions:
            return False, f"State transition failed: unknown current_state '{current_state}'."

        if next_state not in allowed_transitions[current_state] and next_state != "error":
            return False, f"State transition failed: cannot transition from '{current_state}' to '{next_state}'."

        return True, "State transition passed."
