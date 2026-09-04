"""
MCP Subagent Pattern V2.

This module provides the MCPSubagentV2 class which orchestrates
the execution of MCP action tools within a dedicated isolated subagent context,
inspired by Agent Teams trends.
"""

import logging
from typing import List, Dict, Any, Optional
from magda_agent.architecture.subagent_spawning import SubagentSpawner

logger = logging.getLogger(__name__)


class MCPSubagentV2:
    """
    Orchestrates the execution of an MCP action tool inside a dedicated isolated subagent.
    """

    def __init__(self, spawner: Optional[SubagentSpawner] = None) -> None:
        """
        Initialize the MCPSubagentV2.

        Args:
            spawner: Optional SubagentSpawner instance. If not provided, a new one is created.
        """
        self.spawner = spawner or SubagentSpawner()

    async def execute_mcp_tool_isolated(
        self,
        mcp_tool_name: str,
        tool_kwargs: Dict[str, Any],
        context: List[Dict[str, Any]],
        agent_executor: Any,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Execute an MCP tool inside an isolated subagent.

        Args:
            mcp_tool_name: The name of the MCP tool to execute.
            tool_kwargs: The keyword arguments to pass to the tool.
            context: The conversation or execution context to pass to the subagent.
            agent_executor: An executor instance (e.g., capable of executing the MCP tool)
                            which will be used by the spawner to run the subagent task.
            agent_id: Optional unique identifier for the subagent.

        Returns:
            The result returned by the subagent's execution of the tool, or an Exception if execution failed.
        """
        # Create a specific task description for the subagent regarding this tool
        task_description = f"Execute MCP tool '{mcp_tool_name}' with arguments {tool_kwargs}"

        logger.info(f"Spawning isolated subagent for MCP tool: {mcp_tool_name}")

        try:
            # We use the subagent spawner to execute the task in isolation.
            # The agent_executor provided is expected to handle the actual tool execution logic.
            result = await self.spawner.spawn_subagent(
                task_description=task_description,
                full_context=context,
                agent_executor=agent_executor,
                agent_id=agent_id,
                merge_results=False # Explicitly do not merge results back automatically for tool calls, we just want the output
            )
            return result
        except Exception as e:
            logger.error(f"Execution of MCP tool '{mcp_tool_name}' in subagent failed: {e}")
            return e
