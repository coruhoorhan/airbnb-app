"""
Comprehensive Unit Test Suite for Tier-1 AutoHealer & Self-Healing Engine.
Tests missing import resolution, database schema healing, price baseline repair,
expired coupon deactivation, and rollback with Tier-2 task escalation.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from magda_agent.guardian.auto_healer import (
    AutoHealer,
    DbSchemaHealer,
    ExpiredCouponHealer,
    MissingImportHealer,
    ZeroPriceHealer,
)


class TestAutoHealerEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="auto_healer_test_")
        self.app_root = Path(self.test_dir)

        # Setup mock app structure
        (self.app_root / "src" / "lib").mkdir(parents=True, exist_ok=True)
        (self.app_root / "data").mkdir(parents=True, exist_ok=True)

        self.db_path = self.app_root / "data" / "airbnb.db"
        self._init_mock_db()

        self.tasks_path = self.app_root / "agent_tasks.json"
        self.tasks_path.write_text(json.dumps({"tasks": [], "archived_tasks": []}))

        self.auto_healer = AutoHealer(
            app_root=str(self.app_root),
            db_path=str(self.db_path),
            tasks_manifest_path=str(self.tasks_path),
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _init_mock_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                pricePerNight INTEGER,
                isPublished INTEGER DEFAULT 1
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discountPercent INTEGER,
                expiryDate TEXT,
                isActive INTEGER DEFAULT 1
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guardian_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                severity TEXT,
                title TEXT,
                description TEXT,
                suggestion TEXT,
                status TEXT DEFAULT 'open',
                autoHealed INTEGER DEFAULT 0,
                createdAt TEXT
            );
        """)
        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # 1. Missing Import Healer
    # -------------------------------------------------------------------------
    def test_missing_import_healer(self):
        # 1. Create source file exporting calculateCancellationRefund
        lib_file = self.app_root / "src" / "lib" / "refundEngine.js"
        lib_file.write_text("export function calculateCancellationRefund(booking) { return 100; }\n")

        # 2. Create target server.js missing the import
        server_file = self.app_root / "server.js"
        server_file.write_text('import express from "express";\n\nconst app = express();\n')

        context = {
            "error": "ReferenceError: calculateCancellationRefund is not defined",
            "file": "server.js",
        }

        healer = MissingImportHealer(self.app_root, self.db_path)
        self.assertTrue(healer.can_heal(context))

        result = healer.heal(context)
        self.assertTrue(result.get("healed"))
        self.assertEqual(result.get("symbol"), "calculateCancellationRefund")

        new_server_code = server_file.read_text()
        self.assertIn("import { calculateCancellationRefund }", new_server_code)

    # -------------------------------------------------------------------------
    # 2. Database Schema Healer
    # -------------------------------------------------------------------------
    def test_db_schema_healer_missing_column(self):
        context = {
            "error": "sqlite3.OperationalError: no such column: listings.instantBookable",
            "table": "listings",
        }

        healer = DbSchemaHealer(self.app_root, self.db_path)
        self.assertTrue(healer.can_heal(context))

        result = healer.heal(context)
        self.assertTrue(result.get("healed"))

        # Verify column added
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.execute("PRAGMA table_info(listings);")
        columns = [row[1] for row in cur.fetchall()]
        conn.close()

        self.assertIn("instantBookable", columns)

    # -------------------------------------------------------------------------
    # 3. Zero-Price Healer
    # -------------------------------------------------------------------------
    def test_zero_price_healer(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("INSERT INTO listings (title, pricePerNight, isPublished) VALUES ('Villa Fatsa', 0, 1);")
        conn.commit()
        conn.close()

        context = {"type": "zero_price_detected", "description": "İlan #1 için geçersiz 0 TL fiyat"}
        healer = ZeroPriceHealer(self.app_root, self.db_path)
        self.assertTrue(healer.can_heal(context))

        result = healer.heal(context)
        self.assertTrue(result.get("healed"))
        self.assertEqual(result.get("fixed_count"), 1)

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT pricePerNight FROM listings WHERE title = 'Villa Fatsa'").fetchone()
        conn.close()
        self.assertEqual(row[0], 1000)

    # -------------------------------------------------------------------------
    # 4. Expired Coupon Healer
    # -------------------------------------------------------------------------
    def test_expired_coupon_healer(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("INSERT INTO coupons (code, discountPercent, expiryDate, isActive) VALUES ('SUMMER2020', 20, '2020-01-01', 1);")
        conn.commit()
        conn.close()

        context = {"type": "coupon_check", "description": "Süresi dolmuş kupon kontrolü"}
        healer = ExpiredCouponHealer(self.app_root, self.db_path)
        self.assertTrue(healer.can_heal(context))

        result = healer.heal(context)
        self.assertTrue(result.get("healed"))
        self.assertEqual(result.get("deactivated_count"), 1)

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT isActive FROM coupons WHERE code = 'SUMMER2020'").fetchone()
        conn.close()
        self.assertEqual(row[0], 0)

    # -------------------------------------------------------------------------
    # 5. Rollback & Tier-2 Escalation
    # -------------------------------------------------------------------------
    def test_tier2_escalation_on_unhandled_error(self):
        unhandled_issue = {
            "title": "Severe Memory Leak in Image Compressor",
            "type": "unhandled_crash",
            "error": "SIGSEGV in libvips native extension",
        }

        res = self.auto_healer.detect_and_heal(unhandled_issue)
        self.assertFalse(res.get("healed"))
        self.assertEqual(res.get("action"), "escalated_to_tier2")
        self.assertTrue(res.get("task_id").startswith("tier2-escalation-"))

        # Verify task added to agent_tasks.json
        manifest_data = json.loads(self.tasks_path.read_text())
        tasks = manifest_data.get("tasks", [])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], res.get("task_id"))
        self.assertEqual(tasks[0]["risk"], "high")


if __name__ == "__main__":
    unittest.main()
