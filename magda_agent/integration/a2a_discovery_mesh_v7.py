import asyncio
import logging
from typing import List, Dict, Any
from dataclasses import asdict
import httpx

from magda_agent.integration.a2a_discovery import A2ADiscovery, AgentCard

class A2ADiscoveryMeshV7:
    """
    Manages an A2A discovery mesh based on the A2A Protocol trend.
    It facilitates finding peers with required capabilities using AgentCards,
    propagates gossip about known peers to other nodes, and allows local
    processing of broadcasted cards via an asyncio Queue.
    """

    def __init__(self, discovery: A2ADiscovery) -> None:
        """
        Initializes the A2ADiscoveryMeshV7.

        Args:
            discovery: The core A2ADiscovery instance containing local_card and _discovered_agents.
        """
        self.discovery = discovery
        self.local_broadcast_queue: asyncio.Queue[List[Dict[str, Any]]] = asyncio.Queue()

    def aggregate_cards(self) -> List[AgentCard]:
        """
        Aggregates the local agent's card and all discovered peer cards.

        Returns:
            A list of AgentCard instances known to this mesh node.
        """
        cards = [self.discovery.local_card]
        cards.extend(list(self.discovery._discovered_agents.values()))
        return cards

    async def broadcast_gossip(self, endpoint_urls: List[str]) -> None:
        """
        Broadcasts all known agent cards (gossip) to the specified endpoints.
        Also puts the aggregated cards into the local_broadcast_queue so they
        are received locally.

        Args:
            endpoint_urls: A list of HTTP endpoints (e.g., 'http://192.168.1.10:8000/gossip') to send the cards to.
        """
        aggregated_cards = self.aggregate_cards()
        cards_data = [asdict(card) for card in aggregated_cards]

        # Enqueue for local reception
        await self.local_broadcast_queue.put(cards_data)

        async with httpx.AsyncClient() as client:
            for url in endpoint_urls:
                try:
                    response = await client.post(url, json=cards_data)
                    response.raise_for_status()
                    logging.info(f"Successfully gossiped {len(aggregated_cards)} cards to {url}")
                except Exception as e:
                    logging.error(f"Failed to gossip cards to {url}: {e}")

    def receive_gossip(self, cards_data: List[Dict[str, Any]]) -> None:
        """
        Receives gossip data (a list of agent card dictionaries) and registers
        new or updated agents into the discovery service.

        Args:
            cards_data: A list of dictionaries, each representing an AgentCard.
        """
        registered_count = 0
        for card_dict in cards_data:
            try:
                card = AgentCard(**card_dict)
                # Don't register ourselves if we receive our own card back
                if card.agent_id != self.discovery.local_card.agent_id:
                    self.discovery._register_agent(card)
                    registered_count += 1
            except Exception as e:
                logging.error(f"Failed to parse or register agent card from gossip: {e}")

        logging.info(f"Registered {registered_count} cards from gossip.")
