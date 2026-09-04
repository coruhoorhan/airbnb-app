from typing import Dict, Any, List, Optional
import logging
import httpx
from magda_agent.integration.a2a_discovery_v3_unique import A2ADiscoveryServiceV3Unique

logger = logging.getLogger(__name__)

class A2ADelegatorV2:
    """
    A2A Task Delegation Protocol v2.
    Handles discovering peers using a discovery service and formatting
    task payloads for peer-to-peer delegation via API requests.
    """

    def __init__(self, discovery_service: Optional[A2ADiscoveryServiceV3Unique] = None) -> None:
        """
        Initializes the A2ADelegatorV2.

        Args:
            discovery_service: An optional discovery service to use for finding peers.
                               Defaults to A2ADiscoveryServiceV3Unique if none is provided.
        """
        self.discovery_service = discovery_service or A2ADiscoveryServiceV3Unique()

    def discover_peers(self, raw_cards: List[str]) -> None:
        """
        Discovers peers from raw agent card JSON strings and registers them.

        Args:
            raw_cards: A list of JSON strings representing AgentCards.
        """
        self.discovery_service.parse_and_register_cards(raw_cards)

    def format_task_payload(self, task_id: str, capability: str, task_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats a task into a structured JSON-RPC style payload.

        Args:
            task_id: A unique identifier for the task.
            capability: The capability required to execute the task.
            task_parameters: A dictionary of parameters for the task.

        Returns:
            A structured dictionary payload.
        """
        return {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "execute_task",
            "params": {
                "capability": capability,
                "task_parameters": task_parameters
            }
        }

    async def delegate_task(self, task_id: str, capability: str, task_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discovers an appropriate peer and delegates a formatted task to it.

        Args:
            task_id: A unique identifier for the task.
            capability: The capability required to execute the task.
            task_parameters: A dictionary of parameters for the task.

        Returns:
            A dictionary containing the response from the peer or an error structure.
        """
        agents = self.discovery_service.find_agents_by_capability(capability)

        if not agents:
            logger.warning(f"No agents found for capability: {capability}")
            return {"error": f"No agent found for capability: {capability}", "status": "failed"}

        # Select the first available agent
        target_agent = agents[0]

        rpc_endpoint = target_agent.endpoints.get("rpc")
        if not rpc_endpoint:
            logger.error(f"Agent {target_agent.name} is missing an RPC endpoint.")
            return {"error": f"Agent {target_agent.name} missing RPC endpoint", "status": "failed"}

        payload = self.format_task_payload(task_id, capability, task_parameters)

        logger.info(f"Delegating task {task_id} to Agent {target_agent.name} at {rpc_endpoint}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(rpc_endpoint, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Delegation to {target_agent.name} failed due to network error: {e}")
            return {"error": f"Network error: {str(e)}", "status": "failed"}
        except Exception as e:
            logger.error(f"Delegation to {target_agent.name} failed: {e}")
            return {"error": f"Internal error: {str(e)}", "status": "failed"}
