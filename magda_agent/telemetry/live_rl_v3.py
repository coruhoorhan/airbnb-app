import logging
import time
from typing import Any, Dict, Optional
from magda_agent.emotions.engine import PADState
from magda_agent.telemetry.live_event_emitter import LiveEventEmitter

class LiveRLTelemetryV3(LiveEventEmitter):
    """
    Live telemetry streamer for OpenClaw-RL.
    Extends LiveEventEmitter to broadcast PAD shifts via WebSocket.
    """
    def __init__(self, websocket: Optional[Any] = None) -> None:
        """
        Initialize the LiveRLTelemetryV3 with an optional websocket.
        """
        super().__init__(websocket)
        self.logger = logging.getLogger(__name__)

    async def emit_pad_shift(
        self,
        old_pad: PADState,
        new_pad: PADState,
        emotion_label: str,
        user_id: Optional[int] = None,
        habit_weights: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Emit a real-time PAD state shift event over the websocket.

        Args:
            old_pad: The previous PADState.
            new_pad: The updated PADState.
            emotion_label: The human-readable emotion label for the new state.
            user_id: Optional identifier for the user.
            habit_weights: Optional current habit weights of the agent.
        """
        delta_pad = {
            "pleasure": new_pad.pleasure - old_pad.pleasure,
            "arousal": new_pad.arousal - old_pad.arousal,
            "dominance": new_pad.dominance - old_pad.dominance
        }

        data = {
            "user_id": user_id,
            "old_pad": old_pad.to_dict(),
            "new_pad": new_pad.to_dict(),
            "delta": delta_pad,
            "emotion_label": emotion_label,
        }

        if habit_weights is not None:
            data["habit_weights"] = habit_weights

        await self.emit_state_change("pad_shift", data)
