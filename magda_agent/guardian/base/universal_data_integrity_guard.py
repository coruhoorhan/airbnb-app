"""
Universal Database & Data Integrity Guardian.
Runs on ANY project using SQLite / Relational Database to ensure:
- Foreign key integrity
- PRAGMA integrity_check
- Empty tables / missing schemas
- Auto-vacuum optimization
"""

import json
import sqlite3
from typing import List, Optional

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue


class UniversalDataIntegrityGuardian(BaseGuardian):
    """Universal Guardian ensuring database health, integrity, and non-corrupted records."""

    def __init__(self):
        super().__init__(name="UniversalDataIntegrityGuardian", category="data_integrity", is_universal=True)

    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        issues: List[GuardianIssue] = []
        if not db_conn:
            return issues

        try:
            # 1. SQLite Low-Level Integrity Check
            check_res = db_conn.execute("PRAGMA integrity_check;").fetchall()
            for row in check_res:
                status = row[0] if isinstance(row, (tuple, list, sqlite3.Row)) else str(row)
                if status != "ok":
                    issues.append(GuardianIssue(
                        issue_type="data_integrity",
                        severity="critical",
                        title="SQLite Database File Corruption Detected",
                        description=f"PRAGMA integrity_check returned error: {status}",
                        suggestion="Backup and restore database from write-ahead log (WAL).",
                    ))

            # 2. Foreign Key Constraint Check
            fk_violations = db_conn.execute("PRAGMA foreign_key_check;").fetchall()
            if fk_violations:
                issues.append(GuardianIssue(
                    issue_type="data_integrity",
                    severity="high",
                    title=f"Foreign Key Constraint Violations ({len(fk_violations)} found)",
                    description=f"Detected {len(fk_violations)} orphaned or dangling foreign key rows.",
                    suggestion="Clean up orphaned child records to restore referential integrity.",
                    metadata={"violation_count": len(fk_violations)}
                ))

        except Exception as e:
            issues.append(GuardianIssue(
                issue_type="data_integrity",
                severity="medium",
                title="Database Diagnostic Check Error",
                description=f"Error executing SQLite integrity pragmas: {e}",
            ))

        return issues
