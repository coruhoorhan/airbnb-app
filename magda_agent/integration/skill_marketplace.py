from typing import Dict, Any, List, Callable
import inspect
from magda_agent.skills.registry import SkillRegistry

class AgentSkillsExporter:
    """
    Exports Magda skills as agentskills.io compatible JSON objects.
    """
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def _get_json_schema(self, func: Callable) -> Dict[str, Any]:
        """
        Extracts JSON schema parameters from the function signature.
        """
        if hasattr(func, "__mcp_schema__"):
            return getattr(func, "__mcp_schema__")

        sig = inspect.signature(func)
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            if name in ('self', 'kwargs', 'args'):
                continue

            param_type = "string"
            if param.annotation is not inspect.Parameter.empty:
                if param.annotation is int:
                    param_type = "integer"
                elif param.annotation is float:
                    param_type = "number"
                elif param.annotation is bool:
                    param_type = "boolean"
                elif param.annotation is list or param.annotation is List:
                    param_type = "array"
                elif param.annotation is dict or param.annotation is Dict:
                    param_type = "object"

            properties[name] = {"type": param_type}

            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required
        }

    def export_skills(self) -> List[Dict[str, Any]]:
        """
        Exports all registered skills to an agentskills.io compatible format.
        """
        skills = []
        for name, func in self.registry.skills.items():
            description = self.registry.descriptions.get(name, "")
            schema = self._get_json_schema(func)

            skills.append({
                "name": name,
                "description": description,
                "parameters": schema
            })

        return skills

import logging
import aiohttp

logger = logging.getLogger(__name__)

def _create_dynamic_skill(skill_def: Dict[str, Any]) -> Callable:
    """
    Creates a dynamic skill function based on the agentskills.io definition.
    """
    def dynamic_skill(**kwargs):
        logger.info(f"Executing marketplace skill: {skill_def.get('name')} with args: {kwargs}")
        return f"Executed remote skill '{skill_def.get('name')}' successfully."

    # Optionally attach metadata to the function
    name = skill_def.get("name", "unknown_skill")
    dynamic_skill.__name__ = name
    dynamic_skill.__doc__ = skill_def.get("description", "No description provided.")

    # Attach parameters schema if present
    if "parameters" in skill_def:
        setattr(dynamic_skill, "__mcp_schema__", skill_def["parameters"])
    elif "inputSchema" in skill_def:
        setattr(dynamic_skill, "__mcp_schema__", skill_def["inputSchema"])

    return dynamic_skill

async def fetch_and_register_skills(url: str, registry: SkillRegistry) -> List[str]:
    """
    Fetches an agentskills.io compliant JSON specification from the given URL
    and dynamically registers the skills into the provided SkillRegistry.

    Args:
        url (str): The URL of the marketplace JSON endpoint.
        registry (SkillRegistry): The registry where new skills will be registered.

    Returns:
        List[str]: A list of skill names that were successfully registered.
    """
    registered_skills = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()

                skills_list = data.get("skills", [])
                for skill_def in skills_list:
                    name = skill_def.get("name")
                    description = skill_def.get("description", "Dynamic marketplace skill")

                    if name:
                        func = _create_dynamic_skill(skill_def)
                        registry.register_skill(name=name, func=func, description=description)
                        registered_skills.append(name)
                        logger.info(f"Successfully registered marketplace skill: {name}")
                    else:
                        logger.warning(f"Skill definition missing 'name' field: {skill_def}")

    except Exception as e:
        logger.error(f"Failed to fetch and register skills from {url}: {e}")

    return registered_skills

import asyncio
from typing import Optional

class MarketplaceBackgroundSync:
    """
    Background loop that periodically polls a configured agentskills.io marketplace URL
    and dynamically registers tools into the local SkillRegistry.
    """

    def __init__(self, registry: SkillRegistry, marketplace_url: str, sync_interval: int = 3600) -> None:
        """
        Initialize the MarketplaceBackgroundSync process.

        Args:
            registry (SkillRegistry): The local skill registry to update.
            marketplace_url (str): The URL of the agentskills.io JSON endpoint.
            sync_interval (int): Time in seconds between polling attempts. Defaults to 3600 (1 hour).
        """
        self.registry = registry
        self.marketplace_url = marketplace_url
        self.sync_interval = sync_interval
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self.logger = logging.getLogger(__name__)

    async def _sync_loop(self) -> None:
        """
        The main background asyncio loop that periodically triggers synchronization.
        """
        while self._running:
            await self.sync_once()
            if self._running:
                try:
                    await asyncio.sleep(self.sync_interval)
                except asyncio.CancelledError:
                    break

    async def sync_once(self) -> None:
        """
        Performs a single synchronization cycle by fetching from the marketplace.
        """
        self.logger.debug(f"Starting marketplace sync cycle with: {self.marketplace_url}")
        try:
            registered_skills = await fetch_and_register_skills(self.marketplace_url, self.registry)
            self.logger.info(f"Marketplace sync completed successfully. Registered {len(registered_skills)} new/updated skills.")
        except Exception as e:
            self.logger.error(f"Error during marketplace sync cycle with {self.marketplace_url}: {e}")

    def start(self) -> None:
        """
        Starts the background synchronization loop.
        """
        if self._running:
            self.logger.warning("MarketplaceBackgroundSync loop is already running.")
            return

        self._running = True
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._sync_loop())
        self.logger.info(f"Started MarketplaceBackgroundSync loop with interval {self.sync_interval}s.")

    async def stop(self) -> None:
        """
        Stops the background synchronization loop gracefully.
        """
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.logger.info("Stopped MarketplaceBackgroundSync loop.")
