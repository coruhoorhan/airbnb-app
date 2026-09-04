"""
A2A Discovery Agent Card Broadcaster V4 module.

Inspired by A2A standard trends: Implements an agent discovery component that
periodically broadcasts the agent's capabilities via Agent Card formatting over the
network and manages discovery registries.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AgentCardV4:
    """Represents the capabilities and network identity of an agent (V4 format)."""

    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v4"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCardV4":
        return cls(
            agent_id=str(data.get("agent_id") or data.get("id") or ""),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            capabilities=list(data.get("capabilities") or []),
            endpoints=dict(data.get("endpoints") or {}),
            protocol_version=str(data.get("protocol_version") or "v4"),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV4":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def has_capability(self, capability: str) -> bool:
        cap_lower = capability.lower()
        return any(c.lower() == cap_lower or cap_lower in c.lower() for c in self.capabilities)


class A2ADiscoveryRegistryV4:
    """A registry to manage external agent discovery using Agent Cards (V4)."""

    def __init__(self) -> None:
        self._registry: Dict[str, AgentCardV4] = {}
        self._last_seen: Dict[str, float] = {}

    def register_agent(self, card: AgentCardV4) -> None:
        """Registers or updates an AgentCardV4 in the registry."""
        self._registry[card.agent_id] = card
        self._last_seen[card.agent_id] = time.time()
        logger.info(f"Registered AgentCardV4 for agent_id: {card.agent_id}")

    def unregister_agent(self, agent_id: str) -> None:
        """Removes an agent from the registry."""
        if agent_id in self._registry:
            del self._registry[agent_id]
            self._last_seen.pop(agent_id, None)
            logger.info(f"Unregistered agent_id: {agent_id}")
        else:
            logger.warning(f"Attempted to unregister non-existent agent_id: {agent_id}")

    def parse_and_register_cards(self, raw_cards: List[str]) -> List[AgentCardV4]:
        """Parses a list of JSON-formatted agent card strings and registers valid ones."""
        successfully_parsed: List[AgentCardV4] = []
        for raw in raw_cards:
            try:
                card = AgentCardV4.from_json(raw)
                self.register_agent(card)
                successfully_parsed.append(card)
            except Exception as e:
                logger.error(f"Failed to parse AgentCard JSON: {e}")
        return successfully_parsed

    def get_agent_card(self, agent_id: str) -> Optional[AgentCardV4]:
        """Retrieves an AgentCardV4 by agent_id."""
        return self._registry.get(agent_id)

    def get_all_agents(self) -> List[AgentCardV4]:
        """Returns all currently registered agent cards."""
        return list(self._registry.values())

    def find_agents_by_capability(self, capability: str) -> List[AgentCardV4]:
        """Finds all agents that advertise a specific capability."""
        return [card for card in self._registry.values() if card.has_capability(capability)]


class A2ADiscoveryAgentCardBroadcasterV4:
    """
    Periodically formats and broadcasts the local agent's capabilities
    as a standardized A2A Agent Card over network/mesh transports.
    """

    def __init__(
        self,
        local_card: AgentCardV4,
        registry: Optional[A2ADiscoveryRegistryV4] = None,
        broadcast_transport_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        broadcast_interval_seconds: float = 30.0,
    ) -> None:
        self.local_card = local_card
        self.registry = registry or A2ADiscoveryRegistryV4()
        self.broadcast_transport_fn = broadcast_transport_fn
        self.broadcast_interval = broadcast_interval_seconds
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self.broadcast_count = 0
        self.last_broadcast_time: Optional[float] = None

    def generate_broadcast_payload(self) -> Dict[str, Any]:
        """Formats the standardized A2A discovery broadcast payload."""
        return {
            "type": "a2a_discovery_broadcast",
            "protocol": "a2a_v4",
            "broadcast_id": f"bcast_{uuid.uuid4().hex[:8]}",
            "timestamp": time.time(),
            "agent_card": self.local_card.to_dict(),
            "capabilities": list(self.local_card.capabilities),
            "endpoints": dict(self.local_card.endpoints),
        }

    async def broadcast_once(
        self,
        custom_transport: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ) -> Dict[str, Any]:
        """Executes a single broadcast of the agent card."""
        payload = self.generate_broadcast_payload()
        transport = custom_transport or self.broadcast_transport_fn

        if transport:
            try:
                await transport(payload)
            except Exception as e:
                logger.error(f"Transport error during agent card broadcast: {e}")

        self.broadcast_count += 1
        self.last_broadcast_time = time.time()
        logger.info(f"Broadcasted AgentCardV4 for '{self.local_card.name}' ({self.local_card.agent_id})")
        return payload

    def receive_remote_broadcast(self, payload: Dict[str, Any]) -> Optional[AgentCardV4]:
        """Processes an incoming broadcast payload from a remote peer and registers it."""
        try:
            card_data = payload.get("agent_card") or payload
            card = AgentCardV4.from_dict(card_data)
            self.registry.register_agent(card)
            logger.info(f"Processed remote broadcast for peer '{card.name}' ({card.agent_id})")
            return card
        except Exception as e:
            logger.error(f"Failed to process remote discovery broadcast: {e}")
            return None

    async def start_broadcasting(self) -> None:
        """Starts periodic background broadcast loop."""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        while self._is_running:
            try:
                await self.broadcast_once()
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")

            try:
                await asyncio.sleep(self.broadcast_interval)
            except asyncio.CancelledError:
                break

    def stop_broadcasting(self) -> None:
        """Stops background broadcast loop."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()


# Backwards compatibility alias
A2AAgentCardBroadcasterV4 = A2ADiscoveryAgentCardBroadcasterV4
