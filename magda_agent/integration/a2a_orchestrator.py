from typing import Dict, Any, List
import logging
import asyncio
import httpx
from magda_agent.integration.a2a_discovery import A2ADiscovery
from magda_agent.integration.a2a_delegation import A2ADelegator
from magda_agent.telemetry.a2a_distributed_v7 import A2ADistributedTelemetryV7
from magda_agent.telemetry.a2a_distributed_v8 import A2ADistributedTelemetryV8

class A2AOrchestrator:
    """
    Coordinates dispatching tasks to multiple A2A sub-agents using A2ADelegator.
    Supports concurrent delegation for parallelizable tasks.
    """
    def __init__(self, discovery: A2ADiscovery, delegator: A2ADelegator, telemetry: A2ADistributedTelemetryV7 = None, telemetry_v8: A2ADistributedTelemetryV8 = None):
        """
        Initializes the orchestrator with discovery and delegator components.
        """
        self.discovery = discovery
        self.delegator = delegator
        self.telemetry = telemetry
        self.telemetry_v8 = telemetry_v8

    async def dispatch_concurrently(self, sub_plans: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Dispatches multiple sub-plans concurrently to peer agents.

        Args:
            sub_plans: A list of sub-plans (where each sub-plan is a dict containing capability and steps).

        Returns:
            A dictionary mapping step IDs to their delegation result.
        """
        results = {}
        tasks = []

        if self.telemetry:
            self.telemetry.track_event(
                "orchestrator",
                "concurrent_delegation_start",
                {"num_sub_plans": len(sub_plans)}
            )
        if self.telemetry_v8:
            self.telemetry_v8.track_event(
                "orchestrator",
                "concurrent_delegation_start",
                {"num_sub_plans": len(sub_plans)}
            )

        async def _delegate_and_record(capability: str, step: Dict[str, Any]):
            step_id = step.get("id")
            result = await self.delegator.delegate_subplan(capability, step)
            return step_id, result

        for sub_plan in sub_plans:
            capability = sub_plan.get("capability")
            for step in sub_plan.get("steps", []):
                tasks.append(_delegate_and_record(capability, step))

        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = 0
        failure_count = 0

        for idx, result in enumerate(completed_tasks):
            if isinstance(result, Exception):
                logging.error(f"Error during concurrent delegation: {result}")
                failure_count += 1
                # We can't easily get the step_id here if the exception happened outside of our inner wrapper,
                # but because we wrapped it, we should get (step_id, exception/result) unless the wrapper itself failed.
            else:
                step_id, delegation_result = result
                if step_id:
                    results[step_id] = delegation_result
                    success_count += 1

        if self.telemetry:
            self.telemetry.track_event(
                "orchestrator",
                "concurrent_delegation_end",
                {"success_count": success_count, "failure_count": failure_count}
            )
        if self.telemetry_v8:
            self.telemetry_v8.track_event(
                "orchestrator",
                "concurrent_delegation_end",
                {"success_count": success_count, "failure_count": failure_count}
            )

        return results

    async def execute_orchestrated_plan(self, plan: List[Dict[str, Any]], concurrent: bool = False) -> Dict[str, str]:
        """
        Executes a full plan by splitting it into sub-plans and dispatching them either concurrently or sequentially.
        Directly executes MCP action tools when 'skill' is 'execute_mcp_tool'.

        Args:
            plan: The full execution plan.
            concurrent: If True, dispatches sub-plans concurrently. If False, executes them sequentially.

        Returns:
            A dictionary mapping step IDs to their delegation result.
        """
        if not plan:
            return {}

        results = {}
        delegation_plan = []
        mcp_tasks = []

        for step in plan:
            skill = step.get("skill")
            if skill == "execute_mcp_tool":
                if not concurrent and delegation_plan:
                    res = await self.delegator.execute_plan(delegation_plan)
                    results.update(res)
                    delegation_plan = []

                step_id = step.get("id")
                kwargs = step.get("skill_kwargs", {})
                target_agent_id = kwargs.get("target_agent_id")
                tool_name = kwargs.get("tool_name")
                tool_kwargs = kwargs.get("tool_kwargs", {})

                if concurrent:
                    async def _run_mcp(s_id, t_id, t_name, t_kw):
                        r = await self.execute_direct_mcp_action(t_id, t_name, t_kw)
                        return s_id, r
                    mcp_tasks.append(_run_mcp(step_id, target_agent_id, tool_name, tool_kwargs))
                else:
                    result = await self.execute_direct_mcp_action(target_agent_id, tool_name, tool_kwargs)
                    if step_id:
                        results[step_id] = result
            elif skill == "delegate_to_agent":
                delegation_plan.append(step)
            else:
                pass

        if concurrent:
            if delegation_plan:
                sub_plans = self.delegator.split_plan(delegation_plan)
                try:
                    del_results = await self.dispatch_concurrently(sub_plans)
                    results.update(del_results)
                except Exception as e:
                    logging.warning(f"Concurrent delegation failed, falling back to sequential: {e}")
                    res = await self.delegator.execute_plan(delegation_plan)
                    results.update(res)
            if mcp_tasks:
                mcp_completed = await asyncio.gather(*mcp_tasks, return_exceptions=True)
                for res in mcp_completed:
                    if isinstance(res, Exception):
                        logging.error(f"Error during concurrent MCP execution: {res}")
                    else:
                        s_id, r = res
                        if s_id:
                            results[s_id] = r
        else:
            if delegation_plan:
                res = await self.delegator.execute_plan(delegation_plan)
                results.update(res)

        return results

    async def execute_direct_mcp_action(self, target_agent_id: str, tool_name: str, tool_kwargs: Dict[str, Any]) -> str:
        """
        Directly executes an MCP action tool exposed by a peer agent.
        """
        target_agent = self.discovery.get_agent_by_id(target_agent_id)
        if not target_agent:
            return f"Agent {target_agent_id} not found"

        endpoint = target_agent.endpoints.get("mcp")
        if not endpoint:
            return f"Agent {target_agent.name} missing MCP endpoint"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_kwargs
            }
        }

        headers = {}
        security_context = getattr(self.delegator, "security_context", None)
        if security_context:
            token = security_context.generate_token()
            headers["Authorization"] = f"Bearer {token}"
            security_context.trace_action("execute_direct_mcp_action", {
                "target_agent": target_agent.name,
                "tool_name": tool_name
            })

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    return str(data["error"].get("message", str(data["error"])))

                result = data.get("result", {})
                content = result.get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", str(result))
                return str(result)
        except Exception as e:
            logging.error(f"Failed to execute direct MCP action on {target_agent.name} at {endpoint}: {e}")
            return f"MCP action execution on {target_agent.name} failed: {e}"
