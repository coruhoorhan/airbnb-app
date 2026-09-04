from typing import Dict, Any
import logging
from magda_agent.integration.a2a_discovery import A2ADiscovery
from magda_agent.integration.a2a_delegation import A2ADelegator


class A2AOrchestratorV2:
    """
    Coordinates dispatching tasks to multiple A2A sub-agents using A2ADelegator natively via Agent Cards.
    """
    def __init__(self, discovery: A2ADiscovery, delegator: A2ADelegator):
        """
        Initializes the orchestrator with discovery and delegator components.
        """
        self.discovery = discovery
        self.delegator = delegator

    async def route_task(self, task_context: Dict[str, Any], required_capability: str) -> str:
        """
        Discovers an available agent with the required capability and delegates the task to it.

        Args:
            task_context: The task context or sub-plan to delegate.
            required_capability: The capability required to execute the task.

        Returns:
            A result string describing the outcome.
        """
        agents = self.discovery.find_agents_by_capability(required_capability)

        if not agents:
            logging.warning(f"No agents found for capability: {required_capability}")
            return f"No agent found with capability: {required_capability}"

        target_agent = agents[0]

        logging.info(f"Routing task to Agent: {target_agent.name} (ID: {target_agent.agent_id}) for capability: {required_capability}")

        result = await self.delegator.delegate_to_peer(target_agent, task_context)

        return result
