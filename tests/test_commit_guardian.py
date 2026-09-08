"""
Comprehensive Unit Test Suite for Commit-Guardian 10-Point Quality Gate.
Tests all 10 pre-commit & commit-msg checks plus git hook installer.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from magda_agent.guardian.commit_guardian import CommitGuardian, install_git_hooks


class TestCommitGuardian10PointGate(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="commit_guardian_test_")
        self.test_path = Path(self.test_dir)
        self.guardian = CommitGuardian(repo_root=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # CHECK 1: Secrets & Sensitive Tokens
    # -------------------------------------------------------------------------
    def test_check_1_secrets_detection_and_whitelist(self):
        # 1. Leaked secrets file
        leak_file = self.test_path / "leaks.py"
        leak_file.write_text(
            'API_KEY = "sk-1234567890abcdef1234567890abcdef"\n'
            'GH_TOKEN = "ghp_123456789012345678901234567890123456"\n'
            'AWS_KEY = "AKIA1234567890ABCDEF"\n'
        )

        ok, errors = self.guardian.check_1_secrets(["leaks.py"])
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("GitHub Personal Access Token" in e for e in errors))
        self.assertTrue(any("OpenAI / Anthropic" in e for e in errors))

        # 2. Whitelisted files (.env.example & dummy mocks)
        env_example = self.test_path / ".env.example"
        env_example.write_text('OPENAI_API_KEY="sk-1234567890abcdef1234567890abcdef"\n')
        ok_env, errors_env = self.guardian.check_1_secrets([".env.example"])
        self.assertTrue(ok_env)
        self.assertEqual(len(errors_env), 0)

        # 3. Dummy mock token whitelist
        mock_file = self.test_path / "mock_service.py"
        mock_file.write_text('KEY = "sk-test12345678901234567890"\n')
        ok_mock, errors_mock = self.guardian.check_1_secrets(["mock_service.py"])
        self.assertTrue(ok_mock)

    # -------------------------------------------------------------------------
    # CHECK 2: AST & Code Syntax Integrity
    # -------------------------------------------------------------------------
    def test_check_2_ast_syntax_python_json_jsx(self):
        # Valid Python
        py_valid = self.test_path / "valid.py"
        py_valid.write_text("def add(a, b):\n    return a + b\n")

        # Invalid Python
        py_invalid = self.test_path / "broken.py"
        py_invalid.write_text("def broken(\n    return 42\n")

        # Valid JSON
        json_valid = self.test_path / "valid.json"
        json_valid.write_text('{"name": "magda", "version": 1}')

        # Invalid JSON
        json_invalid = self.test_path / "broken.json"
        json_invalid.write_text('{"name": "magda", broken}')

        # Broken JSX
        jsx_broken = self.test_path / "BrokenComponent.jsx"
        jsx_broken.write_text('export default function Broken() { return <div /> className="test" />; }')

        ok, errors = self.guardian.check_2_ast_syntax(["valid.py", "valid.json"])
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

        ok_bad, errors_bad = self.guardian.check_2_ast_syntax(["broken.py", "broken.json", "BrokenComponent.jsx"])
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(errors_bad), 3)
        self.assertTrue(any("Python Syntax Error in broken.py" in e for e in errors_bad))
        self.assertTrue(any("Invalid JSON in broken.json" in e for e in errors_bad))
        self.assertTrue(any("Broken JSX Tag in BrokenComponent.jsx" in e for e in errors_bad))

    # -------------------------------------------------------------------------
    # CHECK 3: Zero Regression Test Runner
    # -------------------------------------------------------------------------
    def test_check_3_tests_skip_option(self):
        report = self.guardian.run_all_checks(skip_tests=True)
        self.assertTrue(report["checks"]["3_tests"]["skipped"])
        self.assertTrue(report["checks"]["3_tests"]["passed"])

    # -------------------------------------------------------------------------
    # CHECK 4: Forbidden & Large Files
    # -------------------------------------------------------------------------
    def test_check_4_forbidden_and_large_files(self):
        # Forbidden extension
        pyc_file = self.test_path / "temp.pyc"
        pyc_file.write_bytes(b"bytecode")

        # Oversized file (>10MB)
        large_file = self.test_path / "large_data.bin"
        large_file.write_bytes(b"0" * (11 * 1024 * 1024))

        ok, errors = self.guardian.check_4_forbidden_files(["temp.pyc", "large_data.bin"])
        self.assertFalse(ok)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("Forbidden file extension staged: temp.pyc" in e for e in errors))
        self.assertTrue(any("File too large" in e for e in errors))

    # -------------------------------------------------------------------------
    # CHECK 5: Destructive Code Shield
    # -------------------------------------------------------------------------
    def test_check_5_destructive_code_shield(self):
        bad_diff = """
diff --git a/scripts/clean.sh b/scripts/clean.sh
+rm -rf /
+DROP TABLE users;
"""
        ok, errors = self.guardian.check_5_destructive_code(bad_diff)
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("rm -rf" in e for e in errors))
        self.assertTrue(any("DROP TABLE without IF EXISTS" in e for e in errors))

        good_diff = """
diff --git a/scripts/clean.sh b/scripts/clean.sh
+rm -rf ./tmp/cache
+DROP TABLE IF EXISTS old_temp_table;
"""
        ok_good, errors_good = self.guardian.check_5_destructive_code(good_diff)
        self.assertTrue(ok_good)
        self.assertEqual(len(errors_good), 0)

    # -------------------------------------------------------------------------
    # CHECK 6: Conventional Commits Linter
    # -------------------------------------------------------------------------
    def test_check_6_conventional_commits(self):
        valid_messages = [
            "feat(guardian): add 10-point quality gate",
            "fix: resolve missing import in server.js",
            "chore(deps): bump vite from 5.0 to 5.1",
            "docs: update architecture diagram",
            "refactor(db): optimize query caching",
            "test(e2e): add synthetic booking test",
            "perf: speed up server startup time",
            "ci: add commit-guardian step",
        ]

        for msg in valid_messages:
            ok, errors = self.guardian.check_6_conventional_commit_msg(msg)
            self.assertTrue(ok, f"Failed for valid message: {msg}, errors: {errors}")

        invalid_messages = [
            "Added new feature",                        # Missing type
            "feat: Added new feature",                  # Capital letter in description
            "feat(auth): login fix.",                   # Trailing period
            "WIP: unfinished work",                     # Non-standard type
            "update server.js",                         # Missing type
            "",                                         # Empty
            "   ",                                      # Whitespace
        ]

        for msg in invalid_messages:
            ok, errors = self.guardian.check_6_conventional_commit_msg(msg)
            self.assertFalse(ok, f"Should have failed for message: {msg}")

    # -------------------------------------------------------------------------
    # CHECK 7: Task Scope & Boundary Enforcer
    # -------------------------------------------------------------------------
    def test_check_7_task_boundaries(self):
        manifest_file = self.test_path / "agent_tasks.json"
        manifest_file.write_text(json.dumps({
            "tasks": [
                {
                    "id": "feat-calendar-sync",
                    "status": "in_progress",
                    "title": "Add Calendar iCal Sync",
                    "allowed_paths": ["src/lib/calendarSync.js", "server.js", "agent_tasks.json"]
                }
            ]
        }))

        # Inside allowed boundaries
        ok_in, errors_in = self.guardian.check_7_task_boundaries(["src/lib/calendarSync.js", "server.js"])
        self.assertTrue(ok_in)
        self.assertEqual(len(errors_in), 0)

        # Outside allowed boundaries
        ok_out, errors_out = self.guardian.check_7_task_boundaries(["src/lib/calendarSync.js", "src/components/UnauthorizedPayment.jsx"])
        self.assertFalse(ok_out)
        self.assertTrue(any("Task Boundary Violation" in e for e in errors_out))

    # -------------------------------------------------------------------------
    # CHECK 8: Branch Hygiene
    # -------------------------------------------------------------------------
    def test_check_8_branch_hygiene(self):
        with patch.dict(os.environ, {"ALLOW_DETACHED_COMMIT": "1"}):
            ok, errors = self.guardian.check_8_branch_hygiene()
            self.assertTrue(ok)

    # -------------------------------------------------------------------------
    # CHECK 9: Database Integrity & Migration Rules
    # -------------------------------------------------------------------------
    def test_check_9_db_integrity(self):
        unsafe_sql = self.test_path / "schema_migration.sql"
        unsafe_sql.write_text("CREATE TABLE users (id INTEGER PRIMARY KEY);\nPRAGMA journal_mode = DELETE;\n")

        ok, errors = self.guardian.check_9_db_integrity(["schema_migration.sql"])
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS" in e for e in errors))
        self.assertTrue(any("journal_mode must remain 'WAL'" in e for e in errors))

        safe_sql = self.test_path / "safe_migration.sql"
        safe_sql.write_text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY);\nPRAGMA journal_mode = WAL;\n")

        ok_safe, errors_safe = self.guardian.check_9_db_integrity(["safe_migration.sql"])
        self.assertTrue(ok_safe)
        self.assertEqual(len(errors_safe), 0)

    # -------------------------------------------------------------------------
    # CHECK 10: Agent Signature & Attribution
    # -------------------------------------------------------------------------
    def test_check_10_agent_signature(self):
        with patch.dict(os.environ, {"GIT_AUTHOR_NAME": "Magda Agent", "GIT_AUTHOR_EMAIL": "magda@agent.local"}):
            ok, errors = self.guardian.check_10_agent_signature()
            self.assertTrue(ok)
            self.assertEqual(len(errors), 0)

    # -------------------------------------------------------------------------
    # Git Hooks Installation
    # -------------------------------------------------------------------------
    def test_install_git_hooks(self):
        success = install_git_hooks(self.test_dir)
        self.assertTrue(success)

        pre_commit = self.test_path / ".git" / "hooks" / "pre-commit"
        commit_msg = self.test_path / ".git" / "hooks" / "commit-msg"

        self.assertTrue(pre_commit.exists())
        self.assertTrue(commit_msg.exists())
        self.assertTrue(os.access(str(pre_commit), os.X_OK))
        self.assertTrue(os.access(str(commit_msg), os.X_OK))


if __name__ == "__main__":
    unittest.main()
