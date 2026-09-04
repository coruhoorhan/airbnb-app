from typing import Dict, Any, List
import logging
from magda_agent.integration.a2a_mdns import A2AMDNSDiscovery
from magda_agent.integration.a2a_delegation import A2ADelegator

class A2AOrchestratorMDNS:
    """
    Coordinates dispatching tasks to multiple A2A sub-agents using A2AMDNSDiscovery for peer discovery.
    """
    def __init__(self, discovery: A2AMDNSDiscovery, delegator: A2ADelegator) -> None:
        """
        Initializes the orchestrator with mDNS discovery and delegator components.

        Args:
            discovery: The A2AMDNSDiscovery instance.
            delegator: The A2ADelegator instance.
        """
        self.discovery = discovery
        self.delegator = delegator

    async def execute_plan(self, plan: list[Dict[str, Any]]) -> Dict[str, str]:
        """
        Executes a full plan by splitting it into sub-plans and dispatching them dynamically
        to peers discovered via mDNS.

        Args:
            plan: The full execution plan.

        Returns:
            A dictionary mapping step IDs to their delegation result.
        """
        if not plan:
            return {}

        results: Dict[str, str] = {}
        sub_plans = self.delegator.split_plan(plan)

        for sub_plan in sub_plans:
            capability = sub_plan.get("capability")
            if not capability:
                logging.warning("Sub-plan missing 'capability'. Skipping.")
                continue

            steps = sub_plan.get("steps", [])
            agents = self.discovery.find_agents_by_capability(capability)

            for step in steps:
                step_id = step.get("id")
                if not step_id:
                    continue

                if not agents:
                    logging.warning(f"No agents found for capability: {capability}")
                    results[step_id] = f"No agent found with capability: {capability}"
                else:
                    target_agent = agents[0]
                    logging.info(f"Delegating step {step_id} to Agent: {target_agent.name} (ID: {target_agent.agent_id}) for capability: {capability}")

                    try:
                        result = await self.delegator.delegate_to_peer(target_agent, step)
                        results[step_id] = result
                    except Exception as e:
                        logging.error(f"Error delegating step {step_id} to {target_agent.name}: {e}")
                        results[step_id] = f"Delegation error: {e}"

        return results
