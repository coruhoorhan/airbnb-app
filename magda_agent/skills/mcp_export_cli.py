"""CLI tool to export Magda's active skills as an MCP-compatible JSON schema document."""

from __future__ import annotations

import argparse
import json
import sys

from magda_agent.skills import initialize_skills
from magda_agent.skills.mcp_exporter import MCPSkillExporter


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export active skills as MCP JSON schema")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "export":
        try:
            # Initialize registry with active skills
            registry = initialize_skills()

            # Use MCPSkillExporter to export schemas
            exporter = MCPSkillExporter(registry)
            tools = exporter.list_tools()

            # Print the schema as formatted JSON
            print(json.dumps(tools, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"Failed to export skills: {exc}", file=sys.stderr)
            return 1

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
