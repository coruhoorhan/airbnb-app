"""
Magda-Agent Autonomous Local Backend Worker (Codex Engine).
Autonomous loop that:
1. Picks the next TODO task from backend_tasks.json.
2. Inspects allowed_paths and codebase context.
3. Generates complete, production-ready backend/DB/test implementations via LLM (Mercury-2 / OpenAI).
4. Applies code changes directly to disk.
5. Runs `npm test` locally to verify.
6. Self-corrects on test failures (up to 3 retries).
7. Marks task DONE in backend_tasks.json and commits to git.
8. Automatically proceeds to the next backend task without human in the loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from magda_agent.backend_bridge.backend_cli import (
    load_backend_manifest,
    save_backend_manifest,
    get_todo_tasks,
    render_subagent_prompt,
)
from magda_agent.llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [🤖 MagdaBackendWorker]: %(message)s")
logger = logging.getLogger("MagdaBackendWorker")

APP_ROOT = os.environ.get("AIRBNB_APP_ROOT", "/opt/airbnb-app" if os.path.exists("/opt/airbnb-app") else os.path.abspath("."))


class AutonomousBackendWorker:
    """7/24 Local Autonomous Coding Worker for Backend, Database, and E2E Tests."""

    def __init__(self, app_root: str = APP_ROOT):
        self.app_root = app_root
        self.llm = LLMClient() if LLMClient else None
        self.manifest_path = Path(self.app_root) / "backend_tasks.json"

    def _read_file(self, rel_path: str, max_lines: int = 250) -> str:
        full_p = os.path.join(self.app_root, rel_path)
        if not os.path.exists(full_p):
            return ""
        try:
            with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return "".join(lines[:max_lines])
        except Exception:
            return ""

    def _write_file(self, rel_path: str, content: str) -> bool:
        full_p = os.path.join(self.app_root, rel_path)
        try:
            os.makedirs(os.path.dirname(full_p), exist_ok=True)
            with open(full_p, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to write file {rel_path}: {e}")
            return False

    def run_npm_tests(self) -> Tuple[bool, str]:
        """Runs `npm test` and returns (passed, stdout/stderr output)."""
        try:
            res = subprocess.run(
                ["npm", "test"],
                cwd=self.app_root,
                capture_output=True,
                text=True,
                timeout=90,
            )
            passed = res.returncode == 0
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            return passed, output.strip()
        except Exception as e:
            return False, str(e)

    async def implement_task(self, task: Dict[str, Any]) -> bool:
        """Executes full autonomous implementation and test verification cycle for one task."""
        tid = task.get("id")
        title = task.get("title")
        allowed_paths = task.get("allowed_paths", ["server.js", "src/lib/db.js"])
        logger.info(f"🚀 Starting autonomous implementation of backend task: [{tid}] {title}")

        # Gather relevant codebase context
        server_js = self._read_file("server.js", 200)
        db_js = self._read_file("src/lib/db.js", 150)
        task_prompt = render_subagent_prompt(task)

        system_instruction = (
            "You are Magda-Agent's Senior Autonomous Backend Engineer. "
            "Implement the requested backend feature, API route, database function, and Vitest test cleanly. "
            "Work directly on the provided files. Output ONLY a valid JSON object mapping file paths to their full updated content: "
            "{\"files\": [{\"path\": \"server.js\", \"content\": \"...\"}, {\"path\": \"tests/my_test.test.js\", \"content\": \"...\"}]}"
        )

        user_prompt = f"""CODEBASE SNAPSHOTS:
--- server.js (top 200 lines) ---
{server_js}

--- src/lib/db.js (top 150 lines) ---
{db_js}

TASK BLUEPRINT:
{task_prompt}

Return ONLY raw JSON with the 'files' array. No markdown wrapping outside JSON."""

        for attempt in range(1, 4):
            logger.info(f"🤖 LLM Coding Attempt {attempt}/3 for [{tid}]...")
            try:
                raw_resp = await self.llm.generate(user_prompt, system=system_instruction, temperature=0.2, max_tokens=3000)
                cleaned = raw_resp.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r"^```json\s*", "", cleaned)
                    cleaned = re.sub(r"^```\s*", "", cleaned)
                    cleaned = re.sub(r"```$", "", cleaned).strip()

                data = json.loads(cleaned)
                files_to_update = data.get("files", [])
                if not files_to_update:
                    logger.warning("No files returned in LLM response.")
                    continue

                # Apply code updates to disk
                for f_entry in files_to_update:
                    f_path = f_entry.get("path")
                    f_content = f_entry.get("content")
                    if f_path and f_content:
                        self._write_file(f_path, f_content)
                        logger.info(f"Updated file on disk: {f_path}")

                # Run Vitest Verification
                logger.info("🧪 Running npm test verification...")
                passed, test_out = self.run_npm_tests()

                if passed:
                    logger.info(f"✅ All tests passed cleanly for [{tid}]!")
                    # Mark task DONE
                    manifest = load_backend_manifest(self.manifest_path)
                    for t in manifest.get("tasks", []):
                        if t.get("id") == tid:
                            t["status"] = "done"
                            t["completed_at"] = time.time()
                            t["completed_by"] = "Magda Autonomous Backend Worker"
                            break
                    save_backend_manifest(manifest, self.manifest_path)

                    # Git commit
                    commit_msg = f"feat(backend): implement {tid} — {title}"
                    subprocess.run(["git", "add", "."], cwd=self.app_root, capture_output=True)
                    subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.app_root, capture_output=True)
                    logger.info(f"🎉 Task [{tid}] completed and committed to git.")
                    return True
                else:
                    logger.warning(f"❌ Tests failed on attempt {attempt}: {test_out[:300]}")
                    # Feed error back into next attempt prompt
                    user_prompt += f"\n\nPREVIOUS ATTEMPT FAILED TESTS:\n{test_out[:1000]}\nPlease fix the implementation so all tests pass."

            except Exception as e:
                logger.error(f"Error during coding attempt {attempt}: {e}")

        logger.error(f"❌ Failed to complete [{tid}] after 3 attempts. Leaving for review.")
        return False

    async def run_loop(self, poll_interval: int = 10) -> None:
        """7/24 Continuous Autonomous Worker Loop."""
        logger.info(f"Starting Magda Autonomous Backend Worker Loop (Poll Interval: {poll_interval}s)...")
        while True:
            try:
                manifest = load_backend_manifest(self.manifest_path)
                todos = get_todo_tasks(manifest)
                if not todos:
                    logger.info("All backend tasks are completed. Worker is resting.")
                    await asyncio.sleep(poll_interval * 3)
                    continue

                next_t = todos[0]
                success = await self.implement_task(next_t)
                if not success:
                    # If stuck, wait a bit before moving on
                    await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in backend worker cycle: {e}")

            await asyncio.sleep(poll_interval)


def main():
    worker = AutonomousBackendWorker()
    if len(sys.argv) > 1 and sys.argv[1] == "run-one":
        manifest = load_backend_manifest(worker.manifest_path)
        todos = get_todo_tasks(manifest)
        if todos:
            asyncio.run(worker.implement_task(todos[0]))
        else:
            print("No pending backend tasks.")
        return

    # Run continuous loop
    interval = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 15
    asyncio.run(worker.run_loop(poll_interval=interval))


if __name__ == "__main__":
    main()
