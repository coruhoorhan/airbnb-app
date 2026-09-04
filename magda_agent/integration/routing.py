from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class NormalizedEvent:
    """
    Represents a standard event format normalized from various platforms.
    """
    platform: str
    user_id: str
    text: str
    raw_payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class MultiPlatformRouter:
    """
    Routing layer for handling and normalizing requests from various platforms
    (Telegram, Discord, CLI) into a unified internal format.
    """

    def normalize_event(self, platform: str, payload: Dict[str, Any]) -> NormalizedEvent:
        """
        Normalizes an incoming platform-specific payload into a standard NormalizedEvent.

        Args:
            platform (str): The platform origin (e.g., "telegram", "discord", "cli").
            payload (Dict[str, Any]): The raw payload from the platform.

        Returns:
            NormalizedEvent: The parsed and normalized event.

        Raises:
            ValueError: If the platform is unsupported or the payload is invalid.
        """
        platform = platform.lower()
        if platform == "telegram":
            return self._parse_telegram(payload)
        elif platform == "discord":
            return self._parse_discord(payload)
        elif platform == "cli":
            return self._parse_cli(payload)
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    def _parse_telegram(self, payload: Dict[str, Any]) -> NormalizedEvent:
        """Parses a Telegram payload."""
        message = payload.get("message", {})
        from_user = message.get("from", {})
        user_id = str(from_user.get("id", ""))
        text = message.get("text", "")

        if not user_id:
            raise ValueError("Invalid Telegram payload: missing user id")

        return NormalizedEvent(
            platform="telegram",
            user_id=user_id,
            text=text,
            raw_payload=payload,
            metadata={"chat_id": message.get("chat", {}).get("id")}
        )

    def _parse_discord(self, payload: Dict[str, Any]) -> NormalizedEvent:
        """Parses a Discord payload."""
        author = payload.get("author", {})
        user_id = str(author.get("id", ""))
        text = payload.get("content", "")

        if not user_id:
            raise ValueError("Invalid Discord payload: missing author id")

        return NormalizedEvent(
            platform="discord",
            user_id=user_id,
            text=text,
            raw_payload=payload,
            metadata={"channel_id": payload.get("channel_id")}
        )

    def _parse_cli(self, payload: Dict[str, Any]) -> NormalizedEvent:
        """Parses a CLI payload."""
        user_id = payload.get("user", "local_user")
        text = payload.get("input", "")

        if "input" not in payload:
            raise ValueError("Invalid CLI payload: missing input text")

        return NormalizedEvent(
            platform="cli",
            user_id=user_id,
            text=text,
            raw_payload=payload,
            metadata={}
        )
