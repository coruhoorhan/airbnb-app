from typing import Dict, Any
import logging

class AgentCardV3:
    def __init__(self, agent_id: str, capabilities: list, endpoints: Dict[str, str]):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.endpoints = endpoints

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "capabilities": self.capabilities,
            "endpoints": self.endpoints
        }

class A2ADiscoveryServiceV3Unique:
    def __init__(self, network_interface: Any):
        self.network_interface = network_interface
        self.discovered_agents = {}

    async def broadcast_agent_card(self, card: AgentCardV3) -> None:
        """Broadcasts the agent's capabilities using an Agent Card over the A2A mesh network."""
        payload = card.to_dict()
        logging.info(f"Broadcasting Agent Card for {card.agent_id}")
        await self.network_interface.broadcast(payload)

    def receive_card(self, payload: Dict[str, Any]) -> None:
        """Receives an agent card from the network."""
        agent_id = payload.get("agent_id")
        if agent_id:
            self.discovered_agents[agent_id] = payload
            logging.debug(f"Received Agent Card for {agent_id}")
