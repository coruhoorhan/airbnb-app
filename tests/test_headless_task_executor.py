"""
Comprehensive Unit Test Suite for Headless Task & Roadmap Executor.
Tests task listing, sequential priority selection, dry-run mode, and status progression.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from magda_agent.autonomous.task_executor import HeadlessTaskExecutor


class TestHeadlessTaskExecutor(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="task_executor_test_")
        self.app_root = Path(self.test_dir)

        self.manifest_path = self.app_root / "agent_tasks.json"
        self.manifest_data = {
            "schema_version": 1,
            "tasks": [
                {
                    "id": "security-csrf-protection",
                    "status": "todo",
                    "title": "Add CSRF protection",
                    "area": "security",
                    "risk": "medium",
                    "allowed_paths": ["server.js", "src/lib/auth.js"],
                    "acceptance": ["CSRF tokens required on state-changing requests."]
                },
                {
                    "id": "backend-input-validation",
                    "status": "todo",
                    "title": "Enforce strict input validation",
                    "area": "backend",
                    "risk": "medium",
                    "allowed_paths": ["server.js", "src/lib/db.js"],
                    "acceptance": ["Payloads validated with Joi schemas."]
                }
            ],
            "archived_tasks": []
        }
        self.manifest_path.write_text(json.dumps(self.manifest_data, indent=2))

        self.executor = HeadlessTaskExecutor(
            app_root=str(self.app_root),
            manifest_path=str(self.manifest_path),
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_and_get_next_todo_task(self):
        tasks = self.executor.list_tasks()
        self.assertEqual(len(tasks), 2)

        next_task = self.executor.get_next_todo_task()
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task["id"], "security-csrf-protection")

    def test_dry_run_execution(self):
        res = self.executor.execute_next_task(dry_run=True)
        self.assertEqual(res.get("status"), "dry_run")
        self.assertEqual(res.get("task_id"), "security-csrf-protection")

        # Confirm status remains 'todo'
        manifest = json.loads(self.manifest_path.read_text())
        self.assertEqual(manifest["tasks"][0]["status"], "todo")

    def test_mark_task_done(self):
        success = self.executor.mark_task_done("security-csrf-protection")
        self.assertTrue(success)

        manifest = json.loads(self.manifest_path.read_text())
        self.assertEqual(manifest["tasks"][0]["status"], "done")

        # Next todo task is now the second one
        next_task = self.executor.get_next_todo_task()
        self.assertEqual(next_task["id"], "backend-input-validation")


if __name__ == "__main__":
    unittest.main()
