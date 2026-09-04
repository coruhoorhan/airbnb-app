import logging
import uuid
from typing import Any, Dict, List, Optional
from magda_agent.emotions.mirror_neurons import MirrorNeurons

logger = logging.getLogger(__name__)

class OnlineRLFeedbackLoopV7:
    """
    Online reinforcement learning loop v7.
    Adjusts internal action weights based on parsed next-state user feedback.
    Extends v6 with capabilities for delayed rewards via explicit user actions (e.g., click-throughs).
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
        self.pending_interactions: Dict[str, Dict[str, Any]] = {}
        logger.info("OnlineRLFeedbackLoopV7 initialized.")

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
        self._apply_reward(p_shift)

    def _apply_reward(self, reward: float) -> None:
        """
        Applies a reward to adjust the weights.

        Args:
            reward (float): The reward to apply.
        """
        if reward > 0.1:
            self.weights["verbosity"] = min(2.0, self.weights["verbosity"] + 0.05)
            self.weights["empathy"] = min(2.0, self.weights["empathy"] + 0.05)
            logger.info(f"Positive feedback detected (Reward: {reward:.2f}). Increasing verbosity and empathy.")
        elif reward < -0.1:
            self.weights["verbosity"] = max(0.5, self.weights["verbosity"] - 0.05)
            self.weights["directness"] = min(2.0, self.weights["directness"] + 0.05)
            logger.info(f"Negative feedback detected (Reward: {reward:.2f}). Decreasing verbosity, increasing directness.")

    def register_interaction(self, state_context: str, expected_action_type: str, user_id: Optional[str] = None) -> str:
        """
        Registers an interaction that may receive delayed feedback.

        Args:
            state_context (str): The context of the interaction.
            expected_action_type (str): The type of action expected (e.g., 'click', 'purchase').
            user_id (Optional[str]): The ID of the user.

        Returns:
            str: The unique interaction ID.
        """
        interaction_id = str(uuid.uuid4())
        self.pending_interactions[interaction_id] = {
            "state": state_context,
            "expected_action_type": expected_action_type,
            "user_id": user_id
        }
        logger.info(f"Registered interaction {interaction_id} for delayed feedback.")
        return interaction_id

    async def apply_delayed_feedback(self, interaction_id: str, reward: float) -> None:
        """
        Applies a delayed reward for a previously registered interaction.

        Args:
            interaction_id (str): The ID of the interaction.
            reward (float): The reward value to apply.
        """
        if interaction_id not in self.pending_interactions:
            logger.warning(f"Interaction {interaction_id} not found for delayed feedback.")
            return

        interaction = self.pending_interactions.pop(interaction_id)

        # Log the delayed trajectory
        self.trajectory_log.append({
            "state": interaction["state"],
            "next_state": f"Delayed Action: {interaction['expected_action_type']}",
            "reward": reward,
            "user_id": interaction["user_id"]
        })

        self._apply_reward(reward)
        logger.info(f"Applied delayed reward {reward} for interaction {interaction_id}.")

    def get_weights(self) -> Dict[str, float]:
        """
        Returns the current internal action weights.

        Returns:
            Dict[str, float]: A dictionary containing current weights.
        """
        return self.weights.copy()
