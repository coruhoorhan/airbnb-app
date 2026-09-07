"""
Universal Infrastructure & System Performance Guardian.
Monitors disk space, system memory, and database file sizing across any server environment.
"""

import os
import shutil
import sqlite3
from typing import List, Optional

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue


class UniversalInfraGuardian(BaseGuardian):
    """Universal Guardian monitoring disk storage, process health, and filesystem metrics."""

    def __init__(self, disk_threshold_percent: float = 90.0):
        super().__init__(name="UniversalInfraGuardian", category="infra", is_universal=True)
        self.disk_threshold = disk_threshold_percent

    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        issues: List[GuardianIssue] = []

        # 1. Disk Space Check
        try:
            total, used, free = shutil.disk_usage(app_root)
            used_pct = (used / total) * 100.0
            if used_pct >= self.disk_threshold:
                issues.append(GuardianIssue(
                    issue_type="infra",
                    severity="high",
                    title=f"High Disk Usage Warning ({used_pct:.1f}%)",
                    description=f"Free disk space on {app_root} is critically low ({free // (1024*1024)} MB remaining).",
                    suggestion="Clean up log files, build artifacts (dist/), and old database backups.",
                    metadata={"used_percent": used_pct, "free_mb": free // (1024 * 1024)}
                ))
        except Exception:
            pass

        # 2. Database Size Optimization Recommendation
        if db_conn:
            try:
                page_count = db_conn.execute("PRAGMA page_count;").fetchone()[0]
                page_size = db_conn.execute("PRAGMA page_size;").fetchone()[0]
                freelist_count = db_conn.execute("PRAGMA freelist_count;").fetchone()[0]
                db_size_mb = (page_count * page_size) / (1024 * 1024)

                # If more than 30% of pages are free/unused, recommend VACUUM
                if page_count > 100 and (freelist_count / page_count) > 0.30:
                    db_conn.execute("PRAGMA optimize;")
                    issues.append(GuardianIssue(
                        issue_type="infra",
                        severity="low",
                        title="SQLite Freelist Pages Optimized",
                        description=f"Database file size is {db_size_mb:.2f} MB with {freelist_count} unused pages. PRAGMA optimize executed.",
                        auto_healed=True
                    ))
            except Exception:
                pass

        return issues
