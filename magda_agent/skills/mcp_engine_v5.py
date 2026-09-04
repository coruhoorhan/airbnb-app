import logging
import asyncio
from typing import Dict, Any, List, Optional
from magda_agent.skills.mcp_client import MCPClient
from magda_agent.skills.registry import SkillRegistry
from magda_agent.memory.context_engine import ContextPlugin

class MCPEngineV5(ContextPlugin):
    """
    Engine to seamlessly import and execute external MCP tools, converting them
    into Magda's native procedural skills dynamically, while strictly following
    the ContextPlugin protocol, with robust fallback mechanisms.
    """
    def __init__(self, registry: SkillRegistry, mcp_client: MCPClient) -> None:
        """
        Initializes the MCPEngineV5.

        Args:
            registry (SkillRegistry): Magda's native skill registry.
            mcp_client (MCPClient): The MCP client used for remote tool execution.
        """
        self.registry = registry
        self.mcp_client = mcp_client
        self.hook_registry: Optional[Any] = None

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        self.hook_registry = config.get("hook_registry")
        logging.info("MCPEngineV5 bootstrapped.")

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process incoming content before it is stored or used."""
        return content

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Assemble the context string from retrieved items for the LLM."""
        return "\n".join([str(item) for item in context_items])

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact or summarize the context when limits are reached."""
        return context_items

    def before_retrieval(self, query: str, user_id: int) -> str:
        """Called before context is retrieved. Can modify the query."""
        return query

    def after_retrieval(self, context: List[Any], query: str, user_id: int) -> List[Any]:
        """Called after context is retrieved. Can modify the retrieved context."""
        return context

    def before_write(self, context: Any, user_id: int) -> Any:
        """Called before context is written. Can modify the context."""
        return context

    def after_write(self, context: Any, user_id: int) -> None:
        """Called after context is written."""
        pass

    def on_context_update(self, new_context: Any, user_id: int) -> None:
        """Called when the overall context is updated."""
        pass

    def import_mcp_tool(
        self,
        tool_def: Dict[str, Any],
        connection_info: Dict[str, Any],
        fallback_tool_name: Optional[str] = None
    ) -> None:
        """
        Reads MCP standard tool definitions and wraps them into Magda's SkillRegistry.

        Args:
            tool_def (Dict[str, Any]): Definition containing at least "name" and "description".
            connection_info (Dict[str, Any]): Information needed to execute the remote tool.
            fallback_tool_name (Optional[str]): A registered skill to execute if remote tool fails.
        """
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("MCP tool definition must include a 'name'.")

        description = tool_def.get("description", "Imported MCP tool.")
        input_schema = tool_def.get("inputSchema", {})

        self.mcp_client.register_remote_tool(tool_name, connection_info)

        async def mcp_wrapper_skill(**kwargs: Any) -> Any:
            """
            Dynamically executes the imported MCP tool via the MCPClient,
            triggering context engine lifecycle hooks before and after tool usage,
            with fallback mechanism for robustness.

            Args:
                kwargs: Arguments to pass to the MCP tool.

            Returns:
                Any: Result of the MCP tool execution or the fallback execution.
            """
            # Trigger before tool usage hook
            if self.hook_registry and hasattr(self.hook_registry, 'trigger_broadcast_async'):
                try:
                    await self.hook_registry.trigger_broadcast_async("before_tool_use", tool_name, kwargs)
                except Exception as e:
                    logging.warning(f"Error triggering before_tool_use hook: {e}")

            result = None
            exception_occurred = False
            try:
                result = await self.mcp_client.execute_tool(tool_name, **kwargs)
            except Exception as e:
                result = str(e)
                exception_occurred = True

            # Check if fallback is needed
            if exception_occurred or (isinstance(result, str) and result.startswith("Error ")):
                if fallback_tool_name and self.registry.has_skill(fallback_tool_name):
                    logging.warning(f"Execution of remote MCP tool '{tool_name}' failed. Attempting fallback to '{fallback_tool_name}'.")
                    fallback_func = self.registry.skills.get(fallback_tool_name)
                    if fallback_func:
                        try:
                            if asyncio.iscoroutinefunction(fallback_func):
                                result = await fallback_func(**kwargs)
                            else:
                                result = fallback_func(**kwargs)
                        except Exception as fb_exc:
                            logging.error(f"Fallback execution of '{fallback_tool_name}' also failed: {fb_exc}")
                            # Result remains the original error
                else:
                    logging.warning(f"Execution of remote MCP tool '{tool_name}' failed, and no fallback tool configured or found.")

            # Trigger after tool usage hook
            if self.hook_registry and hasattr(self.hook_registry, 'trigger_broadcast_async'):
                try:
                    await self.hook_registry.trigger_broadcast_async("after_tool_use", tool_name, result)
                except Exception as e:
                    logging.warning(f"Error triggering after_tool_use hook: {e}")

            if exception_occurred and (not fallback_tool_name or not self.registry.has_skill(fallback_tool_name)):
                # If it was an exception and no fallback was successfully used, we might raise it
                # or just return the string. Based on instructions, return/raise the original error.
                pass # Already set result to string representing error, we can just return it.

            return result

        setattr(mcp_wrapper_skill, "__mcp_schema__", input_schema)
        setattr(mcp_wrapper_skill, "__name__", tool_name)

        self.registry.register_skill(
            name=tool_name,
            func=mcp_wrapper_skill,
            description=description
        )

        logging.info(f"Dynamically wrapped MCP tool '{tool_name}' into Magda skill registry with fallback support.")
