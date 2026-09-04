from typing import Dict, List, Optional
import json
import logging
from dataclasses import dataclass, asdict
from magda_agent.integration.a2a_security import A2ASecurityContext


@dataclass
class AgentCardV2:
    """
    Represents the capabilities and identity of an agent in the network, version 2.
    Inspired by Google/Linux Foundation A2A Standard, June 2026 trends.
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v2"

    def to_json(self) -> str:
        """
        Serializes the AgentCardV2 to a JSON string.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV2":
        """
        Deserializes an AgentCardV2 from a JSON string.
        """
        data = json.loads(json_str)
        return cls(**data)


class A2ADiscoveryV2:
    """
    Handles discovery of other agents in the network and broadcasting
    the local agent's capabilities using the v2 protocol.
    """
    def __init__(self, local_card: AgentCardV2, security_context: Optional[A2ASecurityContext] = None) -> None:
        """
        Initializes the discovery module with the local agent's card.
        """
        self.local_card = local_card
        self.security_context = security_context or A2ASecurityContext()
        self._discovered_agents: Dict[str, AgentCardV2] = {}
        self._capability_index: Dict[str, List[str]] = {}

    async def broadcast_card(self) -> str:
        """
        Broadcasts the local agent's card to the network in an envelope format.
        """
        logging.info(f"Broadcasting Agent Card V2: {self.local_card.name}")

        # In a real system, this would be an actual network broadcast
        envelope = {
            "type": "a2a_discovery_broadcast",
            "version": "2.0",
            "payload": self.local_card.to_json()
        }
        return json.dumps(envelope)

    async def fetch_cards(self, network_envelopes: Optional[List[str]] = None, auth_token: Optional[str] = None) -> None:
        """
        Fetches Agent Cards from the network envelopes and indexes them.
        Requires an auth_token for secure discovery.
        """
        if auth_token and not self.security_context.validate_token(auth_token):
            logging.error("Invalid auth token for fetch_cards")
            raise ValueError("Invalid authentication token")

        self.security_context.trace_action("fetch_cards_v2", {"count": len(network_envelopes) if network_envelopes else 0})

        if network_envelopes is None:
            network_envelopes = []

        for envelope_json in network_envelopes:
            try:
                envelope = json.loads(envelope_json)
                if envelope.get("type") == "a2a_discovery_broadcast" and envelope.get("version") == "2.0":
                    payload = envelope.get("payload", "{}")
                    if isinstance(payload, dict):
                        payload = json.dumps(payload)
                    card = AgentCardV2.from_json(payload)
                    self._register_agent(card)
            except Exception as e:
                logging.error(f"Failed to parse Agent Card Envelope V2: {e}")

    def _register_agent(self, card: AgentCardV2) -> None:
        """
        Registers a discovered agent internally and updates the capability index.
        """
        self._discovered_agents[card.agent_id] = card
        for capability in card.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = []
            if card.agent_id not in self._capability_index[capability]:
                self._capability_index[capability].append(card.agent_id)
        logging.info(f"Discovered Agent V2: {card.name} with capabilities {card.capabilities}")

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentCardV2]:
        """
        Retrieves a discovered agent's card by its ID.
        """
        return self._discovered_agents.get(agent_id)

    def find_agents_by_capability(self, capability: str, prefix_match: bool = False) -> List[AgentCardV2]:
        """
        Returns a list of Agent Cards that support the given capability.
        Supports optional prefix matching for capability strings.
        """
        if not prefix_match:
            agent_ids = self._capability_index.get(capability, [])
            return [self._discovered_agents[aid] for aid in agent_ids]

        matching_agents = []
        for card in self._discovered_agents.values():
            if any(c == capability or c.startswith(capability) for c in card.capabilities):
                matching_agents.append(card)
        return matching_agents

    def find_agents_by_capabilities(
        self, capabilities: List[str], match_all: bool = True, prefix_match: bool = False
    ) -> List[AgentCardV2]:
        """
        Returns a list of Agent Cards that support the given list of capabilities.
        If match_all is True, the agent must support all specified capabilities.
        If match_all is False, the agent must support at least one of the specified capabilities.
        Supports optional prefix matching.
        """
        if not capabilities:
            return list(self._discovered_agents.values())

        matching_agents = []
        for card in self._discovered_agents.values():
            if prefix_match:
                matches = [
                    any(c == req or c.startswith(req) for c in card.capabilities)
                    for req in capabilities
                ]
                if match_all and all(matches):
                    matching_agents.append(card)
                elif not match_all and any(matches):
                    matching_agents.append(card)
            else:
                card_caps = set(card.capabilities)
                req_caps = set(capabilities)
                if match_all and req_caps.issubset(card_caps):
                    matching_agents.append(card)
                elif not match_all and req_caps.intersection(card_caps):
                    matching_agents.append(card)
        return matching_agents

    def discover_workflow_subagents(
        self,
        required_capabilities: List[str],
        optional_capabilities: Optional[List[str]] = None,
        prefix_match: bool = True,
    ) -> List[Dict[str, object]]:
        """
        Discovers subagents suitable for workflow delegation based on required and optional capabilities.
        Returns a list of dictionary descriptors containing the agent card and a score.
        """
        optional_capabilities = optional_capabilities or []
        candidates = self.find_agents_by_capabilities(
            required_capabilities, match_all=True, prefix_match=prefix_match
        )

        results = []
        for card in candidates:
            score = 100.0
            if optional_capabilities:
                opt_matches = sum(
                    1
                    for opt in optional_capabilities
                    if any(
                        c == opt or (prefix_match and c.startswith(opt))
                        for c in card.capabilities
                    )
                )
                score += (opt_matches / len(optional_capabilities)) * 50.0

            results.append({
                "card": card,
                "agent_id": card.agent_id,
                "score": score,
                "matched_required": required_capabilities,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def select_subagent_for_workflow_task(
        self,
        required_capabilities: List[str],
        optional_capabilities: Optional[List[str]] = None,
        prefix_match: bool = True,
    ) -> Optional[AgentCardV2]:
        """
        Selects the single best subagent for a workflow task, or None if no candidate satisfies required capabilities.
        """
        scored_subagents = self.discover_workflow_subagents(
            required_capabilities=required_capabilities,
            optional_capabilities=optional_capabilities,
            prefix_match=prefix_match,
        )
        if not scored_subagents:
            return None
        return scored_subagents[0]["card"]

    async def register_with_registry(self, registry_url: str, auth_token: Optional[str] = None) -> bool:
        """
        Registers the local Agent Card V2 with a central discovery registry.
        """
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{registry_url}/register",
                    json=asdict(self.local_card),
                    headers=headers
                )
                response.raise_for_status()
                logging.info(f"Successfully registered with {registry_url} (v2)")
                return True
        except Exception as e:
            logging.error(f"Failed to register with registry {registry_url}: {e}")
            return False

    async def discover_from_registry(self, registry_url: str, auth_token: Optional[str] = None) -> List[AgentCardV2]:
        """
        Fetches all available Agent Cards from a central discovery registry.
        """
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{registry_url}/cards", headers=headers)
                response.raise_for_status()
                cards_data = response.json()

                discovered = []
                for card_data in cards_data:
                    card = AgentCardV2(**card_data)
                    self._register_agent(card)
                    discovered.append(card)

                logging.info(f"Discovered {len(discovered)} agents from {registry_url} (v2)")
                return discovered
        except Exception as e:
            logging.error(f"Failed to discover from registry {registry_url}: {e}")
            return []
