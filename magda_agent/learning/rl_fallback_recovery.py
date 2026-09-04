import logging
from typing import Optional, Dict, Any

class RLFallbackRecoveryHandler:
    """
    OpenClaw-RL Fallback Recovery Handler.
    Intercepts execution errors and extracts contextual features, then
    triggers negative habit weight reinforcement utilizing the online learning loop
    or the HabitTracker directly.
    """
    def __init__(self, online_rl_integrator: Any = None) -> None:
        """
        Initializes the recovery handler.

        Args:
            online_rl_integrator (Any): The online RL integrator to process negative feedback.
        """
        self.online_rl_integrator = online_rl_integrator

    async def handle_execution_error(
        self,
        exception: Exception,
        action_context: str,
        skill_used: str,
        user_id: Optional[int] = None
    ) -> None:
        """
        Handles an exception during tool execution by extracting contextual features
        and sending a negative reinforcement signal to reduce the weight of the failed path.

        Args:
            exception (Exception): The exception that was raised.
            action_context (str): The context or input text leading to the error.
            skill_used (str): The name of the skill that failed.
            user_id (Optional[int]): The user ID associated with the interaction.
        """
        error_message = str(exception)
        error_type = type(exception).__name__

        logging.error(f"RLFallbackRecoveryHandler intercepted error: {error_type}: {error_message} in skill {skill_used}")

        # We simulate a negative user reply based on the error to trigger negative feedback in the RL integrator
        synthetic_negative_feedback = f"Execution failed with {error_type}: {error_message}"

        if self.online_rl_integrator:
            # We pass explicit_score=0.0 to strongly penalize the failed tool
            await self.online_rl_integrator.process_feedback(
                user_reply=synthetic_negative_feedback,
                action_context=action_context,
                user_id=user_id,
                explicit_score=0.0,
                tool_success=False,
                skill_used=skill_used
            )
            logging.info(f"RLFallbackRecoveryHandler applied negative reinforcement for {skill_used}")
