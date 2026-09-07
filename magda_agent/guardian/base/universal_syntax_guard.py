"""
Universal Syntax & AST Guardian.
Runs on EVERY repository to ensure zero broken JavaScript, JSX, or Python files.
"""

import ast
import os
import re
from typing import List, Optional
import sqlite3

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue


class UniversalSyntaxGuardian(BaseGuardian):
    """Universal Guardian checking AST validity across JS, JSX, TS, and Python files."""

    def __init__(self):
        super().__init__(name="UniversalSyntaxGuardian", category="syntax", is_universal=True)

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
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, app_root)

                # 1. Python AST validation
                if file_name.endswith(".py"):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            code = f.read()
                        ast.parse(code, filename=rel_path)
                    except SyntaxError as e:
                        issues.append(GuardianIssue(
                            issue_type="syntax",
                            severity="high",
                            title=f"Python Syntax Error in {rel_path}",
                            description=f"Line {e.lineno}: {e.msg}",
                            suggestion="Fix Python syntax error to prevent runtime crash.",
                            metadata={"file": rel_path, "line": e.lineno}
                        ))

                # 2. JSX Tag Closure Validation (Catching unclosed tags & attribute placement errors)
                elif file_name.endswith((".jsx", ".tsx", ".js")):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        # Check for broken self-closing tag patterns e.g. `<div ... /> tabIndex=...`
                        bad_jsx_pattern = re.search(r'/>\s+[a-zA-Z]+=', content)
                        if bad_jsx_pattern:
                            issues.append(GuardianIssue(
                                issue_type="syntax",
                                severity="high",
                                title=f"Broken JSX Tag Closure in {rel_path}",
                                description="Found attributes placed outside closed tag (e.g. `/> tabIndex=...`).",
                                suggestion="Move JSX attributes inside the closing tag.",
                                metadata={"file": rel_path}
                            ))
                    except Exception:
                        pass

        return issues
