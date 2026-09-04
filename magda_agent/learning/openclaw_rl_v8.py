from typing import Dict
from magda_agent.emotions.mirror_neurons import MirrorNeurons

class RLSignalsProcessorV8:
    """
    OpenClaw RL Signals Processor V8.
    Responsible for processing user replies and tool outputs to generate next-state signals
    and reward values for online reinforcement learning from implicit user feedback.
    """

    def __init__(self, mirror_neurons: MirrorNeurons) -> None:
        """
        Initializes the RL Signals Processor V8.

        Args:
            mirror_neurons (MirrorNeurons): The module responsible for extracting PAD shifts.
        """
        self.mirror_neurons = mirror_neurons

    def process_next_state_signals(self, user_reply: str, tool_output: str) -> Dict[str, float]:
        """
        Maps a user reply and tool output to a dictionary of next-state signals.

        Args:
            user_reply (str): The text of the user's reply.
            tool_output (str): The text output from the executed tool.

        Returns:
            Dict[str, float]: A dictionary containing 'p_shift', 'a_shift', 'd_shift', and 'reward'.
        """
        combined_text = f"{user_reply} {tool_output}".strip()
        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(combined_text)

        reward = (p_shift + 1.0) * 5.0

        return {
            "p_shift": p_shift,
            "a_shift": a_shift,
            "d_shift": d_shift,
            "reward": reward
        }
