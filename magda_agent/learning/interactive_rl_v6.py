import logging
import re
from typing import Optional
from magda_agent.learning.habits import HabitTracker

class InteractiveRLLoopV6:
    """
    OpenClaw-inspired Interactive Reinforcement Learning Loop V6.

    This module analyzes explicit user replies (next-state signals) and
    translates them into an evaluation score, which is then fed into
    the HabitTracker to dynamically adjust behavior weights.
    """

    def __init__(self, habit_tracker: HabitTracker) -> None:
        """
        Initializes the InteractiveRLLoopV6 with a HabitTracker instance.

        Args:
            habit_tracker (HabitTracker): The habit tracker instance to record successful skill usages.
        """
        self.habit_tracker = habit_tracker
        logging.info("Initialized InteractiveRLLoopV6 with HabitTracker")

    def analyze_feedback(self, reply: str) -> float:
        """
        Analyzes a user's reply to determine a heuristic evaluation score.

        Args:
            reply (str): The user's text reply.

        Returns:
            float: An evaluation score between 0.0 and 10.0.
        """
        reply_lower = reply.lower()

        # Simple heuristic for negative sentiment
        negative_words = [r"\bno\b", r"\bwrong\b", r"\bbad\b", r"\bincorrect\b", r"\bterrible\b", r"\bstop\b", r"\bfail\b"]
        if any(re.search(word, reply_lower) for word in negative_words):
            return 2.0

        # Simple heuristic for positive sentiment
        positive_words = [r"\bthanks\b", r"\bthank you\b", r"\bgreat\b", r"\bawesome\b", r"\bperfect\b", r"\bgood\b", r"\bcorrect\b", r"\byes\b"]
        if any(re.search(word, reply_lower) for word in positive_words):
            return 9.0

        # Default neutral score
        return 5.0

    def process_interaction(self, input_text: str, skill_used: str, user_reply: str, user_id: Optional[int] = None) -> None:
        """
        Processes a full interaction cycle by analyzing the user's reply and
        recording the skill usage if it was successful.

        Args:
            input_text (str): The original user input that triggered the skill.
            skill_used (str): The name of the skill that was executed.
            user_reply (str): The subsequent reply from the user evaluating the response.
            user_id (Optional[int]): The ID of the user. Defaults to None.
        """
        score = self.analyze_feedback(user_reply)
        logging.info(f"Analyzed user reply '{user_reply[:20]}...' -> Score: {score}")

        # We pass the calculated score to the HabitTracker.
        # The HabitTracker itself contains logic (e.g., score >= 8.0) to decide
        # whether to form a habit from this interaction.
        self.habit_tracker.record_usage(
            input_text=input_text,
            skill_used=skill_used,
            evaluation_score=score,
            user_id=user_id
        )
