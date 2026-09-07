import shutil
from magda_agent.guardian.guardian_runner import MagdaGuardianEngine
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
import subprocess
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
    """7/24 Senior Fullstack Principal Engineer & Architect powered by Inception Labs Mercury-2 LLM."""

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

    async def analyze_and_propose_improvements(
        self,
        existing_tasks: List[Dict[str, Any]],
        existing_task_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Analyzes fullstack codebase with Mercury-2 LLM and proposes structured tasks for Jules."""
        if not self.llm:
            logger.warning("LLMClient not available for LLM code review.")
            return []

        # Gather rich multi-layer codebase snapshots
        server_code = self._read_file_snippet("server.js", 120)
        db_code = self._read_file_snippet("src/lib/db.js", 100)
        app_jsx = self._read_file_snippet("src/App.jsx", 100)
        booking_widget = self._read_file_snippet("src/components/BookingWidget.jsx", 60)
        pricing_engine = self._read_file_snippet("src/lib/pricingEngine.js", 60)

        # Existing task summary for full deduplication awareness
        tasks_summary = "\n".join([
            f"- [{t.get('status', 'todo')}] {t.get('id')}: {t.get('title')} ({t.get('area', 'feature')})"
            for t in existing_tasks
        ])

        prompt = f"""You are Magda-Agent's 7/24 Principal Architect & Fullstack Guardian reviewing the Airbnb Fatsa Clone application (React, Vite, Node.js, Express, SQLite, GraphQL).

CURRENT CODEBASE SNAPSHOTS:
--- server.js ---
{server_code}

--- src/lib/db.js ---
{db_code}

--- src/App.jsx ---
{app_jsx}

--- src/components/BookingWidget.jsx ---
{booking_widget}

--- src/lib/pricingEngine.js ---
{pricing_engine}

EXISTING TASKS IN MANIFEST (DO NOT DUPLICATE OR PROPOSE SIMILAR TASKS):
{tasks_summary}

MISSION:
Identify exactly 1 high-value, novel, and concrete product or architectural capability for the Airbnb application (e.g., Host Payout & Revenue Analytics, Interactive Map Clustering, Multi-currency Checkout, Guest Review Moderation, Push Notification Engine, Calendar Availability iCal Sync, Instant Booking Approval Flow).

Return ONLY a valid JSON array with exactly 1 task object adhering strictly to the schema:
[
  {{
    "id": "feat-or-fix-unique-descriptive-slug",
    "area": "frontend" | "backend" | "fullstack" | "security",
    "risk": "low" | "medium",
    "title": "Clear concise descriptive title",
    "description": "Concrete technical description of what to implement, which files to modify, and the expected behavior",
    "allowed_paths": ["server.js", "src/components/...", "src/lib/...", "agent_tasks.json"],
    "acceptance": ["Concrete verification step 1", "Concrete verification step 2"]
  }}
]
Output ONLY raw JSON array. No markdown fences, no explanatory text."""

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
                    tid = t.get("id", "")
                    if tid and t.get("title") and tid not in existing_task_ids:
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
        self.guardian_engine = MagdaGuardianEngine(app_root=self.app_root, db_path=self.db_path)
        self._last_scan_result: Dict[str, Any] = {}
        self._is_running = False
        self._llm_scan_counter = 0
        self._scan_count = 0

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
                    WHERE b1.status = 'confirmed' AND b2.status = 'confirmed' AND b1.id NOT LIKE '%test%' AND b1.id NOT LIKE 'book_rec_%' AND b2.id NOT LIKE '%test%' AND b2.id NOT LIKE 'book_rec_%' 
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

    def _git_commit_and_push(self, message: str) -> bool:
        """Commits agent_tasks.json changes and pushes to origin/main."""
        try:
            # Validate agent_tasks.json before committing
            validator_script = os.path.join(self.app_root, "scripts", "validate_agent_tasks.py")
            manifest_file = os.path.join(self.app_root, "agent_tasks.json")
            if os.path.exists(validator_script) and os.path.exists(manifest_file):
                v_res = subprocess.run(
                    [sys.executable, validator_script, manifest_file],
                    cwd=self.app_root,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if v_res.returncode != 0:
                    logger.error(f"Task validation failed before push: {v_res.stderr or v_res.stdout}. Skipping push.")
                    return False

            subprocess.run(["git", "add", "agent_tasks.json"], cwd=self.app_root, check=True, capture_output=True, text=True, timeout=15)
            # Check if there is anything to commit
            status_res = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=self.app_root)
            if status_res.returncode == 0:
                logger.info("No staged changes to commit for agent_tasks.json.")
                return False

            commit_res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.app_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            logger.info(f"Git commit successful: {commit_res.stdout.strip()}")

            push_res = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=self.app_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            logger.info(f"Git push successful: {push_res.stdout.strip() or 'OK'}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit/push failed (exit {e.returncode}): {e.stderr or e.stdout}")
            return False
        except Exception as e:
            logger.error(f"Git commit/push unexpected error: {e}")
            return False

    def _git_pull(self) -> bool:
        """Pulls latest changes from origin/main with automatic backup and stash resilience."""
        try:
            # 1. Automated DB Backup before pulling new migrations
            if self.db_path and os.path.exists(self.db_path):
                backup_dir = os.path.join(self.app_root, "data", "backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(backup_dir, f"airbnb_backup_{int(time.time())}.db")
                shutil.copy2(self.db_path, backup_file)
                # Keep only last 5 backups
                backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")])
                for old_b in backups[:-5]:
                    try:
                        os.remove(old_b)
                    except Exception:
                        pass

            # 2. Stash local changes to prevent pull conflicts
            subprocess.run(["git", "stash"], cwd=self.app_root, capture_output=True, text=True, timeout=15)

            logger.info("Executing robust git pull origin main...")
            res = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.app_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            logger.info(f"Git pull result: {res.stdout.strip()}")

            # 3. If pull brought updates, rebuild frontend
            if "Already up to date." not in res.stdout:
                logger.info("New updates pulled from main. Triggering npm run build...")
                subprocess.run(["npm", "run", "build"], cwd=self.app_root, capture_output=True, text=True, timeout=60)

            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git pull failed (exit {e.returncode}): {e.stderr or e.stdout}")
            return False
        except Exception as e:
            logger.warning(f"Git pull error: {e}")
            return False

    async def execute_full_scan(self) -> Dict[str, Any]:
        """Executes a full diagnostic and health scan across codebase, database, and tasks."""
        start_t = time.perf_counter()
        logger.info("Executing Magda-Agent Autonomous Watchdog Full Scan...")
        diag_report = self.guardian_engine.run_full_diagnostics()
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

        # 7/24 Autonomous Magda Brain: Propose next improvements when queue is low or on schedule
        should_run_llm = len(todo_tasks) < 5 or (self._llm_scan_counter % 5 == 0)
        new_llm_tasks = []
        if should_run_llm:
            logger.info("🧠 Triggering Inception Labs Mercury-2 Fullstack AI Code Reviewer...")
            new_llm_tasks = await self.llm_reviewer.analyze_and_propose_improvements(tasks, existing_ids)
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
                    logger.info(f"✨ Magda Brain added new task: [{nt['id']}] {nt['title']}")

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

        # Count newly added tasks from DB issues that resulted in new tasks
        db_tasks_added = sum(1 for d in db_issues if d.get("task_id"))
        total_new_tasks = llm_proposed_count + db_tasks_added

        if total_new_tasks > 0:
            commit_msg = f"chore(daemon): auto-sync task queue — {total_new_tasks} new task(s)"
            logger.info(f"New tasks detected ({total_new_tasks}). Triggering auto-sync commit & push...")
            self._git_commit_and_push(commit_msg)

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
                self._scan_count += 1
                if self._scan_count % 10 == 0:
                    self._git_pull()
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
