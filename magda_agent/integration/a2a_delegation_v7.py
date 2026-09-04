import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import httpx

from magda_agent.integration.a2a_security import A2ASecurityContext
from magda_agent.integration.a2a_tracing import A2ATracer

logger = logging.getLogger(__name__)

@dataclass
class AgentCardV7:
    """
    Represents the capabilities and identity of an agent in the network, version 7.
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v7"

    def to_json(self) -> str:
        """
        Serializes the AgentCardV7 to a JSON string.

        Returns:
            str: JSON representation of the card.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV7":
        """
        Deserializes an AgentCardV7 from a JSON string.

        Args:
            json_str (str): The JSON string representation of the card.

        Returns:
            AgentCardV7: The deserialized agent card.
        """
        data = json.loads(json_str)
        return cls(**data)

    def has_capability(self, capability: str) -> bool:
        """
        Checks if the agent card has a specific capability.

        Args:
            capability (str): The capability to check for.

        Returns:
            bool: True if the capability exists, False otherwise.
        """
        for cap in self.capabilities:
            if cap == capability or cap.startswith(f"{capability}_"):
                return True
        return False

class A2ADiscoveryRegistryV7:
    """
    A registry to manage external agent discovery using Agent Cards (V7).
    """
    def __init__(self) -> None:
        """
        Initializes the A2ADiscoveryRegistryV7.
        """
        self._registry: Dict[str, AgentCardV7] = {}

    def register_agent(self, card: AgentCardV7) -> None:
        """
        Registers an AgentCardV7 in the registry.

        Args:
            card (AgentCardV7): The agent card to register.
        """
        self._registry[card.agent_id] = card
        logger.info(f"Registered AgentCardV7 for agent_id: {card.agent_id}")

    def find_agents_by_capability(self, capability: str) -> List[AgentCardV7]:
        """
        Finds agents in the registry that match a specific capability.

        Args:
            capability (str): The capability to filter by.

        Returns:
            List[AgentCardV7]: A list of matched agents.
        """
        return [agent for agent in self._registry.values() if agent.has_capability(capability)]

class A2ADelegatorV7:
    """
    Handles peer-to-peer task delegation dynamically using Agent Cards (V7).
    """
    def __init__(
        self,
        discovery_registry: Optional[A2ADiscoveryRegistryV7] = None,
        security_context: Optional[A2ASecurityContext] = None,
        timeout: float = 10.0
    ) -> None:
        """
        Initializes the A2ADelegatorV7.

        Args:
            discovery_registry (Optional[A2ADiscoveryRegistryV7]): An optional registry to manage agent cards.
            security_context (Optional[A2ASecurityContext]): An optional security context.
            timeout (float): The timeout for HTTP requests.
        """
        self.discovery_registry = discovery_registry or A2ADiscoveryRegistryV7()
        self.security_context = security_context or A2ASecurityContext()
        self.timeout = timeout

    async def delegate_task(self, peer_agent: AgentCardV7, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegates a task to a peer agent asynchronously.

        Args:
            peer_agent (AgentCardV7): The agent card of the peer.
            task_payload (Dict[str, Any]): The task details.

        Returns:
            Dict[str, Any]: The result of the delegation.
        """
        endpoint = peer_agent.endpoints.get("rpc") or peer_agent.endpoints.get("mcp")
        if not endpoint:
            logger.error(f"Agent {peer_agent.agent_id} missing endpoint")
            raise ValueError(f"Agent {peer_agent.agent_id} missing endpoint")

        headers: Dict[str, str] = {}
        A2ATracer.inject_headers(headers)

        if self.security_context:
            token = self.security_context.generate_token()
            headers["Authorization"] = f"Bearer {token}"
            self.security_context.trace_action("delegate_task_v7", {"target_agent": peer_agent.name})

        A2ATracer.record_event("peer_delegation_v7", {"target_agent_id": peer_agent.agent_id})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=task_payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delegate task to {peer_agent.agent_id} at {endpoint}: {e}")
            raise

    async def delegate_by_capability(self, capability: str, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-discovers an agent supporting the specified capability and delegates the task to it.

        Args:
            capability (str): The capability to filter by.
            task_payload (Dict[str, Any]): The task details.

        Returns:
            Dict[str, Any]: The result of the delegation.
        """
        matching_agents = self.discovery_registry.find_agents_by_capability(capability)
        if not matching_agents:
            logger.warning(f"No peer agents found with capability: {capability}")
            raise ValueError(f"No peer agents found supporting capability: {capability}")

        target_agent = matching_agents[0]
        logger.info(f"Auto-discovered target peer agent {target_agent.agent_id} for capability {capability}")
        return await self.delegate_task(target_agent, task_payload)
