import logging
from typing import Any, Callable, Dict, List, Protocol, Optional

from magda_agent.architecture.context_hooks_v5 import HookRegistry


class ContextPluginV8(Protocol):
    """
    Protocol for OpenClaw Context Engine Plugins V8.
    Defines lifecycle hooks for memory context management.
    """

    async def bootstrap(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        ...

    async def pre_process(self, content: str, metadata: Dict[str, Any]) -> str:
        """Process content before it is ingested or used."""
        ...

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """Ingest new content into the memory system."""
        ...

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """Assemble a list of context items into a string format."""
        ...

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """Compact or summarize context items to fit within limits."""
        ...

    async def post_process(self, response: str, metadata: Dict[str, Any]) -> str:
        """Process the final response before returning."""
        ...


class ContextEngineV8:
    """
    Context Engine Architecture V8.
    Manages plugins and executes lifecycle hooks using a HookRegistry.
    """

    def __init__(self, hook_registry: Optional[HookRegistry] = None) -> None:
        """
        Initialize ContextEngineV8.

        Args:
            hook_registry: Optional HookRegistry instance to use. If not provided,
                           a new one is created.
        """
        self.hook_registry = hook_registry or HookRegistry()

    def register_plugin(self, plugin: ContextPluginV8) -> None:
        """
        Register a ContextPluginV8.
        Registers the plugin's methods with the HookRegistry.

        Args:
            plugin: The plugin instance to register.
        """
        if hasattr(plugin, 'bootstrap'):
            self.hook_registry.register_hook('bootstrap', plugin.bootstrap)
        if hasattr(plugin, 'pre_process'):
            self.hook_registry.register_hook('pre_process', plugin.pre_process)
        if hasattr(plugin, 'ingest'):
            self.hook_registry.register_hook('ingest', plugin.ingest)
        if hasattr(plugin, 'assemble'):
            self.hook_registry.register_hook('assemble', plugin.assemble)
        if hasattr(plugin, 'compact'):
            self.hook_registry.register_hook('compact', plugin.compact)
        if hasattr(plugin, 'post_process'):
            self.hook_registry.register_hook('post_process', plugin.post_process)

        logging.debug(f"Registered plugin V8: {plugin.__class__.__name__}")

    async def bootstrap_all(self, config: Dict[str, Any]) -> None:
        """
        Run the bootstrap hook on all registered plugins.

        Args:
            config: Configuration dictionary to pass to plugins.
        """
        config_with_hooks: Dict[str, Any] = dict(config)
        config_with_hooks["hook_registry"] = self.hook_registry
        await self.hook_registry.trigger_broadcast_async('bootstrap', config_with_hooks)

    async def pre_process(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Execute the pre_process pipeline on content.

        Args:
            content: The input content.
            metadata: Additional metadata.

        Returns:
            The processed content string.
        """
        return await self.hook_registry.trigger_hook_async('pre_process', content, metadata)

    async def ingest(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Execute the ingest pipeline.

        Args:
            content: The input content.
            metadata: Additional metadata.

        Returns:
            The ingested content string.
        """
        return await self.hook_registry.trigger_hook_async('ingest', content, metadata)

    async def assemble(self, context_items: List[Any], metadata: Dict[str, Any]) -> str:
        """
        Execute the assemble hook to build context.

        Args:
            context_items: List of items to assemble.
            metadata: Additional metadata.

        Returns:
            The assembled context string.
        """
        if 'assemble' not in self.hook_registry._hooks or not self.hook_registry._hooks['assemble']:
            return "\n".join([str(item) for item in context_items])

        return await self.hook_registry.trigger_broadcast_async('assemble', context_items, metadata)

    async def compact(self, context_items: List[Any], metadata: Dict[str, Any]) -> List[Any]:
        """
        Execute the compact pipeline to reduce context size.

        Args:
            context_items: List of items to compact.
            metadata: Additional metadata (e.g., limit).

        Returns:
            The compacted list of context items.
        """
        current_items = await self.hook_registry.trigger_hook_async('compact', context_items, metadata)

        limit = metadata.get("limit", 10)
        if len(current_items) > limit:
            logging.info("Context length exceeds limit after plugins. Using ContextEngineV8 built-in fallback compaction.")
            # Drop older items (keep recent)
            current_items = current_items[-limit:]

        return current_items

    async def post_process(self, response: str, metadata: Dict[str, Any]) -> str:
        """
        Execute the post_process pipeline on the response.

        Args:
            response: The response to process.
            metadata: Additional metadata.

        Returns:
            The processed response string.
        """
        return await self.hook_registry.trigger_hook_async('post_process', response, metadata)
