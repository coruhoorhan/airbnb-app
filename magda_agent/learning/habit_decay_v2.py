"""
OpenClaw-RL Habit Decay Parameterization V2.

Inspired by OpenClaw-RL learning and habit formation trends: Implements configurable,
time-dependent and feedback-driven decay curves (exponential, linear, half-life, stepwise)
for learned agent habits, allowing precise tuning of habit permanence and decay rates.
"""

import asyncio
import json
import logging
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class DecayFunctionType(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    HALF_LIFE = "half_life"
    STEPWISE = "stepwise"


@dataclass
class HabitDecayConfig:
    """Configurable parameterization for habit decay curves."""

    decay_function: DecayFunctionType = DecayFunctionType.EXPONENTIAL
    decay_rate: float = 0.001  # Decay rate per second
    half_life_seconds: float = 3600.0  # Time for strength above baseline to halve
    baseline_strength: float = 1.0
    min_strength: float = 0.05
    max_strength: float = 10.0
    reinforcement_factor: float = 0.5  # Gain upon positive feedback

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decay_function"] = (
            self.decay_function.value
            if isinstance(self.decay_function, DecayFunctionType)
            else str(self.decay_function)
        )
        return d


@dataclass
class LearnedHabitRecord:
    """Represents a learned behavioral or skill habit."""

    name: str
    current_strength: float = 1.0
    initial_strength: float = 1.0
    last_reinforced_at: float = field(default_factory=time.time)
    last_evaluated_at: float = field(default_factory=time.time)
    total_reinforcements: int = 0
    config: HabitDecayConfig = field(default_factory=HabitDecayConfig)
    habit_id: str = field(default_factory=lambda: f"hbt_{uuid.uuid4().hex[:8]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_strength": round(self.current_strength, 4),
            "initial_strength": self.initial_strength,
            "last_reinforced_at": self.last_reinforced_at,
            "total_reinforcements": self.total_reinforcements,
            "config": self.config.to_dict(),
            "habit_id": self.habit_id,
        }


class OpenClawHabitDecayManagerV2:
    """
    OpenClaw-RL Habit Decay Manager V2.

    Manages a collection of learned habits, applying configurable mathematical decay curves
    and feedback reinforcements.
    """

    def __init__(self, default_config: Optional[HabitDecayConfig] = None):
        self.default_config = default_config or HabitDecayConfig()
        self._habits: Dict[str, LearnedHabitRecord] = {}

    def register_habit(
        self,
        name: str,
        initial_strength: float = 1.0,
        config: Optional[HabitDecayConfig] = None,
        creation_time: Optional[float] = None,
    ) -> LearnedHabitRecord:
        """Register a new habit with specified or default decay parameters."""
        now = creation_time if creation_time is not None else time.time()
        cfg = config or self.default_config
        clamped_init = max(cfg.min_strength, min(cfg.max_strength, initial_strength))

        habit = LearnedHabitRecord(
            name=name,
            current_strength=clamped_init,
            initial_strength=clamped_init,
            last_reinforced_at=now,
            last_evaluated_at=now,
            config=cfg,
        )
        self._habits[name] = habit
        return habit

    def get_habit(self, name: str) -> Optional[LearnedHabitRecord]:
        """Fetch habit record by name."""
        return self._habits.get(name)

    def configure_habit_decay(
        self,
        name: str,
        decay_function: Optional[Union[DecayFunctionType, str]] = None,
        decay_rate: Optional[float] = None,
        half_life_seconds: Optional[float] = None,
        reinforcement_factor: Optional[float] = None,
        baseline_strength: Optional[float] = None,
    ) -> LearnedHabitRecord:
        """Dynamically adjust decay parameters for an existing habit."""
        habit = self.get_habit(name)
        if not habit:
            raise ValueError(f"Habit '{name}' not found.")

        if decay_function is not None:
            if isinstance(decay_function, str):
                try:
                    habit.config.decay_function = DecayFunctionType(decay_function.lower())
                except ValueError:
                    pass
            else:
                habit.config.decay_function = decay_function

        if decay_rate is not None:
            habit.config.decay_rate = max(0.0, float(decay_rate))

        if half_life_seconds is not None:
            habit.config.half_life_seconds = max(0.001, float(half_life_seconds))

        if reinforcement_factor is not None:
            habit.config.reinforcement_factor = max(0.0, float(reinforcement_factor))

        if baseline_strength is not None:
            habit.config.baseline_strength = float(baseline_strength)

        return habit

    def calculate_decayed_strength(
        self,
        name: str,
        current_time: Optional[float] = None,
    ) -> float:
        """
        Calculate current strength of a habit after applying time decay from its last reinforcement.
        """
        habit = self.get_habit(name)
        if not habit:
            raise ValueError(f"Habit '{name}' not found.")

        now = current_time if current_time is not None else time.time()
        elapsed = max(0.0, now - habit.last_reinforced_at)
        cfg = habit.config
        baseline = cfg.baseline_strength

        # Delta from baseline
        delta = habit.current_strength - baseline

        if elapsed <= 0.0 or delta == 0.0:
            return habit.current_strength

        func_type = cfg.decay_function

        if func_type == DecayFunctionType.EXPONENTIAL:
            decay_factor = math.exp(-cfg.decay_rate * elapsed)
            decayed = baseline + (delta * decay_factor)

        elif func_type == DecayFunctionType.HALF_LIFE:
            # decayed = baseline + delta * (0.5 ** (elapsed / half_life))
            half_life_ratio = elapsed / cfg.half_life_seconds
            decay_factor = math.pow(0.5, half_life_ratio)
            decayed = baseline + (delta * decay_factor)

        elif func_type == DecayFunctionType.LINEAR:
            # Constant rate reduction per second towards baseline
            reduction = cfg.decay_rate * elapsed
            if delta > 0:
                decayed = max(baseline, habit.current_strength - reduction)
            else:
                decayed = min(baseline, habit.current_strength + reduction)

        elif func_type == DecayFunctionType.STEPWISE:
            # Decay in distinct blocks of 60 seconds
            steps = int(elapsed // 60)
            step_rate = min(0.99, cfg.decay_rate * 60)
            decay_factor = (1.0 - step_rate) ** steps
            decayed = baseline + (delta * decay_factor)

        else:
            decayed = habit.current_strength

        clamped = max(cfg.min_strength, min(cfg.max_strength, decayed))
        return round(clamped, 4)

    def reinforce_habit(
        self,
        name: str,
        feedback_score: float = 1.0,
        current_time: Optional[float] = None,
    ) -> float:
        """
        Apply feedback reinforcement to a habit.
        Calculates current decayed strength first, then boosts or penalizes strength.
        """
        now = current_time if current_time is not None else time.time()
        current_val = self.calculate_decayed_strength(name, current_time=now)
        habit = self._habits[name]
        cfg = habit.config

        # Reinforcement boost/penalty
        boost = cfg.reinforcement_factor * feedback_score
        new_strength = current_val + boost
        clamped = max(cfg.min_strength, min(cfg.max_strength, new_strength))

        habit.current_strength = round(clamped, 4)
        habit.last_reinforced_at = now
        habit.last_evaluated_at = now
        habit.total_reinforcements += 1

        logger.info(f"Reinforced habit '{name}': score={feedback_score:.2f}, new_strength={habit.current_strength:.4f}")
        return habit.current_strength

    def decay_all_habits(self, current_time: Optional[float] = None) -> Dict[str, float]:
        """Apply and update decayed strength across all registered habits."""
        now = current_time if current_time is not None else time.time()
        results = {}
        for name in list(self._habits.keys()):
            val = self.calculate_decayed_strength(name, current_time=now)
            self._habits[name].current_strength = val
            self._habits[name].last_evaluated_at = now
            results[name] = val
        return results

    def get_habit_stats(self) -> Dict[str, Any]:
        """Summary metrics of all active habits."""
        return {
            "total_habits": len(self._habits),
            "habits": {name: h.to_dict() for name, h in self._habits.items()},
        }
