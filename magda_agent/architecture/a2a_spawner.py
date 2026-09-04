"""
A2A Spawner Module.

This module provides the A2ASpawner class, which extends the base SubagentSpawner
to support delegating subagent creation/execution directly to discovered local peers
using their Agent Cards over the A2A standard via httpx.
"""

import os
import logging
from typing import List, Dict, Any
import httpx

from magda_agent.architecture.subagent_spawning import SubagentSpawner
from magda_agent.integration.a2a_discovery import A2ADiscovery
from magda_agent.integration.a2a_tracing import A2ATracer
from magda_agent.architecture.a2a_handshake import A2AHandshakeProtocol


class A2ASpawner(SubagentSpawner):
    """
    Spawns subagents by delegating tasks to remote peers discovered via A2ADiscovery.
    Inherits context compression logic from SubagentSpawner.
    """

    def __init__(self, discovery: A2ADiscovery, max_context_tokens: int = 4000) -> None:
        """
        Initialize the A2ASpawner.

        Args:
            discovery: The A2ADiscovery instance used to find peers.
            max_context_tokens: Maximum allowed token threshold for context.
        """
        super().__init__(max_context_tokens=max_context_tokens)
        self.discovery = discovery
        self.handshake_protocol = A2AHandshakeProtocol(os.getenv('A2A_SECRET_KEY', 'dev_default_key'))

    async def spawn_a2a_subagent(
        self,
        task_description: str,
        capability_required: str,
        full_context: List[Dict[str, Any]]
    ) -> str:
        """
        Spawns a subagent on a remote peer capable of fulfilling the required capability.

        Args:
            task_description: A description of the task to perform.
            capability_required: The capability required to perform the task.
            full_context: The execution context (typically a list of messages).

        Returns:
            A result string describing the outcome of the delegation.
        """
        # Compress the context
        compressed_context = self.compress_context(full_context)

        # Build execution context
        execution_context = compressed_context.copy()
        execution_context.append({
            "role": "user",
            "content": f"Task: {task_description}"
        })

        # Find agents with the required capability
        agents = self.discovery.find_agents_by_capability(capability_required)
        if not agents:
            logging.warning(f"No agents found for capability: {capability_required}")
            return "No agent found"

        # Select the first available agent
        target_agent = agents[0]

        logging.info(f"Delegating A2A subagent task to Agent: {target_agent.name} (ID: {target_agent.agent_id})")

        endpoint = target_agent.endpoints.get("mcp")
        if not endpoint:
            return f"Agent {target_agent.name} missing MCP endpoint"

        local_id = getattr(getattr(self.discovery, 'local_card', None), 'agent_id', "unknown_local")

        # Generate handshake
        handshake_payload = self.handshake_protocol.create_handshake(
            local_id,
            target_agent.agent_id,
            {"context": execution_context}
        )

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "execute_subplan",
            "params": {

                "context": execution_context,
                "_a2a_handshake": handshake_payload
            }
        }

        headers: Dict[str, str] = {}

        # Inject distributed tracing headers
        A2ATracer.inject_headers(headers)

        # Use discovery's security context if available
        if hasattr(self.discovery, 'security_context') and self.discovery.security_context:
            token = self.discovery.security_context.generate_token()
            headers["Authorization"] = f"Bearer {token}"
            self.discovery.security_context.trace_action(
                "spawn_a2a_subagent",
                { "target_agent": target_agent.name}
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                result = data.get("result", {})
                return f"Delegated to Agent {target_agent.name}: {result.get('status', 'Success')}"
        except Exception as e:
            logging.error(f"Failed to delegate to {target_agent.name} at {endpoint}: {e}")
            return f"Delegation to {target_agent.name} failed: {e}"
