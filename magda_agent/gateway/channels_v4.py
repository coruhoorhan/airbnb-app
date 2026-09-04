import asyncio
from typing import Any, Dict
from magda_agent.gateway.router import GatewayRouter, UnifiedMessage

class Channel:
    """Base class for all unified gateway channels."""
    def __init__(self, channel_id: str):
        self.channel_id = channel_id

    async def process(self, raw_message: Dict[str, Any], router: GatewayRouter) -> Any:
        """Process raw message and route it as a UnifiedMessage."""
        raise NotImplementedError


class DiscordChannel(Channel):
    """Discord channel adapter implementation."""
    def __init__(self, channel_id: str = "discord"):
        super().__init__(channel_id)

    async def process(self, event: Dict[str, Any], router: GatewayRouter) -> Any:
        """Process discord event and route."""
        text = event.get("content", "")
        author = event.get("author", {})
        user_id = str(author.get("id", "unknown"))
        msg = UnifiedMessage(
            channel=self.channel_id,
            text=text,
            user_id=user_id,
            metadata={"raw_event": event}
        )
        return await router.route_message(msg)


class WhatsAppChannel(Channel):
    """WhatsApp channel adapter implementation."""
    def __init__(self, channel_id: str = "whatsapp"):
        super().__init__(channel_id)

    async def process(self, payload: Dict[str, Any], router: GatewayRouter) -> Any:
        """Process whatsapp payload and route."""
        # Typically WhatsApp payloads have structure like:
        # {"messages": [{"text": {"body": "hello"}, "from": "1234567"}]}
        messages = payload.get("messages", [])
        if not messages:
            return None

        first_message = messages[0]
        text_obj = first_message.get("text", {})
        text = text_obj.get("body", "")
        user_id = str(first_message.get("from", "unknown"))

        msg = UnifiedMessage(
            channel=self.channel_id,
            text=text,
            user_id=user_id,
            metadata={"raw_payload": payload}
        )
        return await router.route_message(msg)


class CLIChannel(Channel):
    """CLI channel adapter implementation."""
    def __init__(self, channel_id: str = "cli"):
        super().__init__(channel_id)

    async def process(self, event: Dict[str, Any], router: GatewayRouter) -> Any:
        """Process CLI event and route."""
        text = event.get("input", "")
        user_id = str(event.get("user", "local_user"))
        msg = UnifiedMessage(
            channel=self.channel_id,
            text=text,
            user_id=user_id,
            metadata={"raw_cli_event": event}
        )
        return await router.route_message(msg)
