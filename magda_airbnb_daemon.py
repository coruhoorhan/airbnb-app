#!/usr/bin/env python3
"""
Magda-Agent 7/24 Autonomous Fullstack Guardian Daemon.

Continuously monitors:
1. Frontend & Backend codebase with Inception Labs Mercury-2 LLM Code Reviewer.
2. Codebase syntax & AST integrity (Aider Smoke Tester).
3. Database consistency, booking date conflicts & 0 TL price auto-healing.
4. Task queue in agent_tasks.json for autonomous Jules/Codex execution.
"""

import ast
import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import logging
import os
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [🤖 MagdaDaemon]: %(message)s")
logger = logging.getLogger("MagdaDaemon")

APP_ROOT = os.environ.get("AIRBNB_APP_ROOT", "/opt/airbnb-app" if os.path.exists("/opt/airbnb-app") else os.path.abspath("."))
DB_PATH = os.environ.get("AIRBNB_DB_PATH", os.path.join(APP_ROOT, "data", "airbnb.db") if os.path.exists(os.path.join(APP_ROOT, "data", "airbnb.db")) else os.path.join(APP_ROOT, "operations.sqlite3"))
TASKS_MANIFEST_PATH = os.environ.get("AIRBNB_TASKS_PATH", os.path.join(APP_ROOT, "agent_tasks.json"))

# Dynamic loader for standalone Magda modules
def _load_magda_module(rel_path: str, module_name: str):
    base_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "magda_agent", rel_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path),
        os.path.join("/root/magda-agent/magda_agent", rel_path),
        os.path.join("/opt/airbnb-app/magda_agent", rel_path),
    ]
    for p in base_paths:
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location(module_name, p)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    return None

# Load available cognitive modules
_llm_mod = _load_magda_module("llm_client.py", "llm_client")
LLMClient = getattr(_llm_mod, "LLMClient", None) if _llm_mod else None

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
    """Manages reading and updating agent_tasks.json."""

    def __init__(self, manifest_path: str = TASKS_MANIFEST_PATH):
        self.manifest_path = manifest_path

    def load_manifest(self) -> Dict[str, Any]:
        if not os.path.exists(self.manifest_path):
            initial_data = {
                "schema_version": 1,
                "project": "airbnb-fatsa-clone",
                "task_source_priority": ["agent_tasks.json", "AGENTS.md", "MASTER_ROADMAP.md"],
                "risk_levels": ["low", "medium", "high", "critical"],
                "merge_policy": {
                    "low": "auto_merge_after_tests",
                    "medium": "auto_merge_after_tests",
                    "high": "human_review_required",
                    "critical": "manual_only",
                },
                "replenishment_policy": {
                    "minimum_todo_tasks": 3,
                    "batch_size": 3,
                    "always_add_tasks": False,
                    "tasks_per_run": 1,
                    "allowed_risks_for_generated_tasks": ["low", "medium"],
                    "instruction": "Add new todo tasks ONLY when the pool falls below minimum_todo_tasks.",
                    "max_todo_tasks": 50,
                },
                "archived_tasks": [],
                "tasks": [],
            }
            self.save_manifest(initial_data)
            return initial_data

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {self.manifest_path}: {e}")
            return {"schema_version": 1, "project": "airbnb-fatsa-clone", "tasks": []}

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
        archived = manifest.get("archived_tasks", [])

        # Check if task ID already exists
        if any(t.get("id") == task_id for t in tasks) or any(t.get("id") == task_id for t in archived):
            return False

        new_task = {
            "id": task_id,
            "status": "todo",
            "area": area,
            "risk": risk,
            "title": title,
            "description": description,
            "allowed_paths": allowed_paths or ["server.js", "src/lib/db.js", "agent_tasks.json"],
            "acceptance": acceptance or ["Code implementation verified by AST smoke tests and automated build."],
            "created_at": time.time(),
            "created_by": "Magda Fullstack LLM Watchdog",
        }

        tasks.append(new_task)
        manifest["tasks"] = tasks
        self.save_manifest(manifest)
        logger.info(f"Generated new autonomous task in agent_tasks.json: [{task_id}] {title}")
        return True


class FullstackLLMCodeReviewer:
    """7/24 Senior Fullstack Engineer powered by Inception Labs Mercury-2 LLM."""

    def __init__(self, app_root: str = APP_ROOT):
        self.app_root = app_root
        self.llm = LLMClient() if LLMClient else None

    def _read_file_snippet(self, rel_path: str, max_lines: int = 120) -> str:
        full_p = os.path.join(self.app_root, rel_path)
        if not os.path.exists(full_p):
            return ""
        try:
            with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return "".join(lines[:max_lines])
        except Exception:
            return ""

    async def analyze_and_propose_improvements(self, existing_task_ids: Set[str]) -> List[Dict[str, Any]]:
        """Analyzes codebase with Mercury-2 LLM and proposes structured tasks."""
        if not self.llm:
            logger.warning("LLMClient not available for LLM code review.")
            return []

        # Gather codebase snapshots
        server_code = self._read_file_snippet("server.js", 150)
        db_code = self._read_file_snippet("src/lib/db.js", 100)
        app_jsx = self._read_file_snippet("App.jsx", 100)

        prompt = f"""You are a Senior Fullstack Principal Engineer & Security Architect reviewing the Airbnb Fatsa Clone project.

CURRENT CODEBASE SNAPSHOT:
--- server.js ---
{server_code}

--- src/lib/db.js ---
{db_code}

--- App.jsx ---
{app_jsx}

EXISTING TASKS ALREADY CREATED (DO NOT DUPLICATE THESE):
{list(existing_task_ids)}

TASK:
Identify exactly 1-2 critical, high-impact improvements (Frontend UX/Responsive, Backend Performance/API, or Security).
Return ONLY a valid JSON array of objects with the exact schema:
[
  {{
    "id": "feat-or-fix-unique-slug",
    "area": "frontend" | "backend" | "security",
    "risk": "low" | "medium",
    "title": "Short descriptive title in Turkish or English",
    "description": "Concrete technical description of what to implement and why",
    "allowed_paths": ["server.js", "src/components/...", "agent_tasks.json"],
    "acceptance": ["Verification criteria 1", "Verification criteria 2"]
  }}
]
Do NOT return any explanation or markdown wrapping outside JSON. Only the JSON array."""

        try:
            raw_resp = await self.llm.generate(prompt, temperature=0.3, max_tokens=1024)
            cleaned = raw_resp.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```json\s*", "", cleaned)
                cleaned = re.sub(r"^```\s*", "", cleaned)
                cleaned = re.sub(r"```$", "", cleaned).strip()

            tasks = json.loads(cleaned)
            if isinstance(tasks, list):
                valid_tasks = []
                for t in tasks:
                    if t.get("id") and t.get("title") and t.get("id") not in existing_task_ids:
                        valid_tasks.append(t)
                return valid_tasks
        except Exception as e:
            logger.warning(f"LLM Fullstack Review parse error: {e}")

        return []


class MagdaAutonomousWatchdog:
    """7/24 System Watchdog scanning database, payments, and codebase syntax with LLM Intelligence."""

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
        self.llm_reviewer = FullstackLLMCodeReviewer(app_root)
        self._last_scan_result: Dict[str, Any] = {}
        self._is_running = False
        self._llm_scan_counter = 0

    def get_connection(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.db_path):
            return None
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

        conn = self.get_connection()
        if not conn:
            return detected, healed_count

        now = int(time.time())

        try:
            # 1. Booking date conflicts
            try:
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
                    self._record_guardian_issue(conn, "Booking Date Conflict", desc, severity="high")
                    self.manifest_mgr.add_task(
                        task_id=task_id,
                        title=f"Resolve Booking Conflict #{c['b1_id']} vs #{c['b2_id']}",
                        description=desc,
                        area="backend",
                        risk="high",
                        allowed_paths=["src/lib/bookingEngine.js", "server.js", "agent_tasks.json"],
                        acceptance=["Booking conflict is resolved and overlapping booking refunded or rescheduled."],
                    )
                    detected.append({"type": "booking_conflict", "description": desc, "task_id": task_id})
            except Exception:
                pass

            # 2. Zero-Price Listings Auto-Heal
            try:
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
            except Exception:
                pass

            # 3. Expired Active Coupons Auto-Deactivate
            try:
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
            except Exception:
                pass

            # 4. Failed iyzico payments with confirmed bookings check
            try:
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
                        allowed_paths=["server.js", "src/lib/db.js", "agent_tasks.json"],
                        acceptance=["Payment reconciliation verified with iyzico payment gateway API."],
                    )
                    detected.append({"type": "payment_anomaly", "description": desc, "task_id": task_id})
            except Exception:
                pass

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

    async def execute_full_scan(self) -> Dict[str, Any]:
        """Executes a full diagnostic and health scan across codebase, database, and tasks."""
        start_t = time.perf_counter()
        logger.info("Executing Magda-Agent Autonomous Watchdog Full Scan...")
        db_issues, healed_count = self.scan_database_and_payments()
        syntax_errors = self.scan_codebase_syntax()

        manifest_data = self.manifest_mgr.load_manifest()
        tasks = manifest_data.get("tasks", [])
        archived = manifest_data.get("archived_tasks", [])
        existing_ids = {t["id"] for t in tasks}.union({t["id"] for t in archived})

        # LLM Fullstack Review Cycle (run if todo pool is low or periodically)
        todo_tasks = [t for t in tasks if t.get("status") == "todo"]
        self._llm_scan_counter += 1
        llm_proposed_count = 0

        logger.info("Triggering Inception Labs Mercury-2 Fullstack AI Code Reviewer...")
        new_llm_tasks = await self.llm_reviewer.analyze_and_propose_improvements(existing_ids)
        for nt in new_llm_tasks:
            success = self.manifest_mgr.add_task(
                task_id=nt["id"],
                title=nt["title"],
                description=nt["description"],
                area=nt.get("area", "backend"),
                risk=nt.get("risk", "medium"),
                allowed_paths=nt.get("allowed_paths"),
                acceptance=nt.get("acceptance"),
            )
            if success:
                llm_proposed_count += 1
                logger.info(f"✨ LLM Reviewer added new task: [{nt['id']}] {nt['title']}")

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
                "llm_tasks_proposed": llm_proposed_count,
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
            f"Full scan complete in {elapsed:.1f}ms. DB anomalies: {len(db_issues)}, "
            f"auto-healed: {healed_count}, LLM tasks generated: {llm_proposed_count}. Active todo tasks: {len(todo_tasks)}"
        )
        return result

    async def run_loop(self, interval_seconds: int = 60) -> None:
        """7/24 Continuous Autonomous Background Loop."""
        self._is_running = True
        logger.info(f"Starting Magda-Agent 7/24 Watchdog Daemon with Mercury-2 LLM (Interval: {interval_seconds}s)")

        while self._is_running:
            try:
                await self.execute_full_scan()
            except Exception as e:
                logger.error(f"Error in watchdog cycle: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._is_running = False
        logger.info("Stopping Magda-Agent Watchdog Daemon.")


def main():
    watchdog = MagdaAutonomousWatchdog()

    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        res = asyncio.run(watchdog.execute_full_scan())
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
