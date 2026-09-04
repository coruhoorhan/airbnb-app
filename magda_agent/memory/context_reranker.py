import logging
from typing import Any, Dict, List, Optional

from magda_agent.memory.context_engine import ContextPlugin

class ContextLiveRerankerPlugin(ContextPlugin):
    """
    Context Live Re-ranker Plugin V1
    Dynamically re-orders Working Memory entries based on instantaneous task urgency and emotional arousal.
    """

    def __init__(self) -> None:
        pass

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        logging.debug("ContextLiveRerankerPlugin initialized")

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """
        Sort the retrieved context entries dynamically based on a computed score.
        Score = importance + (emotional arousal * 0.5)
        Highest score first.
        """
        if not context:
            return context

        def calculate_score(entry: Any) -> float:
            # Fallback importance is 0.0
            importance = getattr(entry, "importance", 0.0)

            # Emotional arousal (assume PADState has 'arousal')
            arousal = 0.0
            if hasattr(entry, "emotional_state") and entry.emotional_state:
                arousal = getattr(entry.emotional_state, "arousal", 0.0)

            # Calculate final urgency score
            return importance + (arousal * 0.5)

        # Re-rank context based on score (descending)
        sorted_context = sorted(context, key=calculate_score, reverse=True)
        return sorted_context
