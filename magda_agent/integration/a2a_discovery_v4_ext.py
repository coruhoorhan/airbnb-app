from typing import List, Optional, Set
import logging
from magda_agent.integration.a2a_discovery_v4 import A2ADiscoveryRegistryV4, AgentCardV4

class A2ADiscoveryRegistryV4Ext(A2ADiscoveryRegistryV4):
    """
    Extended A2A discovery registry that supports advanced capability matching and querying.
    Inspired by A2A Protocol capability-based delegation trends.
    """

    def filter_by_capabilities(self, required_capabilities: List[str]) -> List[AgentCardV4]:
        """
        Filters all registered agents and returns only those that support
        all of the specified capabilities.

        Args:
            required_capabilities: A list of capabilities strings to match against.

        Returns:
            A list of AgentCardV4 instances that possess the required capabilities.
        """
        if not required_capabilities:
            return self.get_all_agents()

        required_set = set(required_capabilities)
        matched_agents = []
        for agent in self.get_all_agents():
            agent_caps_set = set(agent.capabilities)
            if required_set.issubset(agent_caps_set):
                matched_agents.append(agent)

        return matched_agents

    def find_agent_for_delegation(self, required_capabilities: List[str], exclude_agent_id: Optional[str] = None) -> Optional[AgentCardV4]:
        """
        Finds an optimal agent for delegating a task that requires specific capabilities.

        Args:
            required_capabilities: A list of capabilities the agent must support.
            exclude_agent_id: Optional agent ID to exclude (typically the caller's own ID).

        Returns:
            An AgentCardV4 if a suitable agent is found, otherwise None.
        """
        matched_agents = self.filter_by_capabilities(required_capabilities)

        if exclude_agent_id:
            matched_agents = [agent for agent in matched_agents if agent.agent_id != exclude_agent_id]

        if matched_agents:
            # We can implement a more complex routing strategy here (e.g. least loaded, lowest latency)
            # For now, simply return the first match.
            logging.info(f"Found suitable agent {matched_agents[0].agent_id} for capabilities {required_capabilities}")
            return matched_agents[0]

        logging.warning(f"No suitable agent found for capabilities {required_capabilities}")
        return None
