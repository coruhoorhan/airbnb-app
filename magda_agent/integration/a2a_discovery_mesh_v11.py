from typing import Dict, List, Optional, Any
import logging
from magda_agent.integration.a2a_discovery import A2ADiscovery, AgentCard

class A2ADiscoveryMeshV11:
    """
    Manages an A2A discovery mesh based on the A2A Protocol trend.
    It tracks the state of peers, allows registering new peers, and facilitates finding
    peers with required capabilities using AgentCards.
    """

    def __init__(self, discovery: A2ADiscovery) -> None:
        """
        Initializes the A2ADiscoveryMeshV11.

        Args:
            discovery: The core A2ADiscovery instance.
        """
        self.discovery = discovery
        self.peer_states: Dict[str, str] = {}

    def register_peers(self, cards: List[AgentCard]) -> None:
        """
        Registers multiple external Agent Cards into the mesh.

        Args:
            cards: A list of AgentCard instances to register.
        """
        for card in cards:
            self.discovery._register_agent(card)
            self.peer_states[card.agent_id] = "active"
            logging.info(f"Registered peer in mesh: {card.agent_id}")

    def update_peer_state(self, agent_id: str, state: str) -> None:
        """
        Updates the state of a registered peer in the mesh.

        Args:
            agent_id: The ID of the agent whose state to update.
            state: The new state (e.g., 'active', 'offline', 'busy').
        """
        if agent_id in self.peer_states:
            self.peer_states[agent_id] = state
            logging.info(f"Updated peer state for {agent_id} to {state}")
        else:
            logging.warning(f"Attempted to update state for unknown peer: {agent_id}")

    def get_peer_state(self, agent_id: str) -> Optional[str]:
        """
        Retrieves the state of a registered peer.

        Args:
            agent_id: The ID of the agent.

        Returns:
            The state of the agent if it exists, otherwise None.
        """
        return self.peer_states.get(agent_id)

    def find_best_peer_for_capability(self, capability: str) -> Optional[AgentCard]:
        """
        Finds the most suitable active peer for a required capability.

        Args:
            capability: The required capability.

        Returns:
            The AgentCard of the selected peer, or None if no active peer is found.
        """
        agents = self.discovery.find_agents_by_capability(capability)
        if not agents:
            return None

        # Filter for only active agents
        active_agents = [
            agent for agent in agents
            if self.peer_states.get(agent.agent_id) == "active"
        ]

        if not active_agents:
            return None

        # Return the first active agent as a simple strategy
        return active_agents[0]
