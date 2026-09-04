import logging
from typing import Optional, Dict

class OpenClawRLNextStatePipelineV9:
    """
    OpenClaw-RL Next-State Feedback Processing V9 pipeline.
    Parses next-state interaction signals directly from user text for real-time model tuning.
    """
    def __init__(self) -> None:
        pass

    def parse_text_signal(self, text: str) -> float:
        """
        Parses the text signal and returns a reward value.
        A very simple heuristic for now.

        Args:
            text (str): The user's text reply.

        Returns:
            float: A calculated reward signal between -1.0 and 1.0.
        """
        text_lower = text.lower()
        if any(word in text_lower for word in ["great", "awesome", "good", "thanks", "perfect", "yes"]):
            return 1.0
        if any(word in text_lower for word in ["bad", "terrible", "wrong", "no", "stop", "fail"]):
            return -1.0
        return 0.0

    def calculate_reward(self, user_reply: str, tool_output: Optional[str] = None) -> float:
        """
        Calculates the overall reward from the user reply and tool output.

        Args:
            user_reply (str): The user's text reply.
            tool_output (Optional[str], optional): The output from the tool.

        Returns:
            float: The calculated reward.
        """
        base_reward = self.parse_text_signal(user_reply)

        if tool_output:
            if "error" in tool_output.lower() or "exception" in tool_output.lower():
                base_reward -= 0.5
            elif "success" in tool_output.lower():
                base_reward += 0.5

        return max(-1.0, min(1.0, base_reward))
