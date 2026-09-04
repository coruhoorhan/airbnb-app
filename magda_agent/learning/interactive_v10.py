import logging
from typing import Optional, Dict, Any, List
from magda_agent.emotions.mirror_neurons import MirrorNeurons
from magda_agent.user_model.model import UserModel

class InteractiveLearnerV10:
    """
    OpenClaw-inspired online learning interactions v10.
    Adjusts agent responses and user model parameters based on continuous interaction feedback.
    """
    def __init__(
        self,
        mirror_neurons: MirrorNeurons,
        user_model: UserModel
    ) -> None:
        """
        Initializes the InteractiveLearnerV10.

        Args:
            mirror_neurons (MirrorNeurons): The module to empathize with the user's input.
            user_model (UserModel): The persistent user model storage.
        """
        self.mirror_neurons = mirror_neurons
        self.user_model = user_model

    async def process_interaction(
        self,
        user_reply: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Processes a user reply, infers emotional state, and updates the user model dynamically.

        Args:
            user_reply (str): The continuous interaction feedback from the user.
            user_id (Optional[str], optional): The user's ID. Defaults to None.
        """
        if not user_reply:
            return

        # Empathize with the reply to get Pleasure, Arousal, Dominance shifts
        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(user_reply)
        model_data: Dict[str, Any] = self.user_model.get_model(user_id)

        # Update interaction history weight dynamically
        if "interactions" not in model_data:
            model_data["interactions"] = {}

        model_data["interactions"]["last_p_shift"] = p_shift
        model_data["interactions"]["last_a_shift"] = a_shift
        model_data["interactions"]["last_d_shift"] = d_shift

        # Dynamic Behavior Adjustment based on implicit emotional shifts
        behavior_weights = model_data.setdefault("interaction_weights", {
            "exploration": 1.0,
            "verbosity": 1.0,
            "directness": 1.0,
            "empathy": 1.0
        })

        if p_shift > 0.0:
            logging.info(f"InteractiveLearnerV10: Positive feedback (p={p_shift:.2f}). Increasing exploration.")
            behavior_weights["exploration"] = min(2.0, behavior_weights["exploration"] + p_shift * 0.3)
            # Adjust communication style towards friendly if positive
            if "(friendly)" not in model_data.get("interaction_style", ""):
                model_data["interaction_style"] = f"{model_data.get('interaction_style', 'default')} (friendly)"
        elif p_shift < 0.0:
            logging.info(f"InteractiveLearnerV10: Negative feedback (p={p_shift:.2f}). Decreasing exploration.")
            behavior_weights["exploration"] = max(0.5, behavior_weights["exploration"] + p_shift * 0.3)
            # Adjust communication style towards cautious if negative
            if "(cautious)" not in model_data.get("interaction_style", ""):
                model_data["interaction_style"] = f"{model_data.get('interaction_style', 'default')} (cautious)"

        if a_shift > 0.0:
            behavior_weights["verbosity"] = min(2.0, behavior_weights["verbosity"] + a_shift * 0.2)
        elif a_shift < 0.0:
            behavior_weights["verbosity"] = max(0.5, behavior_weights["verbosity"] + a_shift * 0.2)

        if d_shift > 0.0:
            behavior_weights["directness"] = min(2.0, behavior_weights["directness"] + d_shift * 0.2)
        elif d_shift < 0.0:
            behavior_weights["directness"] = max(0.5, behavior_weights["directness"] + d_shift * 0.2)

        # Global empathy adjustments
        behavior_weights["empathy"] = min(2.0, behavior_weights["empathy"] + abs(p_shift) * 0.1)

        model_data["interaction_weights"] = behavior_weights

        # Save the updated user model back to disk
        self.user_model.save_model(user_id, model_data)
        logging.info(f"InteractiveLearnerV10: Updated interaction model for user {user_id}")
