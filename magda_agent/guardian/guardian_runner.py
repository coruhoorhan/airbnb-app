"""
Magda-Agent 2-Tier Modular Guardian Engine.
Orchestrates:
1. Tier 1: Universal Base Guardians (Security, Syntax/AST, Data Integrity, Infrastructure)
2. Tier 2: Project-Specific Domain Guardians (Airbnb, E-Belediye, CRM, E-Commerce plugins)
"""

import json
import logging
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional

from magda_agent.guardian.base.abstract_guard import BaseGuardian, GuardianIssue
from magda_agent.guardian.base.universal_syntax_guard import UniversalSyntaxGuardian
from magda_agent.guardian.base.universal_security_guard import UniversalSecurityGuardian
from magda_agent.guardian.base.universal_data_integrity_guard import UniversalDataIntegrityGuardian
from magda_agent.guardian.base.universal_infra_guard import UniversalInfraGuardian
from magda_agent.guardian.plugins.airbnb_domain_guard import AirbnbDomainGuardian

logger = logging.getLogger("MagdaGuardianEngine")


class MagdaGuardianEngine:
    """Master Guardian Engine running Universal Checks and Dynamic Domain Plugins."""

    def __init__(self, app_root: str, db_path: Optional[str] = None):
        self.app_root = app_root
        self.db_path = db_path

        # 1. Tier 1: Universal Guardians (Executed on EVERY repository)
        self.universal_guardians: List[BaseGuardian] = [
            UniversalSyntaxGuardian(),
            UniversalSecurityGuardian(),
            UniversalDataIntegrityGuardian(),
            UniversalInfraGuardian(),
        ]

        # 2. Tier 2: Project-Specific Domain Plugins (Pluggable)
        self.domain_guardians: List[BaseGuardian] = []
        self._auto_detect_domain_plugin()

    def _auto_detect_domain_plugin(self) -> None:
        """Detects and registers project-specific domain guardians."""
        # Detect Airbnb project
        if os.path.exists(os.path.join(self.app_root, "src", "components", "BookingWidget.jsx")) or \
           os.path.exists(os.path.join(self.app_root, "src", "lib", "bookingEngine.js")):
            self.domain_guardians.append(AirbnbDomainGuardian())
            logger.info("Loaded project-specific domain plugin: AirbnbDomainGuardian")

    def register_guardian(self, guardian: BaseGuardian) -> None:
        """Allows dynamic registration of custom project guardians."""
        self.domain_guardians.append(guardian)

    def get_db_connection(self) -> Optional[sqlite3.Connection]:
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Runs all Universal Guardians and Domain Plugins."""
        start_t = time.perf_counter()
        db_conn = self.get_db_connection()

        all_issues: List[GuardianIssue] = []
        universal_issues: List[GuardianIssue] = []
        domain_issues: List[GuardianIssue] = []

        try:
            # 1. Execute Tier 1 Universal Guardians
            for guard in self.universal_guardians:
                try:
                    res = guard.run_check(self.app_root, db_conn)
                    universal_issues.extend(res)
                    all_issues.extend(res)
                except Exception as e:
                    logger.error(f"Error in universal guard {guard.name}: {e}")

            # 2. Execute Tier 2 Project-Specific Domain Guardians
            for guard in self.domain_guardians:
                try:
                    res = guard.run_check(self.app_root, db_conn)
                    domain_issues.extend(res)
                    all_issues.extend(res)
                except Exception as e:
                    logger.error(f"Error in domain guard {guard.name}: {e}")

        finally:
            if db_conn:
                db_conn.close()

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        healed = sum(1 for iss in all_issues if iss.auto_healed)

        return {
            "status": "healthy" if len(all_issues) == 0 else "issues_detected",
            "execution_time_ms": round(elapsed_ms, 2),
            "summary": {
                "total_issues": len(all_issues),
                "universal_issues": len(universal_issues),
                "domain_issues": len(domain_issues),
                "auto_healed_count": healed,
                "critical_count": sum(1 for iss in all_issues if iss.severity == "critical"),
                "high_count": sum(1 for iss in all_issues if iss.severity == "high"),
            },
            "issues": [iss.to_dict() for iss in all_issues],
            "guardians_executed": [g.name for g in self.universal_guardians + self.domain_guardians]
        }


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    db = sys.argv[2] if len(sys.argv) > 2 else os.path.join(target, "data", "airbnb.db")

    engine = MagdaGuardianEngine(app_root=target, db_path=db)
    report = engine.run_full_diagnostics()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
