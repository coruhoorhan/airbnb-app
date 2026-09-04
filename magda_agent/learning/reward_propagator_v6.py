"""
OpenClaw-RL Online Reward Propagator v6.

Inspired by OpenClaw-RL implicit feedback trends: Develops an online reinforcement
learning propagator that dynamically traces sub-agent execution paths, assigning
positive or negative PAD feedback signals recursively through the hierarchy of
delegated actions based on user replies.
"""

from collections import defaultdict
import json
import logging
import math
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class PADVector:
    """Pleasure, Arousal, Dominance (PAD) emotional/reward state vector."""

    pleasure: float = 0.0   # -1.0 (unpleasant/failure) to +1.0 (pleasure/success)
    arousal: float = 0.0    # -1.0 (calm/passive) to +1.0 (excited/alert)
    dominance: float = 0.0  # -1.0 (submissive/inhibited) to +1.0 (dominant/in-control)

    def to_scalar_reward(self, weights: Tuple[float, float, float] = (0.7, 0.15, 0.15)) -> float:
        """
        Combines PAD components into a unified scalar reward signal in [-1.0, 1.0].
        Pleasure is the primary driver of positive/negative reinforcement.
        """
        w_p, w_a, w_d = weights
        scalar = (w_p * self.pleasure) + (w_a * self.arousal) + (w_d * self.dominance)
        return max(-1.0, min(1.0, scalar))

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class ExecutionNode:
    """Represents an action node in the hierarchical execution graph."""

    action_id: str
    agent_id: str
    skill_name: str
    role: str = "worker"
    parent_action_id: Optional[str] = None
    children_action_ids: List[str] = field(default_factory=list)
    depth: int = 0
    weight: float = 1.0
    reward_history: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImplicitFeedbackParser:
    """Extracts implicit and explicit sentiment/feedback signals from user replies."""

    POSITIVE_CUES = [
        (re.compile(r"\b(?:great|perfect|awesome|excellent|amazing|brilliant|good job|well done|thank(?:s| you)?)\b", re.IGNORECASE), 0.8, 0.4, 0.3),
        (re.compile(r"\b(?:correct|works|fixed|solved|verified|approved|looks good|lgtm|nice)\b", re.IGNORECASE), 0.7, 0.2, 0.3),
        (re.compile(r"\b(?:yes|helpful|fast|clean|precise|fixed_issue)\b", re.IGNORECASE), 0.5, 0.1, 0.2),
        (re.compile(r"👍|🎉|✅|🚀|❤️|👏"), 0.9, 0.5, 0.4),
    ]

    NEGATIVE_CUES = [
        (re.compile(r"\b(?:wrong|broken|failed|error|bug|crash|horrible|terrible|awful)\b", re.IGNORECASE), -0.8, 0.6, -0.4),
        (re.compile(r"\b(?:incorrect|not working|redo|undo|useless|bad|unhelpful|revert)\b", re.IGNORECASE), -0.7, 0.4, -0.3),
        (re.compile(r"\b(?:no|wait|stop|disapprove|cannot|syntax error)\b", re.IGNORECASE), -0.5, 0.3, -0.2),
        (re.compile(r"👎|❌|🚫|💔|😡|🐛"), -0.9, 0.7, -0.5),
    ]

    EXPLICIT_RATING_PATTERN = re.compile(r"/rate\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE)
    EXPLICIT_REWARD_PATTERN = re.compile(r"/reward\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE)

    @classmethod
    def parse_reply(cls, reply_text: str) -> PADVector:
        """Parses user message and infers appropriate PAD vector."""
        # 1. Check explicit rating / reward command
        rate_match = cls.EXPLICIT_RATING_PATTERN.search(reply_text)
        if rate_match:
            val = float(rate_match.group(1))
            # Normalize 1..5 scale to -1.0 .. 1.0
            norm_p = max(-1.0, min(1.0, (val - 3.0) / 2.0))
            return PADVector(pleasure=norm_p, arousal=abs(norm_p) * 0.5, dominance=norm_p * 0.4)

        reward_match = cls.EXPLICIT_REWARD_PATTERN.search(reply_text)
        if reward_match:
            val = float(reward_match.group(1))
            norm_p = max(-1.0, min(1.0, val))
            return PADVector(pleasure=norm_p, arousal=abs(norm_p) * 0.5, dominance=norm_p * 0.4)

        # 2. Check compound phrases to avoid false negative on "fixed the bug"
        clean_text = re.sub(
            r"\b(?:fixing|fixed|resolved|handled)\s+(?:the\s+)?(?:bug|error|issue|problem)\b",
            "fixed_issue",
            reply_text,
            flags=re.IGNORECASE,
        )

        pos_p, pos_a, pos_d = 0.0, 0.0, 0.0
        neg_p, neg_a, neg_d = 0.0, 0.0, 0.0
        pos_matches = 0
        neg_matches = 0

        for pattern, p, a, d in cls.POSITIVE_CUES:
            if pattern.search(clean_text):
                pos_p += p
                pos_a += a
                pos_d += d
                pos_matches += 1

        for pattern, p, a, d in cls.NEGATIVE_CUES:
            if pattern.search(clean_text):
                neg_p += abs(p)
                neg_a += a
                neg_d += d
                neg_matches += 1

        if pos_matches > 0 or neg_matches > 0:
            avg_pos_p = (pos_p / pos_matches) if pos_matches > 0 else 0.0
            avg_neg_p = (neg_p / neg_matches) if neg_matches > 0 else 0.0
            net_p = avg_pos_p - avg_neg_p

            total_matches = pos_matches + neg_matches
            avg_a = (pos_a + neg_a) / total_matches
            avg_d = (pos_d + neg_d) / total_matches

            return PADVector(
                pleasure=max(-1.0, min(1.0, net_p)),
                arousal=max(-1.0, min(1.0, avg_a)),
                dominance=max(-1.0, min(1.0, avg_d)),
            )

        # Default neutral baseline
        return PADVector(pleasure=0.0, arousal=0.0, dominance=0.0)


class OpenClawRewardPropagatorV6:
    """
    Hierarchical online reinforcement learning reward propagator.
    Traces subagent execution paths and dynamically modulates policy weights
    across the delegation tree upon user feedback.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.85,
        min_weight: float = 0.1,
        max_weight: float = 10.0,
    ) -> None:
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.min_weight = min_weight
        self.max_weight = max_weight
        self._lock = threading.RLock()
        self._execution_nodes: Dict[str, ExecutionNode] = {}
        self._agent_weights: Dict[str, float] = defaultdict(lambda: 1.0)
        self._skill_weights: Dict[str, float] = defaultdict(lambda: 1.0)
        self._root_actions: List[str] = []

    def record_action(
        self,
        action_id: Optional[str] = None,
        agent_id: str = "orchestrator",
        skill_name: str = "default_skill",
        role: str = "worker",
        parent_action_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionNode:
        """
        Records a subagent action in the hierarchy tree with parent linking.
        """
        act_id = action_id or f"act_{uuid.uuid4().hex[:8]}"

        with self._lock:
            depth = 0
            if parent_action_id and parent_action_id in self._execution_nodes:
                parent_node = self._execution_nodes[parent_action_id]
                parent_node.children_action_ids.append(act_id)
                depth = parent_node.depth + 1
            else:
                self._root_actions.append(act_id)

            init_weight = self._agent_weights.get(agent_id, 1.0)
            node = ExecutionNode(
                action_id=act_id,
                agent_id=agent_id,
                skill_name=skill_name,
                role=role,
                parent_action_id=parent_action_id,
                depth=depth,
                weight=init_weight,
                metadata=metadata or {},
            )

            self._execution_nodes[act_id] = node
            return node

    def propagate_feedback(
        self,
        user_reply: str,
        root_action_id: Optional[str] = None,
        explicit_pad: Optional[PADVector] = None,
    ) -> Dict[str, Any]:
        """
        Parses feedback from user reply and propagates reward recursively
        through the execution tree, updating subagent and skill weights.
        """
        with self._lock:
            pad_vector = explicit_pad or ImplicitFeedbackParser.parse_reply(user_reply)
            scalar_reward = pad_vector.to_scalar_reward()

            # Determine nodes to update
            if root_action_id and root_action_id in self._execution_nodes:
                target_roots = [root_action_id]
            else:
                target_roots = list(self._root_actions) if self._root_actions else list(self._execution_nodes.keys())

            updated_nodes: List[Dict[str, Any]] = []
            visited: Set[str] = set()

            def _traverse_and_update(node_id: str, current_depth: int) -> None:
                if node_id in visited or node_id not in self._execution_nodes:
                    return
                visited.add(node_id)
                node = self._execution_nodes[node_id]

                # Calculate discounted effective reward for this depth: r_eff = r * (gamma ^ depth)
                decay = math.pow(self.discount_factor, current_depth)
                effective_reward = scalar_reward * decay

                old_node_weight = node.weight
                delta = self.learning_rate * effective_reward
                new_node_weight = max(self.min_weight, min(self.max_weight, old_node_weight + delta))

                node.weight = new_node_weight
                node.reward_history.append(effective_reward)

                # Update agent and skill global weights
                old_agent_w = self._agent_weights[node.agent_id]
                self._agent_weights[node.agent_id] = max(
                    self.min_weight, min(self.max_weight, old_agent_w + delta)
                )

                old_skill_w = self._skill_weights[node.skill_name]
                self._skill_weights[node.skill_name] = max(
                    self.min_weight, min(self.max_weight, old_skill_w + delta)
                )

                updated_nodes.append({
                    "action_id": node.action_id,
                    "agent_id": node.agent_id,
                    "skill_name": node.skill_name,
                    "depth": node.depth,
                    "effective_reward": effective_reward,
                    "old_weight": old_node_weight,
                    "new_weight": new_node_weight,
                })

                # Recursively propagate to subagent children
                for child_id in node.children_action_ids:
                    _traverse_and_update(child_id, current_depth + 1)

            for root_id in target_roots:
                _traverse_and_update(root_id, current_depth=0)

            return {
                "user_reply": user_reply,
                "pad_vector": pad_vector.to_dict(),
                "scalar_reward": scalar_reward,
                "updated_nodes_count": len(updated_nodes),
                "nodes": updated_nodes,
                "agent_weights": dict(self._agent_weights),
                "skill_weights": dict(self._skill_weights),
            }

    def get_agent_weight(self, agent_id: str) -> float:
        """Returns the current policy weight for an agent."""
        with self._lock:
            return self._agent_weights.get(agent_id, 1.0)

    def get_skill_weight(self, skill_name: str) -> float:
        """Returns the current policy weight for a skill."""
        with self._lock:
            return self._skill_weights.get(skill_name, 1.0)

    def get_execution_tree(self) -> Dict[str, Any]:
        """Exports the entire tracked execution hierarchy."""
        with self._lock:
            return {
                "total_nodes": len(self._execution_nodes),
                "root_actions": list(self._root_actions),
                "nodes": {k: v.to_dict() for k, v in self._execution_nodes.items()},
                "agent_weights": dict(self._agent_weights),
                "skill_weights": dict(self._skill_weights),
            }

    def clear(self) -> None:
        """Resets execution nodes and cached weights."""
        with self._lock:
            self._execution_nodes.clear()
            self._agent_weights.clear()
            self._skill_weights.clear()
            self._root_actions.clear()
