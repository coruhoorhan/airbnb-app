from typing import Dict, List, Optional, Any
import logging
import httpx
from magda_agent.integration.a2a_discovery import A2ADiscovery, AgentCard
from magda_agent.integration.a2a_orchestrator import A2AOrchestrator

class A2APeerDiscoveryServiceV10:
    """
    Service to register, rank, and map tasks to discovered external A2A agents (v10).
    Inspired by A2A standard from Google/Linux foundation: Implement mesh agent cards discovery.
    """

    def __init__(self, discovery: A2ADiscovery, orchestrator: A2AOrchestrator) -> None:
        """
        Initializes the A2APeerDiscoveryServiceV10.
        """
        self.discovery = discovery
        self.orchestrator = orchestrator

    async def register_and_rank_peers(self, external_cards: List[AgentCard]) -> None:
        """
        Registers external Agent Cards and optionally ranks them.
        """
        for card in external_cards:
            self.discovery._register_agent(card)
        logging.info(f"Registered {len(external_cards)} external peers.")

    def map_task_to_peer(self, task_constraints: Dict[str, Any]) -> Optional[AgentCard]:
        """
        Maps task constraints to a discovered peer agent.
        """
        required_capability = task_constraints.get("required_capability")
        if not required_capability:
            return None

        agents = self.discovery.find_agents_by_capability(required_capability)
        if not agents:
            return None

        # Basic ranking: return the first matched agent
        return agents[0]

    async def discover_peers_via_mdns(self, mdns_endpoint: str) -> List[AgentCard]:
        """
        Simulates discovering peers via mDNS/API.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(mdns_endpoint)
                response.raise_for_status()
                data = response.json()
                cards = [AgentCard.from_json(card_json) for card_json in data.get("cards", [])]
                await self.register_and_rank_peers(cards)
                return cards
        except Exception as e:
            logging.error(f"Error discovering peers via mDNS: {e}")
            return []
