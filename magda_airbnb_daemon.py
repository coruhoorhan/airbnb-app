#!/usr/bin/env python3
"""
Magda-Agent 7/24 Autonomous Daemon & Task Engine.

Continuously monitors the Airbnb application (Database, Payments, Codebase Syntax,
User Inquiries) on 10.0.2.1:
1. Scans SQLite database and iyzico payment reconciliation.
2. Runs AST syntax checks across all codebase files.
3. Automatically generates structured tasks in /opt/airbnb-app/airbnb_tasks.json.
4. Auto-heals safe runtime issues and logs incidents to guardian_issues table.
5. Emits real-time cognitive metrics for the Admin Dashboard.
"""

import ast
import asyncio
import importlib.util
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [🤖 MagdaDaemon]: %(message)s")
logger = logging.getLogger("MagdaDaemon")

DB_PATH = "/opt/airbnb-app/data/airbnb.db"
APP_ROOT = "/opt/airbnb-app"
TASKS_MANIFEST_PATH = "/opt/airbnb-app/airbnb_tasks.json"

# Dynamic loader for standalone Magda modules
def _load_magda_module(rel_path: str, module_name: str):
    base_paths = [
        "/opt/airbnb-app/magda_agent",
        "/root/magda-agent/magda_agent",
        os.path.join(os.path.dirname(__file__), "magda_agent"),
    ]
    for bp in base_paths:
        full_p = os.path.join(bp, rel_path)
        if os.path.exists(full_p):
            spec = importlib.util.spec_from_file_location(module_name, full_p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None

# Load available modules
_smoke_mod = _load_magda_module("evaluation/smoke_tester_v1.py", "smoke_tester_v1")
AiderPostMergeSmokeTesterV1 = getattr(_smoke_mod, "AiderPostMergeSmokeTesterV1", None) if _smoke_mod else None

_acs_mod = _load_magda_module("safety/acs_guard_runtime_v7.py", "acs_guard_runtime_v7")
ACSGuardRuntimeV7 = getattr(_acs_mod, "ACSGuardRuntimeV7", None) if _acs_mod else None

_rl_mod = _load_magda_module("learning/online_rl_context_v2.py", "online_rl_context_v2")
OnlineRLContextEngineV2 = getattr(_rl_mod, "OnlineRLContextEngineV2", None) if _rl_mod else None

_mem_mod = _load_magda_module("memory/virtual_compression_v5.py", "virtual_compression_v5")
MemGPTVirtualContextSemanticCompressorV5 = getattr(_mem_mod, "MemGPTVirtualContextSemanticCompressorV5", None) if _mem_mod else None
try:
    from magda_airbnb_codebase_indexer import AirbnbCodebaseIndexer
except ImportError:
    AirbnbCodebaseIndexer = None


class AirbnbTasksManifestManager:
    """Manages reading and updating airbnb_tasks.json."""

    def __init__(self, manifest_path: str = TASKS_MANIFEST_PATH):
        self.manifest_path = manifest_path

    def load_manifest(self) -> Dict[str, Any]:
        if not os.path.exists(self.manifest_path):
            initial_data = {
                "project": "airbnb-fatsa-clone",
                "version": "1.0.0",
                "updated_at": time.time(),
                "tasks": [
                    {
                        "id": "task-01-database-schema",
                        "status": "done",
                        "area": "backend",
                        "title": "SQLite WAL Database Schema & iyzico Payments",
                        "description": "Initialize relational schema for users, listings, bookings, reviews, and payments.",
                        "allowed_paths": ["src/lib/db.js", "server.js", "airbnb_tasks.json"],
                        "acceptance": ["All tables created with foreign key references."],
                    }
                ],
            }
            self.save_manifest(initial_data)
            return initial_data

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {self.manifest_path}: {e}")
            return {"project": "airbnb-fatsa-clone", "tasks": []}

    def save_manifest(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = time.time()
        temp_path = f"{self.manifest_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, self.manifest_path)

    def add_task(
        self,
        task_id: str,
        title: str,
        description: str,
        area: str = "backend",
        risk: str = "medium",
        allowed_paths: Optional[List[str]] = None,
        acceptance: Optional[List[str]] = None,
    ) -> bool:
        manifest = self.load_manifest()
        tasks = manifest.get("tasks", [])

        # Check if task ID already exists
        if any(t.get("id") == task_id for t in tasks):
            return False

        new_task = {
            "id": task_id,
            "status": "todo",
            "area": area,
            "risk": risk,
            "title": title,
            "description": description,
            "allowed_paths": allowed_paths or ["server.js", "src/lib/db.js", "airbnb_tasks.json"],
            "acceptance": acceptance or ["Code implementation verified by AST smoke tests."],
            "created_at": time.time(),
            "created_by": "Magda Autonomous Watchdog",
        }

        tasks.append(new_task)
        manifest["tasks"] = tasks
        self.save_manifest(manifest)
        logger.info(f"Generated new autonomous task in airbnb_tasks.json: [{task_id}] {title}")
        return True


class MagdaAutonomousWatchdog:
    """7/24 System Watchdog scanning database, payments, and codebase syntax."""

    def __init__(
        self,
        db_path: str = DB_PATH,
        app_root: str = APP_ROOT,
        manifest_path: str = TASKS_MANIFEST_PATH,
    ):
        self.db_path = db_path
        self.app_root = app_root
        self.manifest_mgr = AirbnbTasksManifestManager(manifest_path)
        self.smoke_tester = AiderPostMergeSmokeTesterV1() if AiderPostMergeSmokeTesterV1 else None
        self.code_indexer = AirbnbCodebaseIndexer(app_root) if AirbnbCodebaseIndexer else None
        self._last_scan_result: Dict[str, Any] = {}
        self._is_running = False

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def scan_codebase_syntax(self) -> List[Dict[str, Any]]:
        """Scans all Python and JavaScript files for AST syntax errors."""
        errors = []
        if self.smoke_tester:
            report = self.smoke_tester.test_directory(self.app_root, recursive=True)
            for r in report.results:
                if not r.passed:
                    errors.append({
                        "file": r.file_path,
                        "error": r.error_message,
                        "line": r.line_number,
                    })
        return errors

    def scan_database_and_payments(self) -> Tuple[List[Dict[str, Any]], int]:
        """Scans database for integrity violations, payment anomalies, and booking conflicts."""
        detected = []
        healed_count = 0

        if not os.path.exists(self.db_path):
            return detected, healed_count

        conn = self.get_connection()
        now = int(time.time())

        try:
            # 1. Booking date conflicts
            conflicts = conn.execute("""
                SELECT b1.id AS b1_id, b2.id AS b2_id, b1.listingId, b1.checkIn, b1.checkOut 
                FROM bookings b1 
                JOIN bookings b2 ON b1.listingId = b2.listingId AND b1.id < b2.id 
                WHERE b1.status = 'confirmed' AND b2.status = 'confirmed' 
                AND b1.checkIn < b2.checkOut AND b1.checkOut > b2.checkIn
            """).fetchall()

            for c in conflicts:
                task_id = f"fix-booking-conflict-{c['b1_id']}-{c['b2_id']}"
                desc = f"Çakışan rezervasyon tespit edildi: #{c['b1_id']} ve #{c['b2_id']} (İlan #{c['listingId']}). Tarihler: {c['checkIn']} - {c['checkOut']}"
                
                # Insert issue into guardian_issues
                self._record_guardian_issue(conn, "Booking Date Conflict", desc, severity="high")
                
                # Auto-generate task into airbnb_tasks.json
                self.manifest_mgr.add_task(
                    task_id=task_id,
                    title=f"Resolve Booking Conflict #{c['b1_id']} vs #{c['b2_id']}",
                    description=desc,
                    area="backend",
                    risk="high",
                    allowed_paths=["src/lib/bookingEngine.js", "server.js", "airbnb_tasks.json"],
                    acceptance=["Booking conflict is resolved and overlapping booking refunded or rescheduled."],
                )
                detected.append({"type": "booking_conflict", "description": desc, "task_id": task_id})

            # 2. Zero-Price Listings Auto-Heal
            zero_prices = conn.execute(
                "SELECT id, title FROM listings WHERE isPublished = 1 AND (pricePerNight <= 0 OR pricePerNight IS NULL)"
            ).fetchall()

            for zp in zero_prices:
                desc = f"İlan #{zp['id']} ({zp['title']}) için geçersiz 0 TL fiyat tespit edildi ve otomatik olarak 1.000 TL taban fiyatla onarıldı."
                conn.execute("UPDATE listings SET pricePerNight = 1000 WHERE id = ?", (zp["id"],))
                conn.commit()
                healed_count += 1
                self._record_guardian_issue(conn, "Zero-Price Listing Auto-Healed", desc, severity="medium", auto_heal=True)
                detected.append({"type": "zero_price_healed", "description": desc})

            # 3. Expired Active Coupons Auto-Deactivate
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            expired_coupons = conn.execute(
                "SELECT code FROM coupons WHERE isActive = 1 AND expiryDate < ?", (today_str,)
            ).fetchall()

            for ec in expired_coupons:
                desc = f"Süresi dolmuş kupon otomatik olarak deaktive edildi: {ec['code']}"
                conn.execute("UPDATE coupons SET isActive = 0 WHERE code = ?", (ec["code"],))
                conn.commit()
                healed_count += 1
                self._record_guardian_issue(conn, "Expired Coupon Auto-Deactivated", desc, severity="low", auto_heal=True)
                detected.append({"type": "coupon_deactivated", "description": desc})

            # 4. Failed iyzico payments with confirmed bookings check
            failed_payments = conn.execute("""
                SELECT b.id AS booking_id, b.totalPrice, b.guestId 
                FROM bookings b 
                LEFT JOIN payments p ON b.id = p.bookingId 
                WHERE b.status = 'confirmed' AND (p.status = 'failed' OR p.id IS NULL)
            """).fetchall()

            for fp in failed_payments:
                task_id = f"reconcile-payment-booking-{fp['booking_id']}"
                desc = f"Ödemesi başarısız veya eksik olan onaylı rezervasyon: #{fp['booking_id']} (Tutar: {fp['totalPrice']} TL)"
                self._record_guardian_issue(conn, "Unpaid Confirmed Booking Anomaly", desc, severity="high")
                self.manifest_mgr.add_task(
                    task_id=task_id,
                    title=f"Reconcile Payment for Booking #{fp['booking_id']}",
                    description=desc,
                    area="backend",
                    risk="high",
                    allowed_paths=["server.js", "src/lib/db.js", "airbnb_tasks.json"],
                    acceptance=["Payment reconciliation verified with iyzico payment gateway API."],
                )
                detected.append({"type": "payment_anomaly", "description": desc, "task_id": task_id})

        finally:
            conn.close()

        return detected, healed_count

    def _record_guardian_issue(
        self,
        conn: sqlite3.Connection,
        title: str,
        description: str,
        severity: str = "medium",
        auto_heal: bool = False,
    ) -> None:
        try:
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO guardian_issues (type, severity, title, description, suggestion, status, autoHealed, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("auto_watchdog", severity, title, description, "Auto-generated by Magda 7/24 Watchdog", "healed" if auto_heal else "open", 1 if auto_heal else 0, now_iso),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to record guardian issue: {e}")

    def execute_full_scan(self) -> Dict[str, Any]:
        """Executes a full diagnostic and health scan across codebase, database, and tasks."""
        start_t = time.perf_counter()
        logger.info("Executing Magda-Agent Autonomous Watchdog Full Scan...")
        db_issues, healed_count = self.scan_database_and_payments()
        syntax_errors = self.scan_codebase_syntax()
        code_vulnerabilities = []
        if self.code_indexer:
            code_vulnerabilities = self.code_indexer.scan_codebase_vulnerabilities_and_smells()
            for cv in code_vulnerabilities[:3]:
                task_id = f"auto-fix-{cv['type']}"
                self.manifest_mgr.add_task(
                    task_id=task_id,
                    title=cv["title"],
                    description=cv["description"],
                    area="security",
                    risk="medium",
                    allowed_paths=["server.js", "airbnb_tasks.json"],
                    acceptance=[cv["suggested_fix"]],
                )
        manifest_data = self.manifest_mgr.load_manifest()
        tasks = manifest_data.get("tasks", [])
        todo_tasks = [t for t in tasks if t.get("status") == "todo"]
        done_tasks = [t for t in tasks if t.get("status") == "done"]

        elapsed = (time.perf_counter() - start_t) * 1000.0

        result = {
            "status": "scan_complete",
            "timestamp": time.time(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": round(elapsed, 2),
            "summary": {
                "db_issues_detected": len(db_issues),
                "auto_healed_count": healed_count,
                "syntax_errors_detected": len(syntax_errors),
                "total_tasks_in_manifest": len(tasks),
                "todo_tasks_count": len(todo_tasks),
                "done_tasks_count": len(done_tasks),
            },
            "database_issues": db_issues,
            "syntax_errors": syntax_errors,
            "active_todo_tasks": todo_tasks[:5],
        }

        self._last_scan_result = result
        logger.info(
            f"Full scan complete in {elapsed:.1f}ms. Found: {len(db_issues)} DB anomalies, "
            f"{healed_count} auto-healed, {len(syntax_errors)} syntax errors. Todo tasks: {len(todo_tasks)}"
        )
        return result

    async def run_loop(self, interval_seconds: int = 60) -> None:
        """7/24 Continuous Autonomous Background Loop."""
        self._is_running = True
        logger.info(f"Starting Magda-Agent 7/24 Watchdog Daemon (Interval: {interval_seconds}s)")

        while self._is_running:
            try:
                self.execute_full_scan()
            except Exception as e:
                logger.error(f"Error in watchdog cycle: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._is_running = False
        logger.info("Stopping Magda-Agent Watchdog Daemon.")


def main():
    watchdog = MagdaAutonomousWatchdog()

    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        res = watchdog.execute_full_scan()
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if len(sys.argv) > 1 and sys.argv[1] == "tasks":
        manifest = watchdog.manifest_mgr.load_manifest()
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return

    # Run background loop
    interval = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60
    asyncio.run(watchdog.run_loop(interval_seconds=interval))


if __name__ == "__main__":
    main()
