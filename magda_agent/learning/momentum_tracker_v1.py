import time
import logging
from typing import Dict, Any

from magda_agent.user_model.model import UserModel

class MomentumTracker:
    """
    OpenClaw RL Conversation Momentum Tracking.

    Monitors interaction speed and depth, using it as an implicit RL reward signal
    to tune agent response brevity (verbosity weights in the user model).
    """

    def __init__(self, user_model: UserModel) -> None:
        """
        Initializes the MomentumTracker.

        Args:
            user_model (UserModel): The persistent user model for adjusting behavior weights.
        """
        self.user_model = user_model
        # Store state per user: last timestamp, last depth
        self.user_states: Dict[int, Dict[str, Any]] = {}

    def track_and_update(self, user_id: int, interaction_text: str) -> None:
        """
        Calculates interaction speed and depth and updates RL verbosity weights.

        Args:
            user_id (int): The user's ID.
            interaction_text (str): The text of the current interaction.
        """
        now: float = time.time()
        depth: int = len(interaction_text.split())

        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "last_timestamp": now,
                "last_depth": depth
            }
            return

        last_state: Dict[str, Any] = self.user_states[user_id]
        time_delta: float = now - last_state["last_timestamp"]

        # Calculate speed (inverse of time delta, bounded)
        # Bounded between 1 and 300 seconds
        time_delta = max(1.0, min(time_delta, 300.0))
        speed: float = 100.0 / time_delta  # Higher speed = faster response

        # Momentum heuristic: speed combined with depth
        momentum_score: float = speed + (depth * 0.1)

        # Tune agent response brevity
        model_data: Dict[str, Any] = self.user_model.get_model(user_id)

        behavior_weights: Dict[str, float] = model_data.setdefault("behavior_weights", {
            "exploration": 1.0,
            "verbosity": 1.0,
            "directness": 1.0
        })

        current_verbosity: float = behavior_weights.get("verbosity", 1.0)

        # Shift verbosity based on momentum
        # If momentum is high (rapid interactions, e.g. speed > 10), user might prefer brevity (lower verbosity)
        # If momentum is low (slow, thoughtful), user might prefer detail (higher verbosity)

        verbosity_shift: float = 0.0
        if momentum_score > 15.0:
            # High momentum, decrease verbosity
            verbosity_shift = -0.1
        elif momentum_score < 5.0:
            # Low momentum, increase verbosity
            verbosity_shift = 0.1

        new_verbosity: float = max(0.5, min(2.0, current_verbosity + verbosity_shift))

        if verbosity_shift != 0.0:
            behavior_weights["verbosity"] = new_verbosity
            model_data["behavior_weights"] = behavior_weights
            self.user_model.save_model(user_id, model_data)
            logging.info(
                f"MomentumTracker: Updated user {user_id} verbosity to {new_verbosity:.2f} "
                f"(shift={verbosity_shift:.2f}, momentum={momentum_score:.2f})"
            )

        # Update state
        self.user_states[user_id] = {
            "last_timestamp": now,
            "last_depth": depth
        }
