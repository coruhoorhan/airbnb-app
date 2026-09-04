import logging
from typing import Dict, Any, Callable, Optional

from magda_agent.safety.acs import ACSWorkflowGuard


class AgenticWorkflow:
    """
    An Agentic Workflow that embeds 5 distinct ACS runtime validation checkpoints
    around state changes and tool executions.
    """

    def __init__(self, guard: Optional[ACSWorkflowGuard] = None) -> None:
        """
        Initializes the AgenticWorkflow.

        Args:
            guard: Optional ACSWorkflowGuard instance.
        """
        self.guard = guard or ACSWorkflowGuard()
        self.logger = logging.getLogger(__name__)

    def execute_action(
        self,
        action: str,
        tool_name: str,
        tool_func: Callable[..., Any],
        kwargs: Dict[str, Any],
        current_state: str = "idle",
        next_state: str = "idle"
    ) -> Dict[str, Any]:
        """
        Executes an action within the agentic workflow, validating against 5 ACS checkpoints.

        Args:
            action: The intent (e.g., 'execute', 'read').
            tool_name: The name of the tool.
            tool_func: The actual callable to invoke.
            kwargs: Arguments to pass to the tool.
            current_state: Current workflow state.
            next_state: Proposed next workflow state.

        Returns:
            A dictionary containing the state of the workflow and the output.
        """
        workflow_data = {
            "action": action,
            "tool": tool_name,
            "kwargs": kwargs,
            "current_state": current_state,
            "next_state": next_state,
        }

        # Checkpoint 1: Input Validation
        passed, reason = self.guard.checkpoint_1_input_validation(workflow_data)
        if not passed:
            return self._abort_workflow(f"ACS Checkpoint 1 Failed: {reason}")

        # Checkpoint 2: Intent Authorization
        passed, reason = self.guard.checkpoint_2_intent_authorization(workflow_data)
        if not passed:
            return self._abort_workflow(f"ACS Checkpoint 2 Failed: {reason}")

        # Checkpoint 3: Tool Policy
        passed, reason = self.guard.checkpoint_3_tool_policy(workflow_data)
        if not passed:
            return self._abort_workflow(f"ACS Checkpoint 3 Failed: {reason}")

        # Checkpoint 4: State Transition (Pre-execution check)
        passed, reason = self.guard.checkpoint_4_state_transition(workflow_data)
        if not passed:
            return self._abort_workflow(f"ACS Checkpoint 4 Failed: {reason}")

        # Execute Tool
        try:
            output = tool_func(**kwargs)
            workflow_data["output"] = output
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            return self._abort_workflow(f"Tool execution failed: {str(e)}")

        # Checkpoint 5: Output Sanitization
        passed, reason = self.guard.checkpoint_5_output_sanitization(workflow_data)
        if not passed:
            return self._abort_workflow(f"ACS Checkpoint 5 Failed: {reason}")

        # Final state transition
        return {
            "status": "success",
            "current_state": next_state,
            "output": workflow_data["output"]
        }

    def _abort_workflow(self, reason: str) -> Dict[str, Any]:
        """
        Gracefully aborts the workflow, transitioning to error state.

        Args:
            reason: The reason for aborting the workflow.

        Returns:
            A dictionary representing the error state.
        """
        self.logger.warning(f"Workflow aborted: {reason}")
        return {
            "status": "error",
            "current_state": "error",
            "error_reason": reason,
            "output": None
        }
