import logging
from typing import Optional, List

from magda_agent.learning.habits import HabitTracker
from magda_agent.emotions.mirror_neurons import MirrorNeurons
from magda_agent.learning.rl_tuner_v5 import OnlineRLParameterTunerV5

class OpenClawRLV6:
    """
    OpenClaw-RL Online Reinforcement Learning V6.
    Implements online learning from next-state signals (such as user replies
    and tool outputs) without explicit labeling. The agent learns from talking.
    """

    def __init__(
        self,
        habit_tracker: HabitTracker,
        mirror_neurons: MirrorNeurons,
    ) -> None:
        """
        Initializes the learner with its dependencies.

        Args:
            habit_tracker: The system for tracking habit/skill usage.
            mirror_neurons: The sentiment and empathy processor for implicit feedback.
        """
        self.habit_tracker = habit_tracker
        self.mirror_neurons = mirror_neurons
        self.parameter_tuner = OnlineRLParameterTunerV5()

    def _calculate_reward(self, p_shift: float, tool_output: Optional[str]) -> float:
        """
        Calculates the reward score based on empathy shift and tool output.

        Args:
            p_shift: The positive shift in empathy.
            tool_output: The output from the executed tool.

        Returns:
            A calculated reward float between 0.0 and 10.0.
        """
        # Base reward transformation
        base_reward = (p_shift + 1.0) * 5.0

        # Give bonus if there's a valid tool output and positive empathy shift
        if tool_output and p_shift > 0.0:
            base_reward += 2.0

        return max(0.0, min(10.0, base_reward))

    async def process_next_state_signal(
        self,
        user_reply: str,
        action_context: str,
        user_id: int,
        tool_output: Optional[str] = None,
        skills_used: Optional[List[str]] = None,
    ) -> None:
        """
        Analyzes the user's reply as a next-state signal, and reinforces habits.

        Args:
            user_reply (str): The user's reply string.
            action_context (str): A description of the action taken.
            user_id (int): The ID of the current user.
            tool_output (Optional[str], optional): The output from the executed tool. Defaults to None.
            skills_used (Optional[List[str]], optional): A list of skill names used. Defaults to None.
        """
        if not user_reply or not action_context:
            return

        signal_text = user_reply
        if tool_output:
            signal_text += f" [Tool Output: {tool_output}]"

        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(signal_text)

        skills = skills_used or ["rl_skill_v6"]

        reward = self._calculate_reward(p_shift, tool_output)

        uncertainty = abs(a_shift)
        metrics = {'reward': reward, 'uncertainty': uncertainty}
        tuned_lr = self.parameter_tuner.tune_learning_rate(metrics)

        # Apply tuned_lr to scale the reward instead of only logging it.
        # It's an online RL param tuner, so we scale it explicitly.
        adjusted_reward = reward * (1.0 + tuned_lr)
        adjusted_reward = max(0.0, min(10.0, adjusted_reward))

        logging.debug(f"OpenClawRLV6: Tuned learning rate is {tuned_lr:.4f} for metrics {metrics}. Adjusted reward: {adjusted_reward:.2f}")

        if reward > 5.0:
            # Positive signal, reinforce habits
            for skill in skills:
                self.habit_tracker.record_usage(
                    input_text=action_context,
                    skill_used=skill,
                    evaluation_score=adjusted_reward,
                    user_id=user_id
                )
            logging.info(f"OpenClawRLV6: Positive signal received (reward={adjusted_reward:.2f}). Reinforced skills: {skills}")
        else:
            # Negative or low neutral signal
            logging.info(f"OpenClawRLV6: Low/Negative signal (reward={adjusted_reward:.2f}). No usage recorded.")
