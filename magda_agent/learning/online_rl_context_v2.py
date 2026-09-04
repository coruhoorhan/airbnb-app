"""
OpenClaw Context Engine Online RL Implementation V2.

Inspired by OpenClaw-RL online learning trends: Implements online reinforcement
learning from user feedback to dynamically adjust context retrieval weights (such
as recency, semantic similarity, importance, and tag relevance) to continuously
optimize memory retrieval accuracy and relevance.
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
class FeedbackSignal:
    """Represents a feedback signal derived from explicit ratings or implicit user replies."""

    signal_id: str = field(default_factory=lambda: f"sig_{uuid.uuid4().hex[:8]}")
    user_reply: str = ""
    reward_score: float = 0.0  # -1.0 to 1.0
    is_explicit: bool = False
    retrieved_entry_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContextWeightProfile:
    """Dynamic weight profile applied by the context retrieval engine."""

    recency: float = 1.0
    semantic_similarity: float = 1.5
    tag_overlap: float = 1.0
    importance: float = 1.2
    emotional_affinity: float = 0.8
    total_updates: int = 0
    cumulative_reward: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "recency": self.recency,
            "semantic_similarity": self.semantic_similarity,
            "tag_overlap": self.tag_overlap,
            "importance": self.importance,
            "emotional_affinity": self.emotional_affinity,
            "total_updates": self.total_updates,
            "cumulative_reward": self.cumulative_reward,
        }

    def get_feature_vector(self) -> Dict[str, float]:
        return {
            "recency": self.recency,
            "semantic_similarity": self.semantic_similarity,
            "tag_overlap": self.tag_overlap,
            "importance": self.importance,
            "emotional_affinity": self.emotional_affinity,
        }


class OnlineRLContextEngineV2:
    """
    OpenClaw Online Reinforcement Learning Context Engine V2.

    Learns optimal context ranking and retrieval weights online from user dialogue
    and execution feedback.
    """

    POSITIVE_PATTERNS = [
        re.compile(r"\b(great|awesome|excellent|perfect|correct|good job|thank you|thanks|helpful|exactly)\b", re.IGNORECASE),
        re.compile(r"\b(works|worked|fixed|verified|passed|nice)\b", re.IGNORECASE),
        re.compile(r"\b(\+1|👍|🚀|⭐)\b"),
    ]

    NEGATIVE_PATTERNS = [
        re.compile(r"\b(wrong|incorrect|bad|failed|broken|error|irrelevant|forgot|useless|stop|no)\b", re.IGNORECASE),
        re.compile(r"\b(not what i asked|misunderstood|hallucinat|confused)\b", re.IGNORECASE),
        re.compile(r"\b(-1|👎|❌)\b"),
    ]

    def __init__(
        self,
        learning_rate: float = 0.1,
        weight_min: float = 0.1,
        weight_max: float = 5.0,
        baseline_weights: Optional[Dict[str, float]] = None,
    ):
        self.learning_rate = max(0.001, learning_rate)
        self.weight_min = weight_min
        self.weight_max = weight_max

        init_weights = baseline_weights or {}
        self.profile = ContextWeightProfile(
            recency=float(init_weights.get("recency", 1.0)),
            semantic_similarity=float(init_weights.get("semantic_similarity", 1.5)),
            tag_overlap=float(init_weights.get("tag_overlap", 1.0)),
            importance=float(init_weights.get("importance", 1.2)),
            emotional_affinity=float(init_weights.get("emotional_affinity", 0.8)),
        )

        self._feedback_history: List[FeedbackSignal] = []

    def parse_feedback_sentiment(self, text: str) -> float:
        """Derive a scalar reward score (-1.0 to 1.0) from user reply text."""
        if not text:
            return 0.0

        pos_count = sum(len(p.findall(text)) for p in self.POSITIVE_PATTERNS)
        neg_count = sum(len(p.findall(text)) for p in self.NEGATIVE_PATTERNS)

        if pos_count == 0 and neg_count == 0:
            return 0.0

        score = (pos_count - neg_count) / max(1.0, float(pos_count + neg_count))
        return max(-1.0, min(1.0, score))

    def score_entry(
        self,
        entry: Dict[str, Any],
        query_context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Compute weighted retrieval score for a context/memory entry.
        """
        qc = query_context or {}

        # Extract features (normalized 0.0 to 1.0)
        recency_val = float(entry.get("recency_score", entry.get("recency", 0.5)))
        semantic_val = float(entry.get("semantic_similarity", entry.get("similarity", 0.5)))
        tag_val = float(entry.get("tag_overlap", entry.get("tag_score", 0.5)))
        importance_val = float(entry.get("importance", 0.5))
        emotional_val = float(entry.get("emotional_affinity", 0.5))

        # Dot product with active weights
        score = (
            self.profile.recency * recency_val
            + self.profile.semantic_similarity * semantic_val
            + self.profile.tag_overlap * tag_val
            + self.profile.importance * importance_val
            + self.profile.emotional_affinity * emotional_val
        )
        return round(score, 4)

    def rank_context_entries(
        self,
        entries: List[Dict[str, Any]],
        query_context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rank and sort candidate context entries according to current RL weight profile.
        """
        scored = []
        for e in entries:
            sc = self.score_entry(e, query_context)
            item_copy = dict(e)
            item_copy["_rl_retrieval_score"] = sc
            scored.append((sc, item_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def update_weights_from_feedback(
        self,
        user_feedback: str,
        retrieved_entries: Optional[List[Dict[str, Any]]] = None,
        explicit_reward: Optional[float] = None,
    ) -> Tuple[ContextWeightProfile, float]:
        """
        Execute an online policy update step based on user feedback.

        Applies reward-weighted gradient descent update to feature weights.
        """
        reward = explicit_reward if explicit_reward is not None else self.parse_feedback_sentiment(user_feedback)
        entries = retrieved_entries or []

        entry_ids = [str(e.get("id") or e.get("chunk_id") or "") for e in entries]
        signal = FeedbackSignal(
            user_reply=user_feedback,
            reward_score=reward,
            is_explicit=explicit_reward is not None,
            retrieved_entry_ids=entry_ids,
            timestamp=time.time(),
        )
        self._feedback_history.append(signal)

        if abs(reward) < 0.001:
            return self.profile, reward

        # Compute average feature values for retrieved items
        if entries:
            avg_recency = sum(float(e.get("recency_score", 0.5)) for e in entries) / len(entries)
            avg_semantic = sum(float(e.get("semantic_similarity", 0.5)) for e in entries) / len(entries)
            avg_tag = sum(float(e.get("tag_overlap", 0.5)) for e in entries) / len(entries)
            avg_importance = sum(float(e.get("importance", 0.5)) for e in entries) / len(entries)
            avg_emotional = sum(float(e.get("emotional_affinity", 0.5)) for e in entries) / len(entries)
        else:
            avg_recency = avg_semantic = avg_tag = avg_importance = avg_emotional = 0.5

        # Online Policy Gradient update
        # delta = lr * reward * feature_contribution
        self.profile.recency = self._apply_update(self.profile.recency, reward, avg_recency)
        self.profile.semantic_similarity = self._apply_update(self.profile.semantic_similarity, reward, avg_semantic)
        self.profile.tag_overlap = self._apply_update(self.profile.tag_overlap, reward, avg_tag)
        self.profile.importance = self._apply_update(self.profile.importance, reward, avg_importance)
        self.profile.emotional_affinity = self._apply_update(self.profile.emotional_affinity, reward, avg_emotional)

        self.profile.total_updates += 1
        self.profile.cumulative_reward += reward

        logger.info(
            f"Online RL weight update applied (reward={reward:.2f}). "
            f"New weights: {self.profile.get_feature_vector()}"
        )
        return self.profile, reward

    def _apply_update(self, current_weight: float, reward: float, feature_val: float) -> float:
        """Calculate single weight update and clamp within bounds."""
        delta = self.learning_rate * reward * feature_val
        new_val = current_weight + delta
        return max(self.weight_min, min(self.weight_max, round(new_val, 4)))

    async def update_weights_from_feedback_async(
        self,
        user_feedback: str,
        retrieved_entries: Optional[List[Dict[str, Any]]] = None,
        explicit_reward: Optional[float] = None,
    ) -> Tuple[ContextWeightProfile, float]:
        """Async wrapper for online weight update."""
        return self.update_weights_from_feedback(user_feedback, retrieved_entries, explicit_reward)

    def get_weights(self) -> Dict[str, float]:
        """Return active feature weights."""
        return self.profile.get_feature_vector()

    def get_learning_metrics(self) -> Dict[str, Any]:
        """Return metrics and telemetry on online RL training progress."""
        avg_reward = (
            self.profile.cumulative_reward / self.profile.total_updates
            if self.profile.total_updates > 0
            else 0.0
        )
        return {
            "total_updates": self.profile.total_updates,
            "cumulative_reward": round(self.profile.cumulative_reward, 4),
            "average_reward_per_step": round(avg_reward, 4),
            "current_weights": self.get_weights(),
            "total_feedback_signals_received": len(self._feedback_history),
        }
