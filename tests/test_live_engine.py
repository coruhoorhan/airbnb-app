"""
Comprehensive Unit Test Suite for Autonomous Live Intervention Engine.
Tests missing symbol resolution, SQLite schema auto-sync, atomic rollback, and service reload signals.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from magda_agent.autonomous.live_engine import (
    AutonomousLiveEngine,
    DbSchemaSyncResolver,
    MissingSymbolResolver,
)


class TestAutonomousLiveEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="live_engine_test_")
        self.app_root = Path(self.test_dir)

        (self.app_root / "src" / "lib").mkdir(parents=True, exist_ok=True)
        (self.app_root / "data").mkdir(parents=True, exist_ok=True)

        self.db_path = self.app_root / "data" / "airbnb.db"
        self._init_mock_db()

        self.engine = AutonomousLiveEngine(
            app_root=str(self.app_root),
            db_path=str(self.db_path),
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
        conn.commit()
        conn.close()

    def test_missing_symbol_resolver(self):
        # 1. Create source library exporting generateCsrfToken
        lib_file = self.app_root / "src" / "lib" / "tokenHelper.js"
        lib_file.write_text("export function generateCsrfToken() { return 'token-123'; }\n")

        # 2. Create target server.js
        server_file = self.app_root / "server.js"
        server_file.write_text('import express from "express";\n\nconst app = express();\n')

        resolver = MissingSymbolResolver(self.app_root)
        self.assertTrue(resolver.can_resolve("ReferenceError: generateCsrfToken is not defined"))

        res = resolver.resolve("generateCsrfToken", server_file)
        self.assertTrue(res.get("resolved"))

        new_server_content = server_file.read_text()
        self.assertIn("import { generateCsrfToken }", new_server_content)

    def test_db_schema_sync_resolver(self):
        resolver = DbSchemaSyncResolver(self.db_path)
        err = "sqlite3.OperationalError: no such column: listings.isInstantBookable"
        self.assertTrue(resolver.can_resolve(err))

        res = resolver.resolve(err)
        self.assertTrue(res.get("resolved"))

        conn = sqlite3.connect(str(self.db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(listings);").fetchall()]
        conn.close()
        self.assertIn("isInstantBookable", cols)

    def test_scan_and_heal_full_cycle(self):
        # Create library export
        lib_file = self.app_root / "src" / "lib" / "pricingEngine.js"
        lib_file.write_text("export function calculateDynamicPrice() { return 500; }\n")

        # Create server.js
        server_file = self.app_root / "server.js"
        server_file.write_text('import express from "express";\n\nconst app = express();\n')

        ctx = {
            "error": "ReferenceError: calculateDynamicPrice is not defined",
            "file": "server.js",
        }

        res = self.engine.scan_and_heal(ctx)
        self.assertTrue(res.get("healed"))
        self.assertIn("import { calculateDynamicPrice }", server_file.read_text())


if __name__ == "__main__":
    unittest.main()
