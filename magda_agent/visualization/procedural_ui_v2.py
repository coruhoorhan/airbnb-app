import logging
import copy
from typing import Dict, List, Any

from magda_agent.visualization.canvas_patching_v5 import CanvasPatchManagerV5

logger = logging.getLogger(__name__)

class ProceduralMemoryVisualizerV2:
    """
    ProceduralMemoryVisualizerV2 visualizes the real-time skill weight updates
    from the procedural memory stream. It takes JSON patches and displays them
    in a structured UI format.

    Inspired by the OpenClaw Canvas Live Visualization trend.
    """

    def __init__(self) -> None:
        """
        Initializes the ProceduralMemoryVisualizerV2 with an empty internal state.
        The internal state stores skill identifiers and their associated weights.
        """
        self.state: Dict[str, Any] = {}
        self.patch_manager = CanvasPatchManagerV5()

    def apply_patches(self, patches: List[Dict[str, Any]]) -> None:
        """
        Applies a series of JSON patches to the internal procedural memory state.

        Args:
            patches (List[Dict[str, Any]]): The JSON patch operations to apply.
        """
        try:
            self.state = self.patch_manager.apply_patch(self.state, patches)
        except Exception as e:
            logger.error(f"Failed to apply patches to visualizer state: {e}")

    def get_ui_structure(self) -> Dict[str, Any]:
        """
        Translates the internal state into a structured UI representation suitable
        for a frontend canvas. This function sorts the skills by weight in descending
        order and adds visual indicators (e.g., colors based on weight values).

        Returns:
            Dict[str, Any]: A dictionary structured for real-time canvas UI rendering.
        """
        skills_ui = []
        for skill_id, weight in self.state.items():
            # Add a visual indicator for high/low weights
            color = "green" if weight > 0.7 else ("red" if weight < 0.3 else "yellow")
            skills_ui.append({
                "skill_id": skill_id,
                "weight": weight,
                "color": color
            })

        # Sort by weight in descending order
        skills_ui.sort(key=lambda x: x["weight"], reverse=True)

        return {
            "type": "ProceduralMemoryVisualization",
            "status": "live",
            "skills": skills_ui,
            "total_skills": len(skills_ui)
        }
