import logging
from typing import Optional, List, Dict, Any

from magda_agent.learning.habits import HabitTracker
from magda_agent.emotions.mirror_neurons import MirrorNeurons
from magda_agent.user_model.model import UserModel

class OpenClawInteractiveLearnerV7:
    """
    OpenClaw-RL Interactive Learner v7.
    Processes multi-turn conversation traces to evaluate delayed implicit feedback via PAD shifts
    and updates skill weights and user model preferences.
    """

    def __init__(
        self,
        habit_tracker: HabitTracker,
        mirror_neurons: MirrorNeurons,
        user_model: UserModel,
    ) -> None:
        """
        Initializes the learner with habit tracker, mirror neurons, and user model dependencies.
        """
        self.habit_tracker = habit_tracker
        self.mirror_neurons = mirror_neurons
        self.user_model = user_model

    async def process_conversation_trace(
        self,
        trace: List[Dict[str, Any]],
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Processes a multi-turn conversation trace and identifies PAD shifts to compute delayed implicit rewards.

        Args:
            trace (List[Dict[str, Any]]): List of turn dicts containing conversation signals (e.g., user_reply, action_context, skills_used, tool_output).
            user_id (int): User identifier.

        Returns:
            Dict[str, Any]: A summary of the trace processing results including cumulative PAD shifts, total reward, and updated skills.
        """
        if not trace:
            return {"reward": 0.0, "total_turns": 0, "pad_shifts": (0.0, 0.0, 0.0)}

        total_p = 0.0
        total_a = 0.0
        total_d = 0.0
        all_skills: List[str] = []
        action_contexts: List[str] = []

        for turn in trace:
            user_reply = turn.get("user_reply", "") or turn.get("user_message", "")
            action_ctx = turn.get("action_context", "") or turn.get("input_text", "")
            tool_output = turn.get("tool_output", "")
            skills = turn.get("skills_used", []) or turn.get("skills", [])

            if action_ctx:
                action_contexts.append(action_ctx)

            for s in skills:
                if s not in all_skills:
                    all_skills.append(s)

            signal_text = user_reply
            if tool_output:
                signal_text += f" [Tool Output: {tool_output}]"

            if signal_text:
                p_shift, a_shift, d_shift = self.mirror_neurons.empathize(signal_text)
                total_p += p_shift
                total_a += a_shift
                total_d += d_shift

        num_turns = len(trace)
        avg_p = total_p / num_turns

        # Calculate delayed implicit reward (scale from 0.0 to 10.0)
        base_reward = (avg_p + 1.0) * 5.0
        # Give bonus for positive pleasure trend over turns
        if total_p > 0.0:
            base_reward += min(2.0, total_p * 2.0)

        delayed_reward = max(0.0, min(10.0, base_reward))

        # Retrieve and update user model
        model_data = self.user_model.get_model(user_id)
        if "rl_v7_trace_metrics" not in model_data:
            model_data["rl_v7_trace_metrics"] = []

        model_data["rl_v7_trace_metrics"].append({
            "reward": delayed_reward,
            "turns": num_turns,
            "avg_p_shift": avg_p,
        })

        if delayed_reward >= 5.0:
            for skill in all_skills:
                ctx_summary = " -> ".join(action_contexts) if action_contexts else "trace_context"
                self.habit_tracker.record_usage(
                    input_text=ctx_summary,
                    skill_used=skill,
                    evaluation_score=delayed_reward,
                    user_id=user_id,
                )
            logging.info(
                f"OpenClawRLV7: Positive delayed trace feedback (reward={delayed_reward:.2f}). "
                f"Reinforced skills: {all_skills}"
            )
            model_data["communication_style"] = f"{model_data.get('communication_style', 'default')} (trace_validated)"
        else:
            logging.info(f"OpenClawRLV7: Low/Negative trace feedback (reward={delayed_reward:.2f}).")
            model_data["communication_style"] = f"{model_data.get('communication_style', 'default')} (trace_cautious)"

        self.user_model.save_model(user_id, model_data)

        return {
            "reward": delayed_reward,
            "total_turns": num_turns,
            "pad_shifts": (total_p, total_a, total_d),
            "skills_updated": all_skills if delayed_reward >= 5.0 else [],
        }
