import asyncio
import logging
import httpx

from magda_agent.skills.mcp_registry_v5 import MCPRegistryV5
from magda_agent.scheduler.cron_scheduler_v2 import CronSchedulerV2


logger = logging.getLogger(__name__)


class MCPMarketplacePoller:
    """
    A background job that periodically syncs with an agentskills.io-like
    marketplace to dynamically register external MCP tools.
    """

    def __init__(self, registry: MCPRegistryV5, scheduler: CronSchedulerV2, marketplace_url: str = "https://api.agentskills.io/v1/tools", cron_expr: str = "0 * * * *") -> None:
        """
        Initialize the MCPMarketplacePoller.

        Args:
            registry: The MCPRegistryV5 instance to register valid tools into.
            scheduler: The CronSchedulerV2 instance to schedule the polling job.
            marketplace_url: The URL to fetch MCP tools from.
            cron_expr: Cron expression for how often to sync. Default is hourly ("0 * * * *").
        """
        self.registry = registry
        self.scheduler = scheduler
        self.marketplace_url = marketplace_url
        self.cron_expr = cron_expr
        self.client = httpx.AsyncClient()

    def schedule_sync(self) -> None:
        """
        Registers the sync job with the scheduler.
        """
        self.scheduler.add_task("mcp_marketplace_sync", self.cron_expr, self.sync_marketplace)
        logger.info(f"Scheduled MCP Marketplace sync for {self.marketplace_url} with cron {self.cron_expr}")

    async def sync_marketplace(self) -> None:
        """
        Fetches tools from the marketplace and registers them in the local registry.
        """
        logger.info(f"Starting MCP Marketplace sync from {self.marketplace_url}...")
        try:
            response = await self.client.get(self.marketplace_url, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                logger.warning(f"Marketplace sync failed: Expected JSON list, got {type(data)}")
                return

            registered_count = 0
            for item in data:
                if isinstance(item, dict) and "name" in item and "description" in item and "parameters" in item:
                    # Attempt to register tool
                    success = self.registry.load_tool(item)
                    if success:
                        registered_count += 1
                else:
                    logger.debug(f"Skipping malformed item: {item}")

            logger.info(f"MCP Marketplace sync complete. Registered {registered_count} tools.")

        except httpx.HTTPError as e:
            logger.error(f"Network error during MCP Marketplace sync: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during MCP Marketplace sync: {e}", exc_info=True)

    async def close(self) -> None:
        """Close the internal HTTP client."""
        await self.client.aclose()
