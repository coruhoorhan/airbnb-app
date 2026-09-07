"""
Magda-Agent Backend & E2E CLI / TUI Bridge for Veyyon & Codex.
Manages backend_tasks.json: Database migrations, API routes, security, and E2E test tasks
with subagent dispatch prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_BACKEND_MANIFEST = Path("backend_tasks.json")


def load_backend_manifest(path: Path = DEFAULT_BACKEND_MANIFEST) -> Dict[str, Any]:
    """Load backend tasks manifest from disk."""
    if not path.exists():
        # Fallback to finding in parent or /opt/airbnb-app
        alt_paths = [
            Path("/opt/airbnb-app/backend_tasks.json"),
            Path.cwd() / "backend_tasks.json",
        ]
        for ap in alt_paths:
            if ap.exists():
                path = ap
                break

    if not path.exists():
        return {
            "schema_version": 1,
            "project": "magda-backend-e2e-engine",
            "managed_by": "Veyyon & Codex Subagents",
            "tasks": []
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_backend_manifest(data: Dict[str, Any], path: Path = DEFAULT_BACKEND_MANIFEST) -> None:
    """Save backend tasks manifest to disk."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_todo_tasks(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [t for t in manifest.get("tasks", []) if t.get("status") == "todo"]


def render_subagent_prompt(task: Dict[str, Any]) -> str:
    """Renders a subagent-ready prompt for Veyyon or Codex."""
    title = task.get("title", "")
    tid = task.get("id", "")
    area = task.get("area", "backend")
    risk = task.get("risk", "medium")
    desc = task.get("description", "")
    allowed = task.get("allowed_paths", ["server.js", "src/lib/db.js", "tests/"])
    acceptance = task.get("acceptance", [])

    acc_str = "\n".join([f"  - {a}" for a in acceptance])
    paths_str = ", ".join(allowed)

    return f"""================================================================================
🤖 VEYYON / CODEX BACKEND SUBAGENT DISPATCH
================================================================================
TASK ID:      {tid}
TITLE:        {title}
AREA:         {area.upper()} (Risk: {risk.upper()})
ALLOWED PATHS: {paths_str}

DESCRIPTION:
{desc}

ACCEPTANCE CRITERIA:
{acc_str}

EXECUTION PROTOCOL (LOCAL SUBAGENT):
1. Work directly on local server /opt/airbnb-app.
2. Modify only allowed paths: {paths_str}.
3. Connect directly to SQLite (data/airbnb.db) using prepared statements.
4. Add focused integration & E2E tests in tests/.
5. Run `npm test` locally to verify 100% green pass.
6. Once verified, run `python -m magda_agent.backend_bridge.backend_cli done {tid}`.
================================================================================"""


def print_tui(manifest: Dict[str, Any]) -> None:
    """Renders a colorful terminal TUI."""
    tasks = manifest.get("tasks", [])
    todo = [t for t in tasks if t.get("status") == "todo"]
    done = [t for t in tasks if t.get("status") == "done"]

    print("\033[1;35m" + "=" * 78 + "\033[0m")
    print("\033[1;36m 🧠 MAGDA-AGENT BACKEND & E2E REPL / TUI — (Veyyon & Codex Command Center)\033[0m")
    print(f"\033[1;33m Total: {len(tasks)} | TODO: {len(todo)} | DONE: {len(done)}\033[0m")
    print("\033[1;35m" + "=" * 78 + "\033[0m\n")

    if not todo:
        print("\033[1;32m ✨ All backend & E2E tasks are completed! Queue is clean.\033[0m")
        return

    print("\033[1;37m📋 PENDING BACKEND & DATABASE TASKS:\033[0m")
    for i, t in enumerate(todo, 1):
        area_color = "\033[1;34m" if t.get("area") == "backend" else "\033[1;31m"
        print(f" {i}. {area_color}[{t.get('area', 'backend').upper()}]\033[0m \033[1;37m{t.get('id')}\033[0m")
        print(f"    📌 {t.get('title')}")
        print(f"    📂 {t.get('allowed_paths')}")
        print("-" * 78)


def main():
    parser = argparse.ArgumentParser(description="Magda Backend & E2E Task CLI for Veyyon/Codex")
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="List all backend tasks")

    # tui
    subparsers.add_parser("tui", help="Open terminal TUI dashboard")

    # next
    subparsers.add_parser("next", help="Get next task and render subagent prompt")

    # done
    done_p = subparsers.add_parser("done", help="Mark a task as done")
    done_p.add_argument("task_id", help="ID of task to complete")

    args = parser.parse_args()
    manifest = load_backend_manifest()

    if args.command in ("list", None):
        print_tui(manifest)
    elif args.command == "tui":
        print_tui(manifest)
    elif args.command == "next":
        todos = get_todo_tasks(manifest)
        if not todos:
            print("No pending backend tasks.")
            sys.exit(0)
        print(render_subagent_prompt(todos[0]))
    elif args.command == "done":
        found = False
        for t in manifest.get("tasks", []):
            if t.get("id") == args.task_id:
                t["status"] = "done"
                t["completed_at"] = time.time()
                t["completed_by"] = "Veyyon/Codex Subagent"
                found = True
                break
        if found:
            save_backend_manifest(manifest)
            print(f"✅ Task [{args.task_id}] marked as DONE in backend_tasks.json.")
        else:
            print(f"❌ Task [{args.task_id}] not found in manifest.")


if __name__ == "__main__":
    main()
