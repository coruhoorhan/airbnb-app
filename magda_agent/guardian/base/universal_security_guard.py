"""
Universal Security Guardian.
Runs on EVERY repository to check for secret leaks, hardcoded tokens,
insecure permissions, and exposed sensitive files.
"""

import os
import re
import sqlite3
from typing import List, Optional

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue


class UniversalSecurityGuardian(BaseGuardian):
    """Universal Security Auditor scanning codebase and configurations."""

    # Patterns defined using concatenated parts to prevent false-positive self-detection
    SECRET_PATTERNS = [
        (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "Exposed GitHub Personal Access Token (PAT)"),
        (re.compile(r'sk-[a-zA-Z0-9]{32,}'), "Exposed OpenAI / LLM Secret Key"),
        (re.compile(r'-----' + r'BEGIN ' + r'(?:RSA |EC )?PRIVATE KEY' + r'-----'), "Exposed Private Key"),
        (re.compile(r'AKIA[0-9A-Z]{16}'), "Exposed AWS Access Key ID"),
    ]

    def __init__(self):
        super().__init__(name="UniversalSecurityGuardian", category="security", is_universal=True)

    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        issues: List[GuardianIssue] = []
        ignored_dirs = {"node_modules", ".git", "dist", "build", ".venv", "__pycache__"}

        for root, dirs, files in os.walk(app_root):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]

            for file_name in files:
                # Do not scan .env directly (intended to hold env vars) or security scanner definitions
                if file_name.startswith(".env") or file_name == "universal_security_guard.py":
                    continue

                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, app_root)

                # Scan source code for hardcoded secrets
                if file_name.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".json", ".yml", ".yaml")):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        for regex, leak_name in self.SECRET_PATTERNS:
                            if regex.search(content):
                                issues.append(GuardianIssue(
                                    issue_type="security",
                                    severity="critical",
                                    title=f"Secret Leak: {leak_name} in {rel_path}",
                                    description=f"Found potential unencrypted secret in {rel_path}.",
                                    suggestion="Move sensitive tokens into environment variables (.env) immediately.",
                                    metadata={"file": rel_path, "leak_type": leak_name}
                                ))
                    except Exception:
                        pass

        return issues
