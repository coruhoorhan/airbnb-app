from typing import List, Dict, Optional, Tuple
import logging

from magda_agent.emotions.mirror_neurons import MirrorNeurons

class PADShiftAnalyzer:
    """
    Analytics module to track Pleasure, Arousal, Dominance (PAD) shifts
    across user interactions and measure overall agent behavior adaptability.
    """

    def __init__(self, mirror_neurons: MirrorNeurons) -> None:
        """
        Initializes the PADShiftAnalyzer.

        Args:
            mirror_neurons (MirrorNeurons): The module for computing PAD shifts.
        """
        self.mirror_neurons = mirror_neurons

    def analyze_interaction(self, user_reply: str, tool_output: Optional[str] = None) -> Dict[str, float]:
        """
        Analyzes a single interaction to extract PAD shifts.

        Args:
            user_reply (str): The user's input string.
            tool_output (Optional[str], optional): The tool output string. Defaults to None.

        Returns:
            Dict[str, float]: A dictionary containing the p, a, d shifts.
        """
        signal_text = user_reply
        if tool_output:
            signal_text += f" [Tool Output: {tool_output}]"

        p_shift, a_shift, d_shift = self.mirror_neurons.empathize(signal_text)
        return {
            "p_shift": p_shift,
            "a_shift": a_shift,
            "d_shift": d_shift
        }

    def aggregate_shifts(self, interaction_logs: List[Dict[str, Optional[str]]]) -> Dict[str, float]:
        """
        Aggregates PAD shifts over a list of interaction logs and calculates an adaptability score.

        Args:
            interaction_logs (List[Dict[str, Optional[str]]]): A list of dicts, each with
                'user_reply' and optionally 'tool_output'.

        Returns:
            Dict[str, float]: Aggregated metrics including total shifts, averages, and an adaptability score.
        """
        if not interaction_logs:
            return {
                "total_p_shift": 0.0,
                "total_a_shift": 0.0,
                "total_d_shift": 0.0,
                "avg_p_shift": 0.0,
                "avg_a_shift": 0.0,
                "avg_d_shift": 0.0,
                "adaptability_score": 0.0
            }

        total_p, total_a, total_d = 0.0, 0.0, 0.0

        for log in interaction_logs:
            reply = log.get("user_reply", "")
            output = log.get("tool_output", None)
            shifts = self.analyze_interaction(reply, output)
            total_p += shifts["p_shift"]
            total_a += shifts["a_shift"]
            total_d += shifts["d_shift"]

        n = len(interaction_logs)
        avg_p = total_p / n
        avg_a = total_a / n
        avg_d = total_d / n

        # Adaptability is measured by the absolute magnitude of overall shifts.
        # More empathetic responsiveness implies higher adaptability.
        adaptability_score = abs(avg_p) + abs(avg_a) + abs(avg_d)

        logging.info(f"Aggregated {n} logs. Adaptability score: {adaptability_score:.4f}")

        return {
            "total_p_shift": total_p,
            "total_a_shift": total_a,
            "total_d_shift": total_d,
            "avg_p_shift": avg_p,
            "avg_a_shift": avg_a,
            "avg_d_shift": avg_d,
            "adaptability_score": adaptability_score
        }
