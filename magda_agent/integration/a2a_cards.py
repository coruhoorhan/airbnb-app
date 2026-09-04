from typing import Dict, List, Optional, Any
import httpx
import json
import logging
from dataclasses import dataclass, asdict
from magda_agent.integration.a2a_security import A2ASecurityContext


@dataclass
class AgentCardV3:
    """
    Represents the capabilities and identity of an agent in the network, version 3.
    Supports standardized capability matching.
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v3"

    def to_json(self) -> str:
        """
        Serializes the AgentCardV3 to a JSON string.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV3":
        """
        Deserializes an AgentCardV3 from a JSON string.
        """
        data = json.loads(json_str)
        return cls(**data)

    def has_capability(self, capability: str) -> bool:
        """
        Checks if the agent has the specified capability.
        Supports exact match and prefix match (e.g. 'code' matches 'code_execution').
        """
        for cap in self.capabilities:
            if cap == capability or cap.startswith(f"{capability}_"):
                return True
        return False

    def matches_any_capability(self, required_capabilities: List[str]) -> bool:
        """
        Checks if the agent matches any of the required capabilities.
        """
        return any(self.has_capability(cap) for cap in required_capabilities)


class A2ADiscoveryV3:
    """
    Handles discovery of other agents in the network and broadcasting
    the local agent's capabilities using the v3 protocol.
    """
    def __init__(self, local_card: AgentCardV3, security_context: Optional[A2ASecurityContext] = None) -> None:
        """
        Initializes the discovery module with the local agent's card.
        """
        self.local_card = local_card
        self.security_context = security_context or A2ASecurityContext()
        self._discovered_agents: Dict[str, AgentCardV3] = {}
        self._capability_index: Dict[str, List[str]] = {}

    async def broadcast_card(self) -> str:
        """
        Broadcasts the local agent's card to the network in a v3 envelope format.
        """
        logging.info(f"Broadcasting Agent Card V3: {self.local_card.name}")

        envelope = {
            "type": "a2a_discovery_broadcast",
            "version": "3.0",
            "payload": asdict(self.local_card)
        }
        return json.dumps(envelope)

    async def fetch_cards(self, network_envelopes: Optional[List[str]] = None, auth_token: Optional[str] = None) -> None:
        """
        Fetches Agent Cards from the network envelopes and indexes them.
        """
        if auth_token and not self.security_context.validate_token(auth_token):
            logging.error("Invalid auth token for fetch_cards")
            raise ValueError("Invalid authentication token")

        self.security_context.trace_action("fetch_cards_v3", {"count": len(network_envelopes) if network_envelopes else 0})

        if network_envelopes is None:
            network_envelopes = []

        for envelope_json in network_envelopes:
            try:
                envelope = json.loads(envelope_json)
                if envelope.get("type") == "a2a_discovery_broadcast" and envelope.get("version") == "3.0":
                    payload = envelope.get("payload")
                    if isinstance(payload, str):
                        card = AgentCardV3.from_json(payload)
                    else:
                        card = AgentCardV3(**payload)
                    self._register_agent(card)
            except Exception as e:
                logging.error(f"Failed to parse Agent Card Envelope V3: {e}")

    def _register_agent(self, card: AgentCardV3) -> None:
        """
        Registers a discovered agent internally and updates the capability index.
        """
        self._discovered_agents[card.agent_id] = card
        for capability in card.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = []
            if card.agent_id not in self._capability_index[capability]:
                self._capability_index[capability].append(card.agent_id)
        logging.info(f"Discovered Agent V3: {card.name} with capabilities {card.capabilities}")

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentCardV3]:
        """
        Retrieves a discovered agent's card by its ID.
        """
        return self._discovered_agents.get(agent_id)

    def find_agents_by_capability(self, capability: str) -> List[AgentCardV3]:
        """
        Returns a list of Agent Cards that support the given capability.
        Supports capability matching logic.
        """
        matched_agents = []
        for agent in self._discovered_agents.values():
            if agent.has_capability(capability):
                matched_agents.append(agent)
        return matched_agents


@dataclass
class AgentCardV4:
    """
    Represents the capabilities and identity of an agent in the network, version 4.
    Supports standardized capability matching, status tracking, and metadata extension.
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v4"
    metadata: Optional[Dict[str, Any]] = None
    status: str = "active"

    def to_json(self) -> str:
        """
        Serializes the AgentCardV4 to a JSON string.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV4":
        """
        Deserializes an AgentCardV4 from a JSON string.
        """
        data = json.loads(json_str)
        return cls(**data)

    def has_capability(self, capability: str) -> bool:
        """
        Checks if the agent has the specified capability.
        Supports exact match and prefix match (e.g. 'code' matches 'code_execution').
        """
        for cap in self.capabilities:
            if cap == capability or cap.startswith(f"{capability}_"):
                return True
        return False

    def matches_any_capability(self, required_capabilities: List[str]) -> bool:
        """
        Checks if the agent matches any of the required capabilities.
        """
        return any(self.has_capability(cap) for cap in required_capabilities)


class A2ADiscoveryV4:
    """
    Handles discovery of other agents in the network and broadcasting
    the local agent's capabilities using the v4 protocol.
    """
    def __init__(self, local_card: AgentCardV4, security_context: Optional[A2ASecurityContext] = None) -> None:
        """
        Initializes the discovery module with the local agent's card.
        """
        self.local_card = local_card
        self.security_context = security_context or A2ASecurityContext()
        self._discovered_agents: Dict[str, AgentCardV4] = {}
        self._capability_index: Dict[str, List[str]] = {}

    async def broadcast_card(self) -> str:
        """
        Broadcasts the local agent's card to the network in a v4 envelope format.
        """
        logging.info(f"Broadcasting Agent Card V4: {self.local_card.name}")

        envelope = {
            "type": "a2a_discovery_broadcast",
            "version": "4.0",
            "payload": asdict(self.local_card)
        }
        return json.dumps(envelope)

    def parse_envelope(self, envelope_json: str) -> Optional[AgentCardV4]:
        """
        Parses a single network envelope JSON and returns an AgentCardV4 if valid.
        """
        try:
            envelope = json.loads(envelope_json)
            if isinstance(envelope, dict):
                if envelope.get("type") == "a2a_discovery_broadcast" and envelope.get("version") in ("4.0", "v4"):
                    payload = envelope.get("payload")
                    if isinstance(payload, str):
                        return AgentCardV4.from_json(payload)
                    elif isinstance(payload, dict):
                        return AgentCardV4(**payload)
                elif "agent_id" in envelope and "capabilities" in envelope:
                    return AgentCardV4(**envelope)
        except Exception as e:
            logging.error(f"Failed to parse Agent Card Envelope V4: {e}")
        return None

    async def fetch_cards(self, network_envelopes: Optional[List[str]] = None, auth_token: Optional[str] = None) -> List[AgentCardV4]:
        """
        Fetches Agent Cards from the network envelopes, registers and returns them.
        """
        if auth_token and not self.security_context.validate_token(auth_token):
            logging.error("Invalid auth token for fetch_cards")
            raise ValueError("Invalid authentication token")

        self.security_context.trace_action("fetch_cards_v4", {"count": len(network_envelopes) if network_envelopes else 0})

        if network_envelopes is None:
            network_envelopes = []

        registered_cards: List[AgentCardV4] = []
        for envelope_json in network_envelopes:
            card = self.parse_envelope(envelope_json)
            if card:
                self._register_agent(card)
                registered_cards.append(card)

        return registered_cards

    def _register_agent(self, card: AgentCardV4) -> None:
        """
        Registers a discovered agent internally and updates the capability index.
        """
        self._discovered_agents[card.agent_id] = card
        for capability in card.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = []
            if card.agent_id not in self._capability_index[capability]:
                self._capability_index[capability].append(card.agent_id)
        logging.info(f"Discovered Agent V4: {card.name} with capabilities {card.capabilities}")

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentCardV4]:
        """
        Retrieves a discovered agent's card by its ID.
        """
        return self._discovered_agents.get(agent_id)

    def find_agents_by_capability(self, capability: str) -> List[AgentCardV4]:
        """
        Returns a list of Agent Cards that support the given capability.
        Supports capability matching logic.
        """
        matched_agents = []
        for agent in self._discovered_agents.values():
            if agent.has_capability(capability):
                matched_agents.append(agent)
        return matched_agents

    def get_all_agents(self) -> List[AgentCardV4]:
        """
        Returns all discovered AgentCardV4 instances.
        """
        return list(self._discovered_agents.values())


class A2ADiscoveryMeshV4:
    """
    Manages an A2A discovery mesh based on the A2A Protocol trend for V4.
    It facilitates finding peers with required capabilities using AgentCardV4,
    and propagates gossip about known peers to other nodes.
    """

    def __init__(self, discovery: A2ADiscoveryV4) -> None:
        """
        Initializes the A2ADiscoveryMeshV4.

        Args:
            discovery: The core A2ADiscoveryV4 instance containing local_card and _discovered_agents.
        """
        self.discovery = discovery

    def aggregate_envelopes(self) -> List[Dict[str, Any]]:
        """
        Aggregates the local agent's card and all discovered peer cards into v4 envelopes.

        Returns:
            A list of envelope dictionaries.
        """
        cards = [self.discovery.local_card]
        cards.extend(list(self.discovery._discovered_agents.values()))

        envelopes = []
        for card in cards:
            envelope = {
                "type": "a2a_discovery_broadcast",
                "version": "4.0",
                "payload": asdict(card)
            }
            envelopes.append(envelope)

        return envelopes

    async def broadcast_gossip(self, endpoint_urls: List[str]) -> None:
        """
        Broadcasts all known agent cards (gossip) to the specified endpoints.

        Args:
            endpoint_urls: A list of HTTP endpoints to send the envelopes to.
        """
        envelopes = self.aggregate_envelopes()

        async with httpx.AsyncClient() as client:
            for url in endpoint_urls:
                try:
                    response = await client.post(url, json=envelopes)
                    response.raise_for_status()
                    logging.info(f"Successfully gossiped {len(envelopes)} envelopes to {url}")
                except Exception as e:
                    logging.error(f"Failed to gossip envelopes to {url}: {e}")

    async def receive_gossip(self, network_envelopes: List[str]) -> None:
        """
        Receives gossip data (a list of json envelope strings) and registers
        new or updated agents into the discovery service.

        Args:
            network_envelopes: A list of JSON strings, each representing an AgentCardV4 envelope.
        """
        # Note: fetch_cards already handles parsing and skipping invalid/self cards implicitly if logic allows,
        # but fetch_cards in V4 just registers what is valid.
        await self.discovery.fetch_cards(network_envelopes=network_envelopes)
