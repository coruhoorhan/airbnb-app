"""
Bridge to register Magda skills exported via MCPSkillExporter directly into an MCPRegistryV7.
"""
from typing import Any, Dict
import logging

from magda_agent.skills.registry import SkillRegistry
from magda_agent.skills.mcp_exporter import MCPSkillExporter
from magda_agent.skills.mcp_registry_v7 import MCPRegistryV7

class MCPRegistryBridge:
    """
    Bridge that connects Magda's local SkillRegistry to the external MCPRegistryV7.
    It takes skills generated and formatted by MCPSkillExporter and registers them
    as dynamic tools into the MCPRegistryV7.
    """

    def __init__(self, skill_registry: SkillRegistry, skill_exporter: MCPSkillExporter) -> None:
        """
        Initialize the MCPRegistryBridge.

        Args:
            skill_registry (SkillRegistry): The local registry containing dynamically generated skills.
            skill_exporter (MCPSkillExporter): The exporter used to convert skills to MCP tool schemas.
        """
        self.skill_registry = skill_registry
        self.skill_exporter = skill_exporter

    def bridge_skills(self, mcp_registry: MCPRegistryV7) -> int:
        """
        Exports all local skills and registers them into the provided MCPRegistryV7.

        Args:
            mcp_registry (MCPRegistryV7): The destination MCP registry for the tools.

        Returns:
            int: The number of skills successfully registered.
        """
        tools = self.skill_exporter.list_tools()
        registered_count = 0

        for tool_schema in tools:
            success = mcp_registry.register_tool(tool_schema)
            if success:
                registered_count += 1
                logging.info(f"Bridged skill '{tool_schema.get('name')}' to MCP Registry.")
            else:
                logging.error(f"Failed to bridge skill '{tool_schema.get('name')}' to MCP Registry.")

        return registered_count
