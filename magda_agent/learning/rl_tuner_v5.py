import logging
from typing import Dict

class OnlineRLParameterTunerV5:
    """
    Inspired by OpenClaw RL trends: Implements online RL to tune learning rates
    during execution based on explicit or implicit feedback and environment metrics.
    """

    def __init__(self, base_learning_rate: float = 0.01) -> None:
        """
        Initializes the parameter tuner.

        Args:
            base_learning_rate (float): The initial base learning rate.
        """
        self.learning_rate = base_learning_rate
        self.min_lr = 0.001
        self.max_lr = 0.1

    def tune_learning_rate(self, metrics: Dict[str, float]) -> float:
        """
        Adjusts the current learning rate based on performance metrics.

        Args:
            metrics (Dict[str, float]): A dictionary containing metrics such as
                'reward', 'loss', or 'uncertainty'.

        Returns:
            float: The updated learning rate.
        """
        if not metrics:
            return self.learning_rate

        reward = metrics.get('reward', 0.0)
        uncertainty = metrics.get('uncertainty', 0.0)

        # Increase LR if uncertainty is high, meaning we need to explore/adapt faster
        if uncertainty > 0.5:
            self.learning_rate *= 1.1

        # Decrease LR if reward is consistently high to fine-tune and stabilize
        if reward > 8.0:
            self.learning_rate *= 0.95

        # If reward is very low, we might be stuck in a local minimum, slightly increase LR
        elif reward < 3.0:
            self.learning_rate *= 1.05

        # Clip learning rate to boundaries
        self.learning_rate = max(self.min_lr, min(self.max_lr, self.learning_rate))

        logging.info(f"OnlineRLParameterTunerV5: Tuned learning rate to {self.learning_rate:.4f}")
        return self.learning_rate
