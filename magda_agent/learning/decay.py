import math
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def decay_weight_exponential(
    weight: float,
    elapsed_time: float,
    decay_rate: float,
    baseline: float = 1.0
) -> float:
    """
    Decays a single weight towards a baseline value using exponential decay over time.

    Formula:
        new_weight = baseline + (weight - baseline) * exp(-decay_rate * elapsed_time)

    Args:
        weight (float): The current weight.
        elapsed_time (float): Time elapsed (in seconds, turns, or other units).
                              Must be non-negative. If negative, returns original weight.
        decay_rate (float): The rate of decay. Must be non-negative.
        baseline (float): The target baseline value that weights decay towards. Defaults to 1.0.

    Returns:
        float: The decayed weight.
    """
    if elapsed_time <= 0.0 or decay_rate <= 0.0:
        return weight

    diff = weight - baseline
    decay_factor = math.exp(-decay_rate * elapsed_time)
    return baseline + diff * decay_factor


def decay_weight_step(
    weight: float,
    steps: int,
    decay_rate: float,
    baseline: float = 1.0
) -> float:
    """
    Decays a single weight towards a baseline value using discrete steps.

    Formula:
        new_weight = baseline + (weight - baseline) * (1 - decay_rate) ** steps

    Args:
        weight (float): The current weight.
        steps (int): The number of steps elapsed. Must be non-negative.
        decay_rate (float): The decay rate per step (between 0.0 and 1.0).
        baseline (float): The target baseline value that weights decay towards. Defaults to 1.0.

    Returns:
        float: The decayed weight.
    """
    if steps <= 0 or decay_rate <= 0.0:
        return weight

    # Clamp decay_rate to [0, 1]
    clamped_rate = max(0.0, min(1.0, decay_rate))
    diff = weight - baseline
    decay_factor = (1.0 - clamped_rate) ** steps
    return baseline + diff * decay_factor


def decay_skill_weights(
    skill_weights: Dict[str, float],
    last_updated: Dict[str, float],
    current_time: float,
    decay_rate: float,
    baseline: float = 1.0
) -> Dict[str, float]:
    """
    Decays a dictionary of skill weights based on individual last updated timestamps.

    Args:
        skill_weights (Dict[str, float]): Map of skill names to current weights.
        last_updated (Dict[str, float]): Map of skill names to their last updated timestamps.
        current_time (float): The current timestamp.
        decay_rate (float): The exponential decay rate.
        baseline (float): Target baseline value. Defaults to 1.0.

    Returns:
        Dict[str, float]: A new dictionary containing the decayed skill weights.
    """
    decayed_weights = {}
    for skill, weight in skill_weights.items():
        last_time = last_updated.get(skill)
        if last_time is not None:
            elapsed = current_time - last_time
            decayed_weights[skill] = decay_weight_exponential(
                weight, elapsed, decay_rate, baseline
            )
        else:
            decayed_weights[skill] = weight
    return decayed_weights


class SkillWeightDecayer:
    """
    A helper class to manage and apply time-based or step-based skill weight decay.
    """

    def __init__(self, decay_rate: float = 0.05, baseline: float = 1.0) -> None:
        """
        Initializes the SkillWeightDecayer.

        Args:
            decay_rate (float): The decay rate used for step or time-based decay.
            baseline (float): The baseline value towards which weights decay. Defaults to 1.0.
        """
        self.decay_rate = decay_rate
        self.baseline = baseline

    def decay_by_time(
        self,
        skill_weights: Dict[str, float],
        last_updated: Dict[str, float],
        current_time: float
    ) -> Dict[str, float]:
        """
        Applies time-based exponential decay to a set of skill weights.
        """
        return decay_skill_weights(
            skill_weights, last_updated, current_time, self.decay_rate, self.baseline
        )

    def decay_by_steps(
        self,
        skill_weights: Dict[str, float],
        steps: int = 1
    ) -> Dict[str, float]:
        """
        Applies step-based decay to all skill weights uniformly.
        """
        return {
            skill: decay_weight_step(weight, steps, self.decay_rate, self.baseline)
            for skill, weight in skill_weights.items()
        }
