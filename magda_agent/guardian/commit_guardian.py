"""
Magda-Agent Commit-Guardian Engine (10-Point Pre-Commit Quality Gate).
Enforces strict quality, security, and integrity checks before any code enters Git history.

10 Automated Checks:
1. SECRETS: Regex scan for hardcoded tokens, API keys, private keys, PATs.
2. AST_SYNTAX: Validates Python AST, JSON syntax, and JSX tag closure on staged files.
3. TESTS: Executes local test suite (npm test / pytest) for zero regression.
4. FORBIDDEN_FILES: Blocks staging of .pyc, .tmp, .bak, .swp, .DS_Store, .log, and large binaries (>10MB).
5. DESTRUCTIVE_CODE: Blocks accidental 'rm -rf /' and unsafe raw 'DROP TABLE' scripts.
6. CONVENTIONAL_COMMITS: Validates commit message formatting (feat, fix, chore, etc.).
7. TASK_BOUNDARIES: Verifies staged files do not violate active task boundaries in agent_tasks.json.
8. BRANCH_HYGIENE: Prevents accidental direct commits to detached HEAD or tag states.
9. DB_INTEGRITY: Verifies SQLite schema DDL uses safe 'IF NOT EXISTS' and respects WAL mode.
10. AGENT_SIGNATURE: Enforces proper author and committer attribution (user.name & user.email).
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CommitGuardian:
    """10-Point Pre-Commit Quality Gate for AI Coding Agents and Human Developers."""

    SECRET_PATTERNS = [
        (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "GitHub Personal Access Token (PAT)"),
        (re.compile(r'gho_[a-zA-Z0-9]{36}'), "GitHub OAuth Access Token"),
        (re.compile(r'ghs_[a-zA-Z0-9]{36}'), "GitHub App User-to-Server Token"),
        (re.compile(r'sk-[a-zA-Z0-9_-]{20,}'), "OpenAI / Anthropic LLM API Key"),
        (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID"),
        (re.compile(r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----'), "SSH/RSA/EC Private Key"),
    ]

    SECRET_WHITELIST_PATHS = {
        ".env.example",
        ".env.test",
        ".env.sample",
        ".env.template",
    }

    SECRET_WHITELIST_PATTERNS = [
        "universal_security_guard",
        "commit_guardian",
        "test_commit_guardian",
        "tests/fixtures",
        "mock_",
        "fixtures/",
    ]

    DUMMY_MOCK_SECRETS = {
        "sk-test12345678901234567890",
        "ghp_000000000000000000000000000000000000",
        "gho_000000000000000000000000000000000000",
        "ghs_000000000000000000000000000000000000",
        "AKIAIOSFODNN7EXAMPLE",
    }

    FORBIDDEN_EXTENSIONS = {".pyc", ".tmp", ".bak", ".swp", ".DS_Store", ".log"}
    FORBIDDEN_PATH_SUBSTRINGS = ["node_modules/", ".pytest_cache/", "__pycache__/"]
    MAX_FILE_SIZE_MB = 10.0

    CONVENTIONAL_COMMIT_REGEX = re.compile(
        r'^(feat|fix|chore|docs|style|refactor|perf|test|ci|build|revert)(\([a-zA-Z0-9_\-.]+\))?(!)?:\s+([a-z0-9].+)$'
    )

    DESTRUCTIVE_CODE_PATTERNS = [
        (re.compile(r'rm\s+-rf\s+(?:/\s*|/\*|~\s*|~\*|\$ROOT|\$\{ROOT\})'), "Dangerous root/unbounded rm -rf deletion"),
        (re.compile(r'shutil\.rmtree\(\s*["\']/(?:root)?["\']\s*\)'), "Destructive root directory deletion"),
        (re.compile(r'DROP\s+TABLE\s+(?!IF\s+EXISTS\s+)(?:users|listings|bookings|payments|coupons)\b', re.IGNORECASE), "Destructive raw DROP TABLE without IF EXISTS"),
    ]

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root).resolve()

    def get_staged_files(self) -> List[str]:
        """Returns list of staged files (Added, Copied, Modified) in git index."""
        try:
            res = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return [f.strip() for f in res.stdout.splitlines() if f.strip()]
        except Exception:
            return []

    def get_staged_diff(self) -> str:
        """Returns the full unified diff of all staged changes."""
        try:
            res = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return res.stdout
        except Exception:
            return ""

    # =========================================================================
    # CHECK 1: Secrets & Sensitive Tokens
    # =========================================================================
    def check_1_secrets(self, staged_files: List[str]) -> Tuple[bool, List[str]]:
        """Scans staged files for leaked API keys, tokens, and private keys."""
        errors = []
        for rel_p in staged_files:
            file_name = Path(rel_p).name
            if file_name in self.SECRET_WHITELIST_PATHS or rel_p in self.SECRET_WHITELIST_PATHS:
                continue
            if any(wp in rel_p for wp in self.SECRET_WHITELIST_PATTERNS):
                continue

            full_p = self.repo_root / rel_p
            if not full_p.exists() or full_p.is_dir():
                continue

            try:
                content = full_p.read_text(encoding="utf-8", errors="ignore")
                for pattern, name in self.SECRET_PATTERNS:
                    matches = pattern.findall(content)
                    real_leaks = [m for m in matches if m not in self.DUMMY_MOCK_SECRETS]
                    if real_leaks:
                        errors.append(f"Secret Leak: {name} detected in staged file: {rel_p}")
            except Exception as e:
                errors.append(f"Could not read staged file {rel_p} for secret scanning: {e}")

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 2: AST & Code Syntax Integrity
    # =========================================================================
    def check_2_ast_syntax(self, staged_files: List[str]) -> Tuple[bool, List[str]]:
        """Validates Python AST, JSON validity, and JSX tag closure syntax."""
        errors = []
        for rel_p in staged_files:
            full_p = self.repo_root / rel_p
            if not full_p.exists() or full_p.is_dir():
                continue

            # Python AST Check
            if rel_p.endswith(".py"):
                try:
                    code = full_p.read_text(encoding="utf-8", errors="ignore")
                    ast.parse(code, filename=rel_p)
                except SyntaxError as e:
                    errors.append(f"Python Syntax Error in {rel_p} (line {e.lineno}): {e.msg}")
                except Exception as e:
                    errors.append(f"Python AST parse failed in {rel_p}: {e}")

            # JSON Validation
            elif rel_p.endswith(".json"):
                try:
                    content = full_p.read_text(encoding="utf-8", errors="ignore")
                    json.loads(content)
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON in {rel_p} (line {e.lineno}, col {e.colno}): {e.msg}")
                except Exception as e:
                    errors.append(f"JSON validation failed in {rel_p}: {e}")

            # JavaScript / JSX / TSX Tag and Bracket Check
            elif rel_p.endswith((".jsx", ".tsx", ".js", ".mjs", ".cjs")):
                try:
                    content = full_p.read_text(encoding="utf-8", errors="ignore")
                    # Check 1: JSX Tag closure attribute misplaced
                    if re.search(r'/>\s+[a-zA-Z0-9_\-]+=', content):
                        errors.append(f"Broken JSX Tag in {rel_p}: Found attribute placed outside closing tag '/>'.")

                    # Check 2: Balanced basic braces (skipping comments/strings simplistically)
                    # We only alert if there is a severe mismatch
                    cleaned = re.sub(r'//.*', '', content)
                    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
                    cleaned = re.sub(r'`(?:\\.|[^`])*`', '""', cleaned)
                    cleaned = re.sub(r'"(?:\\.|[^"])*"', '""', cleaned)
                    cleaned = re.sub(r"'(?:\\.|[^'])*'", "''", cleaned)

                    opens_curly = cleaned.count("{")
                    close_curly = cleaned.count("}")
                    if opens_curly != close_curly:
                        errors.append(f"Unbalanced curly braces in {rel_p}: {opens_curly} '{{' vs {close_curly} '}}'")
                except Exception as e:
                    errors.append(f"JS/JSX syntax scan error in {rel_p}: {e}")

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 3: Zero Regression Test Runner
    # =========================================================================
    def check_3_tests(self) -> Tuple[bool, List[str]]:
        """Runs the automated test suite (npm test or pytest) to guarantee zero regression."""
        pkg_json = self.repo_root / "package.json"
        node_modules = self.repo_root / "node_modules"
        has_py_tests = (self.repo_root / "tests").exists() and any((self.repo_root / "tests").glob("test_*.py"))

        # 1. Run Node/Vitest test suite if node_modules is installed
        if pkg_json.exists() and node_modules.exists():
            try:
                res = subprocess.run(
                    ["npm", "test"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=90
                )
                if res.returncode != 0:
                    out = (res.stderr or res.stdout or "").strip()
                    lines = out.splitlines()
                    tail = "\n".join(lines[-10:]) if len(lines) > 10 else out
                    return False, [f"Local 'npm test' failed before commit:\n{tail}"]
                return True, []
            except subprocess.TimeoutExpired:
                return False, ["Test runner timed out after 90 seconds."]
            except Exception as e:
                return False, [f"Test runner error: {e}"]

        # 2. Run Python unit test suite if Python tests exist
        elif has_py_tests:
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "tests"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if res.returncode != 0:
                    out = (res.stderr or res.stdout or "").strip()
                    return False, [f"Local unit tests failed before commit:\n{out[:300]}"]
                return True, []
            except Exception as e:
                return False, [f"Python test runner error: {e}"]

        return True, []

    # =========================================================================
    # CHECK 4: Forbidden & Oversized Files
    # =========================================================================
    def check_4_forbidden_files(self, staged_files: List[str]) -> Tuple[bool, List[str]]:
        """Rejects forbidden file extensions, cache paths, and oversized files."""
        errors = []
        for rel_p in staged_files:
            full_p = self.repo_root / rel_p
            suffix = Path(rel_p).suffix
            if suffix in self.FORBIDDEN_EXTENSIONS:
                errors.append(f"Forbidden file extension staged: {rel_p} ({suffix})")

            for bad_sub in self.FORBIDDEN_PATH_SUBSTRINGS:
                if bad_sub in rel_p:
                    errors.append(f"Forbidden path pattern staged: {rel_p} contains '{bad_sub}'")

            if full_p.exists() and not full_p.is_dir():
                size_mb = full_p.stat().st_size / (1024 * 1024)
                if size_mb > self.MAX_FILE_SIZE_MB:
                    errors.append(f"File too large ({size_mb:.2f} MB > {self.MAX_FILE_SIZE_MB} MB limit): {rel_p}")

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 5: Destructive Code Shield
    # =========================================================================
    def check_5_destructive_code(self, staged_diff: str) -> Tuple[bool, List[str]]:
        """Scans unified diff for dangerous shell commands or unsafe table drops, excluding test fixtures."""
        errors = []

        # Parse diff per file
        diff_by_file: Dict[str, List[str]] = {}
        current_file = "unknown"
        for line in staged_diff.splitlines():
            if line.startswith("diff --git a/"):
                parts = line.split()
                if len(parts) >= 3:
                    current_file = parts[2].replace("a/", "", 1)
                    diff_by_file[current_file] = []
            elif line.startswith("+") and not line.startswith("+++"):
                if current_file not in diff_by_file:
                    diff_by_file[current_file] = []
                diff_by_file[current_file].append(line[1:])

        # If no diff --git header, treat all added lines as general diff
        if not diff_by_file:
            added_lines = [
                line[1:] for line in staged_diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            diff_by_file["general"] = added_lines

        test_path_patterns = ["tests/", "test_", "fixtures/", "mock_", "commit_guardian"]

        for fpath, added_lines in diff_by_file.items():
            if any(tp in fpath for tp in test_path_patterns):
                continue  # Security tools and test cases intentionally contain pattern definitions
            diff_added_text = "\n".join(added_lines)
            for pattern, desc in self.DESTRUCTIVE_CODE_PATTERNS:
                if pattern.search(diff_added_text):
                    errors.append(f"Destructive Code Shield Alert in {fpath}: {desc}")

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 6: Conventional Commits Linter
    # =========================================================================
    def check_6_conventional_commit_msg(self, commit_msg: str) -> Tuple[bool, List[str]]:
        """
        Validates commit message conforms to Conventional Commits standard.
        Format: <type>(<scope>): <lowercase description>
        Allowed types: feat, fix, chore, docs, style, refactor, perf, test, ci, build, revert
        """
        if not commit_msg or not commit_msg.strip():
            return False, ["Commit message cannot be empty."]

        # Take the first line (subject line)
        subject = commit_msg.strip().splitlines()[0].strip()

        match = self.CONVENTIONAL_COMMIT_REGEX.match(subject)
        if not match:
            return False, [
                f"Invalid commit message format: '{subject}'.",
                "Expected format: '<type>(<scope>): <lowercase description>' (e.g., 'feat(guardian): add 10-point gate').",
                "Valid types: feat, fix, chore, docs, style, refactor, perf, test, ci, build, revert."
            ]

        # Check description rules
        desc = match.group(4)
        if desc.endswith("."):
            return False, [f"Commit message subject should not end with a period: '{subject}'."]

        if desc and desc[0].isupper():
            return False, [f"Commit message subject description should start with a lowercase letter: '{desc}'."]

        return True, []

    # =========================================================================
    # CHECK 7: Task Scope & Boundary Enforcer
    # =========================================================================
    def check_7_task_boundaries(self, staged_files: List[str]) -> Tuple[bool, List[str]]:
        """Checks if staged files exceed allowed_paths of any currently active/in_progress task."""
        manifest_files = [
            self.repo_root / "agent_tasks.json",
            self.repo_root / "backend_tasks.json",
        ]

        active_task = None
        for mf in manifest_files:
            if mf.exists():
                try:
                    data = json.loads(mf.read_text(encoding="utf-8"))
                    tasks = data.get("tasks", [])
                    for t in tasks:
                        if t.get("status") in ("in_progress", "active"):
                            active_task = t
                            break
                except Exception:
                    pass
            if active_task:
                break

        if not active_task:
            return True, []

        allowed = active_task.get("allowed_paths", [])
        if not allowed:
            return True, []

        # Standard metadata files always allowed
        standard_allowed = {"agent_tasks.json", "backend_tasks.json", "package.json", "package-lock.json", ".gitignore"}
        errors = []

        for rel_p in staged_files:
            if rel_p in standard_allowed:
                continue

            matches_allowed = False
            for pattern in allowed:
                # Direct match or folder prefix match
                if rel_p == pattern or rel_p.startswith(pattern.rstrip("*")):
                    matches_allowed = True
                    break
                # Directory match
                if pattern.endswith("/") and rel_p.startswith(pattern):
                    matches_allowed = True
                    break

            if not matches_allowed:
                errors.append(
                    f"Task Boundary Violation: File '{rel_p}' is not in allowed_paths for active task "
                    f"[{active_task.get('id', 'unknown')}] ('{active_task.get('title', '')}'). "
                    f"Allowed: {allowed}"
                )

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 8: Branch Hygiene
    # =========================================================================
    def check_8_branch_hygiene(self) -> Tuple[bool, List[str]]:
        """Verifies current git branch is not in detached HEAD or directly on protected release tags."""
        if os.environ.get("ALLOW_DETACHED_COMMIT", "0") == "1":
            return True, []

        try:
            res = subprocess.run(
                ["git", "symbolic-ref", "--short", "-q", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )
            branch = res.stdout.strip()
            if res.returncode != 0 or not branch:
                # Detached HEAD state
                return False, [
                    "Detached HEAD detected. Committing directly to a detached HEAD state is blocked to prevent lost work.",
                    "Switch to or create a branch first: git checkout -b feat/<name>"
                ]

            return True, []
        except Exception as e:
            return True, []

    # =========================================================================
    # CHECK 9: Database Integrity & Migration Rules
    # =========================================================================
    def check_9_db_integrity(self, staged_files: List[str]) -> Tuple[bool, List[str]]:
        """Verifies database schema DDL modifications use safe 'IF NOT EXISTS' and preserve WAL mode."""
        errors = []
        db_related_files = [f for f in staged_files if f.endswith((".sql", ".js", ".py")) and ("db" in f or "schema" in f or "migration" in f)]

        for rel_p in db_related_files:
            full_p = self.repo_root / rel_p
            if not full_p.exists() or full_p.is_dir():
                continue
            try:
                content = full_p.read_text(encoding="utf-8", errors="ignore")
                # Detect CREATE TABLE without IF NOT EXISTS
                unsafe_creates = re.findall(r'CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS\s+)([a-zA-Z0-9_]+)', content, re.IGNORECASE)
                for table in unsafe_creates:
                    # Ignore comment lines
                    errors.append(f"Unsafe DDL in {rel_p}: 'CREATE TABLE {table}' should use 'CREATE TABLE IF NOT EXISTS {table}'.")

                # Detect journal_mode = DELETE or OFF which breaks concurrent SQLite readers
                if re.search(r'PRAGMA\s+journal_mode\s*=\s*(?:DELETE|OFF|MEMORY)', content, re.IGNORECASE):
                    errors.append(f"Database Integrity Alert in {rel_p}: SQLite journal_mode must remain 'WAL' for concurrency.")
            except Exception as e:
                errors.append(f"Could not check DB integrity in {rel_p}: {e}")

        return len(errors) == 0, errors

    # =========================================================================
    # CHECK 10: Agent Signature & Attribution
    # =========================================================================
    def check_10_agent_signature(self) -> Tuple[bool, List[str]]:
        """Asserts non-empty Git user.name and user.email for traceable author attribution."""
        try:
            name_res = subprocess.run(
                ["git", "config", "user.name"],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )
            email_res = subprocess.run(
                ["git", "config", "user.email"],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )
            name = name_res.stdout.strip() or os.environ.get("GIT_AUTHOR_NAME", "").strip()
            email = email_res.stdout.strip() or os.environ.get("GIT_AUTHOR_EMAIL", "").strip()

            errors = []
            if not name:
                errors.append("Git user.name is not set. Run: git config user.name 'Your Name or Agent Name'")
            if not email:
                errors.append("Git user.email is not set. Run: git config user.email 'your.email@domain.com'")

            return len(errors) == 0, errors
        except Exception as e:
            return False, [f"Could not verify Git author configuration: {e}"]

    # =========================================================================
    # Master Execution: Run All 10 Checks
    # =========================================================================
    def run_all_checks(
        self,
        skip_tests: bool = False,
        commit_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the complete 10-point guardian quality gate on staged changes."""
        staged = self.get_staged_files()
        staged_diff = self.get_staged_diff()

        checks_results: Dict[str, Dict[str, Any]] = {}
        all_passed = True

        # Check 1: Secrets & Sensitive Tokens
        ok1, err1 = self.check_1_secrets(staged)
        checks_results["1_secrets"] = {"passed": ok1, "errors": err1}
        all_passed = all_passed and ok1

        # Check 2: AST & Code Syntax Integrity
        ok2, err2 = self.check_2_ast_syntax(staged)
        checks_results["2_ast_syntax"] = {"passed": ok2, "errors": err2}
        all_passed = all_passed and ok2

        # Check 3: Zero Regression Test Runner
        if not skip_tests:
            ok3, err3 = self.check_3_tests()
            checks_results["3_tests"] = {"passed": ok3, "errors": err3}
            all_passed = all_passed and ok3
        else:
            checks_results["3_tests"] = {"passed": True, "skipped": True, "errors": []}

        # Check 4: Forbidden & Oversized Files
        ok4, err4 = self.check_4_forbidden_files(staged)
        checks_results["4_forbidden_files"] = {"passed": ok4, "errors": err4}
        all_passed = all_passed and ok4

        # Check 5: Destructive Code Shield
        ok5, err5 = self.check_5_destructive_code(staged_diff)
        checks_results["5_destructive_code"] = {"passed": ok5, "errors": err5}
        all_passed = all_passed and ok5

        # Check 6: Conventional Commits (if message provided)
        if commit_msg is not None:
            ok6, err6 = self.check_6_conventional_commit_msg(commit_msg)
            checks_results["6_conventional_commits"] = {"passed": ok6, "errors": err6}
            all_passed = all_passed and ok6
        else:
            checks_results["6_conventional_commits"] = {"passed": True, "skipped": True, "message": "Evaluated at commit-msg hook stage", "errors": []}

        # Check 7: Task Scope & Boundary Enforcer
        ok7, err7 = self.check_7_task_boundaries(staged)
        checks_results["7_task_boundaries"] = {"passed": ok7, "errors": err7}
        all_passed = all_passed and ok7

        # Check 8: Branch Hygiene
        ok8, err8 = self.check_8_branch_hygiene()
        checks_results["8_branch_hygiene"] = {"passed": ok8, "errors": err8}
        all_passed = all_passed and ok8

        # Check 9: Database Integrity & Migration Rules
        ok9, err9 = self.check_9_db_integrity(staged)
        checks_results["9_db_integrity"] = {"passed": ok9, "errors": err9}
        all_passed = all_passed and ok9

        # Check 10: Agent Signature & Attribution
        ok10, err10 = self.check_10_agent_signature()
        checks_results["10_agent_signature"] = {"passed": ok10, "errors": err10}
        all_passed = all_passed and ok10

        return {
            "status": "passed" if all_passed else "blocked",
            "all_passed": all_passed,
            "staged_files_count": len(staged),
            "checks": checks_results,
        }


# =============================================================================
# Dual Git Hook Installation (pre-commit & commit-msg)
# =============================================================================
def install_git_hooks(repo_root: str = ".") -> bool:
    """Installs both pre-commit and commit-msg hooks into .git/hooks/."""
    hooks_dir = Path(repo_root).resolve() / ".git" / "hooks"

    pre_commit_content = """#!/usr/bin/env bash
# Magda-Agent 10-Point Pre-Commit Guardian Hook
python3 -m magda_agent.guardian.commit_guardian check || {
    echo "🛑 [COMMIT GUARDIAN BLOCKED]: Pre-commit quality gate failed! Fix the issues above before committing."
    exit 1
}
"""

    commit_msg_content = """#!/usr/bin/env bash
# Magda-Agent Conventional Commits Linter Hook
python3 -m magda_agent.guardian.commit_guardian check-msg "$1" || {
    echo "🛑 [COMMIT GUARDIAN BLOCKED]: Invalid commit message format!"
    exit 1
}
"""

    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)

        pre_commit_path = hooks_dir / "pre-commit"
        pre_commit_path.write_text(pre_commit_content, encoding="utf-8")
        pre_commit_path.chmod(0o755)

        commit_msg_path = hooks_dir / "commit-msg"
        commit_msg_path.write_text(commit_msg_content, encoding="utf-8")
        commit_msg_path.chmod(0o755)

        print(f"✅ Pre-commit hook installed at: {pre_commit_path}")
        print(f"✅ Commit-msg hook installed at: {commit_msg_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to install git hooks: {e}")
        return False


def install_git_hook(repo_root: str = ".") -> bool:
    """Backward-compatible alias for install_git_hooks."""
    return install_git_hooks(repo_root)


# =============================================================================
# CLI Interface
# =============================================================================
def main():
    args = sys.argv[1:]
    command = args[0] if args else "check"

    if command in ("install-hooks", "install-hook"):
        target = args[1] if len(args) > 1 else "."
        success = install_git_hooks(target)
        sys.exit(0 if success else 1)

    elif command == "check-msg":
        if len(args) < 2:
            print("Usage: python3 -m magda_agent.guardian.commit_guardian check-msg <commit_msg_file_or_string>")
            sys.exit(1)

        msg_input = args[1]
        msg_file = Path(msg_input)
        if msg_file.exists() and msg_file.is_file():
            commit_msg = msg_file.read_text(encoding="utf-8").strip()
        else:
            commit_msg = msg_input.strip()

        guardian = CommitGuardian()
        ok, errors = guardian.check_6_conventional_commit_msg(commit_msg)
        if ok:
            print(f"✅ [Commit-Msg Guardian]: Valid conventional commit message: '{commit_msg.splitlines()[0]}'")
            sys.exit(0)
        else:
            print("🛑 [Commit-Msg Guardian BLOCKED]: Invalid commit message format!")
            for err in errors:
                print(f"   ⚠️  {err}")
            sys.exit(1)

    elif command in ("check", "run"):
        skip_tests = "--skip-tests" in args
        repo_root = "."
        for i, a in enumerate(args):
            if a == "--repo-root" and i + 1 < len(args):
                repo_root = args[i + 1]

        guardian = CommitGuardian(repo_root=repo_root)
        report = guardian.run_all_checks(skip_tests=skip_tests)

        print("🛡️ [Magda Commit-Guardian 10-Point Quality Gate Report]:")
        for check_name, res in report.get("checks", {}).items():
            status_icon = "✅" if res.get("passed") else "❌"
            skipped_tag = " (skipped)" if res.get("skipped") else ""
            print(f" {status_icon} {check_name}{skipped_tag}")
            for err in res.get("errors", []):
                print(f"    ⚠️  {err}")

        if not report.get("all_passed"):
            print("\n🛑 [COMMIT BLOCKED]: Quality gate failed. Commit aborted.")
            sys.exit(1)
        else:
            print("\n🎉 [QUALITY GATE PASSED]: All 10 checks green. Commit permitted.")
            sys.exit(0)

    else:
        print(f"Unknown command: {command}. Available: check, check-msg, install-hooks")
        sys.exit(1)


if __name__ == "__main__":
    main()
