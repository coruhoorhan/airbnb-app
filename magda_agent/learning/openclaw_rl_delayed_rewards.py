from typing import Any, Dict, List

class DelayedRewardTracker:
    """
    Tracks conversation steps to apply delayed rewards backwards
    through a trajectory, inspired by OpenClaw RL patterns.
    """

    def __init__(self) -> None:
        """
        Initializes an empty trajectory.
        """
        self.trajectory: List[Dict[str, Any]] = []

    def add_step(self, state: Any, action: Any) -> None:
        """
        Records a single conversation step.

        Args:
            state: The current state of the conversation.
            action: The action taken by the agent.
        """
        self.trajectory.append({
            "state": state,
            "action": action
        })

    def apply_reward(self, final_reward: float, discount_factor: float = 0.9) -> List[Dict[str, Any]]:
        """
        Backpropagates the final reward to all tracked steps in the trajectory.

        Args:
            final_reward: The reward received at the end of the trajectory.
            discount_factor: The rate at which the reward decays for earlier steps (0 to 1).

        Returns:
            A list of dictionaries containing the state, action, and calculated reward for each step.
        """
        if not self.trajectory:
            return []

        adjustments: List[Dict[str, Any]] = []
        current_reward = final_reward

        # Iterate backwards through the trajectory
        for step in reversed(self.trajectory):
            adjustments.append({
                "state": step["state"],
                "action": step["action"],
                "reward": current_reward
            })
            current_reward *= discount_factor

        # Reverse back to return in chronological order
        adjustments.reverse()
        return adjustments

    def clear(self) -> None:
        """
        Clears the current tracked trajectory.
        """
        self.trajectory.clear()
