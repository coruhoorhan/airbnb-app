from typing import Dict, Optional
import logging

class RealtimePolicyGradientUpdater:
    """
    A real-time policy gradient module that modifies action weights dynamically
    mid-session based on cumulative PAD emotion shifts without full consolidation.
    """
    def __init__(self) -> None:
        """
        Initializes the RealtimePolicyGradientUpdater with empty in-memory weight storage.
        """
        # Maps user_id to a dictionary mapping action_name to weight.
        self._user_weights: Dict[str, Dict[str, float]] = {}

    def process_mid_session_emotion_shift(
        self,
        user_id: str,
        action_taken: str,
        pleasure_shift: float,
        arousal_shift: float,
        dominance_shift: float
    ) -> None:
        """
        Processes mid-session cumulative PAD emotion shifts and adjusts action weights
        dynamically in-memory.

        Args:
            user_id (str): The ID of the user session.
            action_taken (str): The action that was taken to cause this shift.
            pleasure_shift (float): The change in the pleasure dimension (-1.0 to 1.0).
            arousal_shift (float): The change in the arousal dimension (-1.0 to 1.0).
            dominance_shift (float): The change in the dominance dimension (-1.0 to 1.0).
        """
        if user_id not in self._user_weights:
            self._user_weights[user_id] = {}

        user_session = self._user_weights[user_id]

        if action_taken not in user_session:
            user_session[action_taken] = 1.0

        current_weight = user_session[action_taken]

        # Simple heuristic for real-time update based on pleasure and arousal shifts.
        # High pleasure increases weight, low pleasure decreases it.
        # High arousal magnifies the effect.
        magnifier = 1.0 + max(0.0, arousal_shift)
        weight_shift = (pleasure_shift * 0.2) * magnifier

        new_weight = current_weight + weight_shift
        # Bounding the weights between 0.1 and 3.0
        new_weight = max(0.1, min(3.0, new_weight))

        user_session[action_taken] = new_weight

        logging.info(
            f"PolicyGradientUpdater: User '{user_id}' action '{action_taken}' "
            f"weight updated from {current_weight:.2f} to {new_weight:.2f} "
            f"(P_shift={pleasure_shift:.2f}, A_shift={arousal_shift:.2f})"
        )

    def get_dynamic_action_weights(self, user_id: str) -> Dict[str, float]:
        """
        Retrieves the dynamically adjusted action weights for a given user.

        Args:
            user_id (str): The ID of the user session.

        Returns:
            Dict[str, float]: A dictionary mapping action names to their current weights.
        """
        return self._user_weights.get(user_id, {})
