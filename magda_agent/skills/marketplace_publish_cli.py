"""CLI tool for publishing Magda skills to the agentskills.io marketplace."""

import argparse
import sys
import httpx
from typing import Optional, List

from magda_agent.skills import initialize_skills
from magda_agent.skills.marketplace_exporter import MarketplaceExporter


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser for the publisher CLI."""
    parser = argparse.ArgumentParser(
        description="Publish Magda skills to agentskills.io standard format endpoints."
    )

    parser.add_argument(
        "--endpoint",
        type=str,
        default="https://agentskills.io/api/publish",
        help="The URL endpoint to publish skills to (default: https://agentskills.io/api/publish)",
    )

    parser.add_argument(
        "--auth-token",
        type=str,
        default=None,
        help="Optional authentication token for the marketplace.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, only prints the JSON payload without making a network request.",
    )

    return parser


def publish_skills(endpoint: str, auth_token: Optional[str] = None, dry_run: bool = False) -> int:
    """
    Exports local skills and publishes them to the specified marketplace endpoint.

    Args:
        endpoint: The URL to publish to.
        auth_token: An optional authentication token for the Authorization header.
        dry_run: Whether to skip the actual network request and just print.

    Returns:
        int: 0 for success, non-zero for failure.
    """
    print("Initializing skills registry...")
    registry = initialize_skills()

    print("Exporting skills to agentskills.io format...")
    exporter = MarketplaceExporter(registry)
    payload_str = exporter.export_skills_to_json()

    if dry_run:
        print("\n--- DRY RUN: Skill Payload ---")
        print(payload_str)
        print("------------------------------")
        return 0

    print(f"Publishing skills to {endpoint}...")
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        response = httpx.post(endpoint, content=payload_str, headers=headers, timeout=10.0)
        response.raise_for_status()
        print(f"Successfully published skills. Server responded: {response.status_code}")
        return 0
    except httpx.HTTPStatusError as exc:
        print(f"HTTP Error: Server returned {exc.response.status_code} - {exc.response.text}", file=sys.stderr)
        return 1
    except httpx.RequestError as exc:
        print(f"Network Error: Failed to connect to endpoint: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected Error: {exc}", file=sys.stderr)
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    return publish_skills(
        endpoint=args.endpoint,
        auth_token=args.auth_token,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    sys.exit(main())
