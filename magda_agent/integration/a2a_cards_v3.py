"""
A2A Agent Discovery Cards Integration V3.

Inspired by A2A Protocol standard trends: Implements a peer discovery mechanism
that resolves, parses, and validates Agent Cards over network endpoints, maintaining
an active registry of discovered peer capabilities.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class AgentCardV3:
    """Represents an agent capability descriptor card conforming to A2A V3 standard."""

    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v3"
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCardV3":
        agent_id = str(data.get("agent_id") or data.get("id") or "").strip()
        if not agent_id:
            raise ValueError("AgentCardV3 requires a non-empty 'agent_id'")

        name = str(data.get("name") or agent_id).strip()
        description = str(data.get("description") or "").strip()
        capabilities = [str(c).strip() for c in (data.get("capabilities") or []) if str(c).strip()]
        endpoints = {str(k): str(v) for k, v in (data.get("endpoints") or {}).items()}

        return cls(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            endpoints=endpoints,
            protocol_version=str(data.get("protocol_version") or "v3"),
            status=str(data.get("status") or "active"),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV3":
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("AgentCard JSON must parse to a dictionary object")
        return cls.from_dict(data)

    def has_capability(self, capability: str) -> bool:
        """Check if agent advertises a specific capability."""
        req = capability.strip().lower()
        for cap in self.capabilities:
            c = cap.strip().lower()
            if req == c or req in c or c in req:
                return True
        return False

    def matches_any_capability(self, required_capabilities: List[str]) -> bool:
        """Check if agent matches any of the required capabilities."""
        return any(self.has_capability(c) for c in required_capabilities)

    def matches_all_capabilities(self, required_capabilities: List[str]) -> bool:
        """Check if agent matches all of the required capabilities."""
        return all(self.has_capability(c) for c in required_capabilities)


class AgentCardResolverV3:
    """Resolves Agent Cards from network endpoints using injected or mocked HTTP clients."""

    def __init__(self, default_timeout_seconds: float = 5.0):
        self.default_timeout = default_timeout_seconds

    async def resolve_endpoint_async(
        self,
        endpoint_url: str,
        http_client: Optional[Any] = None,
    ) -> Optional[AgentCardV3]:
        """Fetch and parse an AgentCardV3 from a remote endpoint asynchronously."""
        url = endpoint_url if endpoint_url.endswith("/agent.json") or "?" in endpoint_url else f"{endpoint_url.rstrip('/')}/agent.json"

        if http_client is not None:
            try:
                # Handle mocked or real http client
                if hasattr(http_client, "get"):
                    if inspect.iscoroutinefunction(http_client.get):
                        resp = await http_client.get(url)
                    else:
                        resp = http_client.get(url)

                    # Extract text or json
                    if hasattr(resp, "json"):
                        data = resp.json()
                        if inspect.iscoroutinefunction(resp.json):
                            data = await resp.json()
                        if isinstance(data, dict):
                            return AgentCardV3.from_dict(data)
                        elif isinstance(data, str):
                            return AgentCardV3.from_json(data)

                    if hasattr(resp, "text"):
                        text_val = resp.text
                        if isinstance(text_val, str):
                            return AgentCardV3.from_json(text_val)

                    if isinstance(resp, dict):
                        return AgentCardV3.from_dict(resp)
            except Exception as e:
                logger.warning(f"Failed to resolve AgentCard from {url}: {e}")
                return None

        logger.warning(f"No HTTP client provided to resolve endpoint {url}")
        return None

    def resolve_endpoint_sync(
        self,
        endpoint_url: str,
        http_client: Optional[Any] = None,
    ) -> Optional[AgentCardV3]:
        """Synchronous wrapper for endpoint resolution."""
        return asyncio.run(self.resolve_endpoint_async(endpoint_url, http_client))


class A2ADiscoveryCardsV3:
    """
    A2A Agent Discovery Service V3.

    Manages resolution, registration, and capability indexing of peer Agent Cards.
    """

    def __init__(
        self,
        local_card: Optional[AgentCardV3] = None,
        resolver: Optional[AgentCardResolverV3] = None,
    ):
        self.local_card = local_card
        self.resolver = resolver or AgentCardResolverV3()
        self._peer_registry: Dict[str, AgentCardV3] = {}
        self._last_seen: Dict[str, float] = {}

        if self.local_card:
            self.register_peer(self.local_card)

    def register_peer(self, card: AgentCardV3) -> None:
        """Register or update a peer AgentCardV3 in the local discovery registry."""
        self._peer_registry[card.agent_id] = card
        self._last_seen[card.agent_id] = time.time()
        logger.info(f"Registered peer AgentCardV3 '{card.name}' ({card.agent_id})")

    def unregister_peer(self, agent_id: str) -> bool:
        """Remove a peer from the registry."""
        if agent_id in self._peer_registry:
            del self._peer_registry[agent_id]
            self._last_seen.pop(agent_id, None)
            return True
        return False

    def parse_and_ingest_card(
        self,
        raw_card: Union[Dict[str, Any], str],
    ) -> Tuple[bool, Optional[AgentCardV3], str]:
        """Parse raw JSON string or dict, validate, and register."""
        try:
            if isinstance(raw_card, str):
                card = AgentCardV3.from_json(raw_card)
            elif isinstance(raw_card, dict):
                card = AgentCardV3.from_dict(raw_card)
            else:
                return False, None, f"Unsupported card input type: {type(raw_card).__name__}"

            self.register_peer(card)
            return True, card, "Success"
        except Exception as e:
            logger.error(f"Failed to parse and ingest Agent Card: {e}")
            return False, None, str(e)

    async def discover_peers_async(
        self,
        endpoints: List[str],
        http_client: Optional[Any] = None,
    ) -> List[AgentCardV3]:
        """Query multiple remote endpoints to discover peer cards."""
        discovered: List[AgentCardV3] = []
        for ep in endpoints:
            card = await self.resolver.resolve_endpoint_async(ep, http_client)
            if card:
                self.register_peer(card)
                discovered.append(card)
        return discovered

    def discover_peers_sync(
        self,
        endpoints: List[str],
        http_client: Optional[Any] = None,
    ) -> List[AgentCardV3]:
        """Synchronously query multiple remote endpoints to discover peer cards."""
        return asyncio.run(self.discover_peers_async(endpoints, http_client))

    def get_peer(self, agent_id: str) -> Optional[AgentCardV3]:
        """Retrieve a registered peer by ID."""
        return self._peer_registry.get(agent_id)

    def get_all_peers(self) -> List[AgentCardV3]:
        """Retrieve all currently registered peer cards."""
        return list(self._peer_registry.values())

    def find_peers_by_capability(self, capability: str) -> List[AgentCardV3]:
        """Find all registered peer agents advertising a specific capability."""
        return [p for p in self._peer_registry.values() if p.has_capability(capability)]

    def find_peers_by_capabilities(
        self,
        capabilities: List[str],
        match_all: bool = False,
    ) -> List[AgentCardV3]:
        """Find peer agents matching a set of capabilities."""
        if match_all:
            return [p for p in self._peer_registry.values() if p.matches_all_capabilities(capabilities)]
        return [p for p in self._peer_registry.values() if p.matches_any_capability(capabilities)]
