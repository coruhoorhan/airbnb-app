import logging
from typing import Any, Dict, List, Optional
from magda_agent.emotions.mirror_neurons import MirrorNeurons

logger = logging.getLogger(__name__)

class OpenClawOnlineLearningV8:
    """
    OpenClaw Online Learning Module v8.
    Implements continuous online reinforcement learning from user feedback during dialogue interactions.
    Updates skill weights based on explicit/implicit feedback, leveraging MirrorNeurons for sentiment extraction.
    """

    def __init__(
        self,
        initial_weights: Optional[Dict[str, float]] = None,
        mirror_neurons: Optional[MirrorNeurons] = None,
        learning_rate: float = 0.1,
        min_weight: float = 0.1,
        max_weight: float = 2.0
    ) -> None:
        """
        Initializes the OpenClawOnlineLearningV8 module.

        Args:
            initial_weights (Optional[Dict[str, float]]): Initial weights for skills.
            mirror_neurons (Optional[MirrorNeurons]): MirrorNeurons instance for emotional shift detection.
            learning_rate (float): The step size (alpha) for updating weights.
            min_weight (float): Minimum allowable weight for any skill.
            max_weight (float): Maximum allowable weight for any skill.
        """
        self.skill_weights: Dict[str, float] = initial_weights or {}
        self.mirror_neurons = mirror_neurons or MirrorNeurons()
        self.learning_rate = learning_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.trajectory_history: List[Dict[str, Any]] = []
        logger.info("OpenClawOnlineLearningV8 initialized successfully.")

    def extract_reward(self, user_reply: str, tool_output: Optional[str] = None) -> float:
        """
        Extracts a reward signal (-1.0 to 1.0) from conversational next-state signals.
        Combines MirrorNeurons' empathy shift with explicit keyword matching.

        Args:
            user_reply (str): The text of the user's response.
            tool_output (Optional[str]): Optional output from the tool execution.

        Returns:
            float: A reward score between -1.0 and 1.0.
        """
        if not user_reply:
            return 0.0

        # Combine dialogue context
        full_text = user_reply
        if tool_output:
            full_text += f" {tool_output}"

        # 1. Get sentiment shift from MirrorNeurons
        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(full_text)

        # 2. Heuristic word-based overrides to complement MirrorNeurons
        words = full_text.lower().replace(".", "").replace(",", "").replace("!", "").replace("?", "").split()

        # Positive indicators
        pos_words = {"good", "great", "excellent", "thanks", "thank", "awesome", "perfect", "correct", "yes", "success"}
        # Negative indicators
        neg_words = {"bad", "wrong", "terrible", "fail", "failure", "error", "no", "incorrect", "bug", "stop"}

        pos_matches = sum(1 for w in words if w in pos_words)
        neg_matches = sum(1 for w in words if w in neg_words)

        # Basic sentiment heuristic combined with MirrorNeurons
        reward = p_shift

        if pos_matches > neg_matches:
            reward = max(reward, 0.5)
            if "excellent" in words or "perfect" in words:
                reward = 1.0
        elif neg_matches > pos_matches:
            reward = min(reward, -0.5)
            if "terrible" in words or "fail" in words or "bug" in words:
                reward = -1.0

        # Clamp reward to safe range
        return max(-1.0, min(1.0, reward))

    def update_weight(self, skill_id: str, reward: float) -> float:
        """
        Updates the weight of a skill using the reinforcement update rule:
        W_new = W_old + learning_rate * (reward)
        and clamps the weight between min_weight and max_weight.

        Args:
            skill_id (str): The identifier of the skill.
            reward (float): The reward signal (-1.0 to 1.0).

        Returns:
            float: The updated weight of the skill.
        """
        current_weight = self.skill_weights.get(skill_id, 1.0)

        # Update rule: adjust weight based on the reward received
        new_weight = current_weight + self.learning_rate * reward
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))

        self.skill_weights[skill_id] = new_weight
        logger.info(f"Updated skill weight for '{skill_id}': {current_weight:.2f} -> {new_weight:.2f} (Reward: {reward})")
        return new_weight

    def process_feedback(self, skill_id: str, user_reply: str, tool_output: Optional[str] = None) -> float:
        """
        Processes conversational feedback synchronously, extracting the reward and updating the skill weight.

        Args:
            skill_id (str): The skill being evaluated.
            user_reply (str): The text of the user's reply.
            tool_output (Optional[str]): The optional output of the tool.

        Returns:
            float: The updated weight of the skill.
        """
        reward = self.extract_reward(user_reply, tool_output)

        # Log trajectory step
        self.trajectory_history.append({
            "skill_id": skill_id,
            "user_reply": user_reply,
            "tool_output": tool_output,
            "reward": reward
        })

        return self.update_weight(skill_id, reward)

    async def process_feedback_async(self, skill_id: str, user_reply: str, tool_output: Optional[str] = None) -> float:
        """
        Processes conversational feedback asynchronously. Useful for integration with async pipelines.

        Args:
            skill_id (str): The skill being evaluated.
            user_reply (str): The text of the user's reply.
            tool_output (Optional[str]): The optional output of the tool.

        Returns:
            float: The updated weight of the skill.
        """
        # In this base v8 implementation, we perform the same logic asynchronously
        return self.process_feedback(skill_id, user_reply, tool_output)

    def get_skill_weight(self, skill_id: str) -> float:
        """
        Retrieves the weight of a skill, defaulting to 1.0 if not yet set.

        Args:
            skill_id (str): The skill identifier.

        Returns:
            float: The skill's current weight.
        """
        return self.skill_weights.get(skill_id, 1.0)

    def get_all_weights(self) -> Dict[str, float]:
        """
        Retrieves a copy of all current skill weights.

        Returns:
            Dict[str, float]: All skill weights.
        """
        return self.skill_weights.copy()
