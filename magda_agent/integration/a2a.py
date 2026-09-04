from typing import Dict, Any, List, Optional, Union
import logging
import os
from magda_agent.architecture.a2a_handshake import A2AHandshakeProtocol
from magda_agent.integration.a2a_discovery import AgentCard, A2ADiscovery
from magda_agent.integration.a2a_discovery_v2 import AgentCardV2, A2ADiscoveryV2
from magda_agent.integration.a2a_cards import AgentCardV3, A2ADiscoveryV3
from magda_agent.integration.a2a_discovery_v4 import AgentCardV4, A2ADiscoveryRegistryV4
from magda_agent.integration.a2a_delegation import A2ADelegator
from magda_agent.integration.a2a_status_broadcaster import A2AStatusBroadcaster

class A2AManager:
    """
    Orchestrates the discovery of other agents via Agent Cards and the delegation
    of sub-plans/tasks to capable peers in a peer-to-peer network.
    Inspired by A2A Protocol trends.
    """
    def __init__(self, local_card: Union[AgentCard, AgentCardV2, AgentCardV3, AgentCardV4], secret_key: Optional[str] = None) -> None:
        """
        Initializes the manager with the local agent's identity and capabilities.

        Args:
            local_card: The AgentCard, AgentCardV2, AgentCardV3, or AgentCardV4 representing this agent.
        """
        self.handshake_protocol = A2AHandshakeProtocol(secret_key or os.getenv('A2A_SECRET_KEY', 'dev_default_key'))
        self.local_card_version = 1
        if isinstance(local_card, AgentCardV4):
            self.discovery = A2ADiscoveryRegistryV4()
            self.discovery.register_agent(local_card)
            self.local_card = local_card
            self.local_card_version = 4
        elif isinstance(local_card, AgentCardV3):
            self.discovery = A2ADiscoveryV3(local_card=local_card) # type: ignore
        elif isinstance(local_card, AgentCardV2):
            self.discovery = A2ADiscoveryV2(local_card=local_card) # type: ignore
        else:
            self.discovery = A2ADiscovery(local_card=local_card) # type: ignore


        if self.local_card_version != 4:
            self.delegator = A2ADelegator(discovery=self.discovery) # type: ignore
            if self.local_card_version == 1:
                self.broadcaster = A2AStatusBroadcaster(local_card, "http://default-registry/broadcast")
            else:
                self.broadcaster = None


    async def start(self) -> str:
        """
        Starts the manager by broadcasting the local agent's capabilities to the network.

        Returns:
            The JSON representation of the broadcasted AgentCard.
        """
        logging.info("Starting A2AManager and broadcasting local capabilities...")
        if self.local_card_version == 4:
            return self.local_card.to_json()
        return await self.discovery.broadcast_card()

    async def discover_peers(self, mock_network_cards: Optional[List[str]] = None) -> None:
        """
        Discovers peers by fetching their Agent Cards from the network.

        Args:
            mock_network_cards: Optional list of JSON strings representing mocked Agent Cards.
        """
        logging.info("A2AManager discovering peers...")
        if self.local_card_version == 4:
            if mock_network_cards:
                self.discovery.parse_and_register_cards(mock_network_cards)
        elif isinstance(self.discovery, (A2ADiscoveryV2, A2ADiscoveryV3)):
            await self.discovery.fetch_cards(network_envelopes=mock_network_cards)
        else:
            await self.discovery.fetch_cards(mock_network_cards=mock_network_cards)

    def get_known_peers(self) -> Union[List[AgentCard], List[AgentCardV2], List[AgentCardV3], List[AgentCardV4]]:
        """
        Retrieves all currently known peers discovered in the network.

        Returns:
            A list of discovered AgentCard objects.
        """
        if self.local_card_version == 4:
            return self.discovery.get_all_agents()
        return list(self.discovery._discovered_agents.values())

    async def delegate_task(self, capability: str, task_context: Dict[str, Any]) -> str:
        """
        Delegates a task to a discovered peer that supports the required capability.
        """
        logging.info(f"A2AManager attempting to delegate task requiring capability: {capability}")

        # We find a target agent to use for the handshake
        target_agent_id = None

        if self.local_card_version == 4:
            for agent in self.discovery.get_all_agents():
                if capability in agent.capabilities and agent.agent_id != self.local_card.agent_id:
                    target_agent_id = agent.agent_id
                    break
        else:
            local_id = getattr(self.discovery, 'local_card', None)
            local_agent_id = local_id.agent_id if local_id else "unknown_local"
            # Avoid private _discovered_agents if possible, but for v1-v3 this is the pattern used in original code
            # In original code get_known_peers returns list(self.discovery._discovered_agents.values())
            for agent in self.get_known_peers():
                if capability in agent.capabilities and agent.agent_id != local_agent_id:
                    target_agent_id = agent.agent_id
                    break

        # If we found a target, we attach the handshake to the context before proceeding
        if target_agent_id:
            local_id = self.local_card.agent_id if self.local_card_version == 4 else getattr(getattr(self.discovery, 'local_card', None), 'agent_id', "unknown_local")

            # Create a shallow copy of the context for the payload to avoid circular reference
            # when we assign the handshake back to task_context
            context_copy = dict(task_context)
            handshake_payload = self.handshake_protocol.create_handshake(local_id, target_agent_id, context_copy)
            # Use a new dict instead of mutating input
            task_context = dict(task_context)
            task_context["_a2a_handshake"] = handshake_payload

        if self.local_card_version == 4:
            if target_agent_id:
                agent_name = next((a.name for a in self.discovery.get_all_agents() if a.agent_id == target_agent_id), target_agent_id)
                return f"Delegated to Agent {agent_name}"
            return "No agent found"

        return await self.delegator.delegate_subplan(capability, task_context)
    async def broadcast_status(self, is_available: bool, active_tasks: int) -> bool:
        """
        Broadcasts the current agent status using the A2AStatusBroadcaster.
        """
        if hasattr(self, 'broadcaster') and self.broadcaster:
            return await self.broadcaster.broadcast_status(is_available, active_tasks)
        return False
