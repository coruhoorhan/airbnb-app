import logging
from typing import Any, Dict, List, Optional
from magda_agent.emotions.mirror_neurons import MirrorNeurons

logger = logging.getLogger(__name__)

class OnlineRLFeedbackLoopV6:
    """
    Online reinforcement learning loop v6.
    Adjusts internal action weights based on parsed next-state user feedback.
    Trains agent simply by talking. Inspired by OpenClaw-RL.
    """

    def __init__(self, mirror_neurons: Optional[MirrorNeurons] = None) -> None:
        """
        Initializes the online RL loop.

        Args:
            mirror_neurons (Optional[MirrorNeurons]): MirrorNeurons instance for extracting sentiment shifts.
        """
        self.mirror_neurons = mirror_neurons or MirrorNeurons()
        self.weights: Dict[str, float] = {
            "verbosity": 1.0,
            "directness": 1.0,
            "empathy": 1.0
        }
        self.trajectory_log: List[Dict[str, Any]] = []
        logger.info("OnlineRLFeedbackLoopV6 initialized.")

    async def adjust_behavior(self, current_user_message: str, last_context: str, user_id: Optional[str] = None) -> None:
        """
        Adjusts internal action weights based on parsed next-state user feedback.

        Args:
            current_user_message (str): The current message from the user, acting as the next-state signal.
            last_context (str): The context of the previous state/action.
            user_id (Optional[str]): The ID of the user.
        """
        # Extract sentiment shifts from user's message using MirrorNeurons
        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(current_user_message)

        # Log the trajectory
        self.trajectory_log.append({
            "state": last_context,
            "next_state": current_user_message,
            "reward": p_shift,
            "user_id": user_id
        })

        # Adjust weights based on the primary reward signal (Pleasure shift)
        if p_shift > 0.1:
            self.weights["verbosity"] = min(2.0, self.weights["verbosity"] + 0.05)
            self.weights["empathy"] = min(2.0, self.weights["empathy"] + 0.05)
            logger.info(f"Positive feedback detected (P-shift: {p_shift:.2f}). Increasing verbosity and empathy.")
        elif p_shift < -0.1:
            self.weights["verbosity"] = max(0.5, self.weights["verbosity"] - 0.05)
            self.weights["directness"] = min(2.0, self.weights["directness"] + 0.05)
            logger.info(f"Negative feedback detected (P-shift: {p_shift:.2f}). Decreasing verbosity, increasing directness.")

    def get_weights(self) -> Dict[str, float]:
        """
        Returns the current internal action weights.

        Returns:
            Dict[str, float]: A dictionary containing current weights.
        """
        return self.weights.copy()
