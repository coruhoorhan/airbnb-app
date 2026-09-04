"""CLI command for syncing external skills from agentskills.io into the local registry."""

import argparse
import asyncio
import logging
import sys
from typing import Optional, List

from magda_agent.skills.registry import SkillRegistry
from magda_agent.skills.marketplace_sync_v4 import MarketplaceSyncRoutineV4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parses command-line arguments for the marketplace sync CLI.

    Args:
        argv: Optional list of command-line arguments.

    Returns:
        The parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Sync external skills from agentskills.io into the local registry.")
    parser.add_argument(
        "--url",
        default="https://agentskills.io/api/skills",
        help="The URL of the marketplace to fetch from"
    )
    parser.add_argument(
        "--cache",
        default=".skill_cache_v4.json",
        help="File path to save/cache fetched skill definitions locally"
    )
    return parser.parse_args(argv)


async def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the marketplace sync CLI.

    Args:
        argv: Optional list of command-line arguments.

    Returns:
        Integer representing the exit code (0 for success, 1 for failure).
    """
    args = parse_args(argv)

    registry = SkillRegistry()
    sync_routine = MarketplaceSyncRoutineV4(
        registry=registry,
        marketplace_url=args.url,
        cache_path=args.cache
    )

    logger.info(f"Starting one-off sync from {args.url}")
    imported_count = await sync_routine.run_sync_cycle()

    if imported_count > 0:
        logger.info(f"Successfully synced {imported_count} skills.")
        return 0
    else:
        logger.error("Failed to sync any skills.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
