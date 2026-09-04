"""
OpenClaw-RL Interactive Learning Integration V4.

Inspired by OpenClaw RL trends: Implements an interactive reinforcement learning loop
for continuous skill improvement derived from next-state observation signals, implicit
user sentiment, and multi-step trajectory feedback.
"""

import asyncio
import inspect
import json
import logging
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class InteractiveSignal:
    """Represents an observed interaction signal and resulting reward."""

    signal_id: str = field(default_factory=lambda: f"isig_{uuid.uuid4().hex[:8]}")
    skill_name: str = "default_skill"
    user_reply: str = ""
    next_state_observation: Dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    sentiment: str = "neutral"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkillWeightProfileV4:
    """Maintains dynamically learned weights and statistics for skills."""

    weights: Dict[str, float] = field(default_factory=dict)
    execution_counts: Dict[str, int] = field(default_factory=dict)
    cumulative_rewards: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.15
    discount_factor: float = 0.95
    min_weight: float = 0.05
    max_weight: float = 5.0
    total_steps: int = 0

    def get_weight(self, skill_name: str, default: float = 1.0) -> float:
        return self.weights.get(skill_name, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "execution_counts": self.execution_counts,
            "cumulative_rewards": {k: round(v, 4) for k, v in self.cumulative_rewards.items()},
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
            "total_steps": self.total_steps,
        }


class OpenClawInteractiveRLV4:
    """
    OpenClaw-RL Interactive Learning Engine V4.

    Evaluates user replies as next-state reward signals to adjust skill weights,
    optimizing future tool selection probabilities.
    """

    POSITIVE_WORDS = {
        "good", "great", "excellent", "awesome", "perfect", "thanks", "thank you",
        "verified", "works", "passed", "fixed", "accurate", "nice", "helpful", "yes",
    }

    NEGATIVE_WORDS = {
        "bad", "wrong", "broken", "failed", "terrible", "awful", "error", "no",
        "stop", "cancel", "useless", "irrelevant", "incorrect", "buggy", "halt",
    }

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        learning_rate: float = 0.15,
        discount_factor: float = 0.95,
        min_weight: float = 0.05,
        max_weight: float = 5.0,
        initial_weights: Optional[Dict[str, float]] = None,
    ):
        self.llm_client = llm_client
        self.profile = SkillWeightProfileV4(
            weights=dict(initial_weights or {}),
            learning_rate=learning_rate,
            discount_factor=discount_factor,
            min_weight=min_weight,
            max_weight=max_weight,
        )
        self._history: List[InteractiveSignal] = []

    async def analyze_signal_async(
        self,
        user_reply: str,
        next_state_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, str]:
        """
        Analyze user reply using LLM (if available) or fast heuristics to derive reward and sentiment.
        """
        if not user_reply or not user_reply.strip():
            return 0.0, "neutral"

        if self.llm_client:
            prompt = (
                f"You are an RL reward evaluator analyzing user feedback.\n"
                f"User reply: \"{user_reply}\"\n"
                f"Context: {json.dumps(next_state_context or {})}\n"
                "Score the user's sentiment as a JSON object: {\"reward\": float (-1.0 to 1.0), \"sentiment\": \"positive\" | \"neutral\" | \"negative\"}"
            )
            try:
                if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                    resp = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "generate"):
                    resp = self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                    resp = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                else:
                    resp = ""

                match = re.search(r"\{.*\}", resp, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    raw_reward = float(data.get("reward", 0.0))
                    sentiment = str(data.get("sentiment", "neutral"))
                    return max(-1.0, min(1.0, raw_reward)), sentiment
            except Exception as ex:
                logger.warning(f"LLM signal analysis error: {ex}. Using heuristic.")

        # Heuristic fallback
        reply_lower = user_reply.lower()
        words = set(re.findall(r"\b\w+\b", reply_lower))

        pos_count = len(words & self.POSITIVE_WORDS)
        neg_count = len(words & self.NEGATIVE_WORDS)

        if pos_count > neg_count:
            reward = min(1.0, 0.4 + (pos_count * 0.2))
            return reward, "positive"
        elif neg_count > pos_count:
            reward = max(-1.0, -0.4 - (neg_count * 0.2))
            return reward, "negative"

        return 0.0, "neutral"

    def analyze_signal_sync(
        self,
        user_reply: str,
        next_state_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, str]:
        """Synchronous wrapper for signal analysis."""
        return asyncio.run(self.analyze_signal_async(user_reply, next_state_context))

    async def process_interaction_async(
        self,
        skill_name: str,
        user_reply: str,
        next_state_context: Optional[Dict[str, Any]] = None,
        explicit_reward: Optional[float] = None,
    ) -> float:
        """
        Process a single interaction and update the skill weight based on the reward.
        """
        if explicit_reward is not None:
            reward = max(-1.0, min(1.0, float(explicit_reward)))
            sentiment = "positive" if reward > 0 else ("negative" if reward < 0 else "neutral")
        else:
            reward, sentiment = await self.analyze_signal_async(user_reply, next_state_context)

        current_weight = self.profile.weights.get(skill_name, 1.0)
        delta = self.profile.learning_rate * reward
        new_weight = current_weight + delta
        new_weight = max(self.profile.min_weight, min(self.profile.max_weight, round(new_weight, 4)))

        self.profile.weights[skill_name] = new_weight
        self.profile.execution_counts[skill_name] = self.profile.execution_counts.get(skill_name, 0) + 1
        self.profile.cumulative_rewards[skill_name] = self.profile.cumulative_rewards.get(skill_name, 0.0) + reward
        self.profile.total_steps += 1

        sig = InteractiveSignal(
            skill_name=skill_name,
            user_reply=user_reply,
            next_state_observation=next_state_context or {},
            reward=reward,
            sentiment=sentiment,
        )
        self._history.append(sig)

        logger.info(
            f"Interactive RL update: skill='{skill_name}', reward={reward:.2f}, "
            f"old_weight={current_weight:.3f}, new_weight={new_weight:.3f}"
        )
        return reward

    def process_interaction(
        self,
        skill_name: str,
        user_reply: str,
        next_state_context: Optional[Dict[str, Any]] = None,
        explicit_reward: Optional[float] = None,
    ) -> float:
        """Synchronous wrapper for single interaction processing."""
        return asyncio.run(self.process_interaction_async(
            skill_name=skill_name,
            user_reply=user_reply,
            next_state_context=next_state_context,
            explicit_reward=explicit_reward,
        ))

    async def process_trajectory_batch_async(
        self,
        trajectory: List[Tuple[str, str]],
    ) -> Dict[str, float]:
        """
        Process a multi-step trajectory with discounted reward propagation backwards.
        trajectory: List of (skill_name, user_reply) tuples.
        """
        rewards = {}
        gamma = self.profile.discount_factor
        running_reward = 0.0

        for skill_name, user_reply in reversed(trajectory):
            step_reward, _ = await self.analyze_signal_async(user_reply)
            running_reward = step_reward + (gamma * running_reward)
            await self.process_interaction_async(
                skill_name=skill_name,
                user_reply=user_reply,
                explicit_reward=running_reward,
            )
            rewards[skill_name] = running_reward

        return rewards

    def get_skill_weight(self, skill_name: str) -> float:
        """Return current weight of a given skill."""
        return self.profile.get_weight(skill_name)

    def rank_skills(self, candidate_skills: List[str]) -> List[Tuple[str, float]]:
        """Rank candidate skills by their learned weights descending."""
        scored = [(s, self.get_skill_weight(s)) for s in candidate_skills]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def get_learning_stats(self) -> Dict[str, Any]:
        """Return comprehensive learning state statistics."""
        return self.profile.to_dict()
