import re
import threading
import logging
from typing import Optional, Dict

class OpenClawRewardHeuristicV1:
    """
    OpenClaw-RL Interactive Reward Heuristic module.
    Parses explicit user rating commands (e.g. '/rate 5') inside message content
    and maps them thread-safely to update procedural habit weights.
    """

    def __init__(self) -> None:
        """
        Initializes the reward heuristic module.
        """
        self.weights: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.pattern = re.compile(r'/rate\s+(-?\d+(?:\.\d+)?)')
        logging.info("Initialized OpenClawRewardHeuristicV1")

    def parse_rating(self, text: str) -> Optional[float]:
        """
        Parses a '/rate X' command from the text and normalizes it to [-1.0, 1.0].
        Assumes a standard 1 to 5 rating scale.

        Args:
            text (str): The user's input text.

        Returns:
            Optional[float]: The normalized reward, or None if no valid rating found.
        """
        match = self.pattern.search(text)
        if match:
            try:
                rating = float(match.group(1))
                # Normalize assuming a 1-5 scale by default.
                # 1 -> -1.0, 3 -> 0.0, 5 -> 1.0
                normalized = (rating - 3.0) / 2.0
                return max(-1.0, min(1.0, normalized))
            except ValueError:
                return None
        return None

    def apply_reward(self, skill_id: str, reward: float) -> float:
        """
        Thread-safely applies a reward to the habit weight of a skill.

        Args:
            skill_id (str): The identifier of the skill.
            reward (float): The normalized reward to apply.

        Returns:
            float: The updated weight for the skill.
        """
        with self._lock:
            current_weight = self.weights.get(skill_id, 0.0)
            new_weight = current_weight + reward
            self.weights[skill_id] = new_weight
            logging.debug(f"OpenClawRewardHeuristicV1: Updated weight for {skill_id} to {new_weight:.4f} (reward: {reward:.4f})")
            return new_weight

    def process_user_reply(self, text: str, skill_id: str) -> Optional[float]:
        """
        Parses a rating from the user's text and applies it to the skill if found.

        Args:
            text (str): The user's input text.
            skill_id (str): The identifier of the skill.

        Returns:
            Optional[float]: The updated weight for the skill, or None if no rating found.
        """
        reward = self.parse_rating(text)
        if reward is not None:
            return self.apply_reward(skill_id, reward)
        return None
