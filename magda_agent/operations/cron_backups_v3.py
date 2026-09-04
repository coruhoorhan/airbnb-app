"""
Hermes Agent Scheduled Nightly Backups V3.

Inspired by Hermes Agent Cron scheduler architecture: Implements an automated
nightly backup cron job for episodic memory dumps, ensuring persistent state
preservation and disaster recovery.
"""

import asyncio
import inspect
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class BackupRecord:
    """Represents an episodic memory backup archive record."""

    backup_id: str = field(default_factory=lambda: f"bak_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    backup_file: str = ""
    entries_count: int = 0
    status: str = "success"  # success, failed
    size_bytes: int = 0
    error: Optional[str] = None
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EpisodicMemoryCronBackupManagerV3:
    """
    Episodic Memory Scheduled Nightly Backup Manager V3.

    Manages automated cron scheduling and execution of episodic memory dumps.
    """

    def __init__(
        self,
        memory_source: Optional[Any] = None,
        backup_dir: str = "/tmp/magda_episodic_backups_v3",
        cron_expression: str = "0 3 * * *",
        scheduler: Optional[Any] = None,
    ):
        self.memory_source = memory_source
        self.backup_dir = backup_dir
        self.cron_expression = cron_expression
        self.scheduler = scheduler

        os.makedirs(self.backup_dir, exist_ok=True)
        self._backup_history: List[BackupRecord] = []
        self._scheduled_job_id: Optional[str] = None
        self._is_running = False

    def schedule_nightly_backup(
        self,
        cron_expr: Optional[str] = None,
        job_name: str = "nightly_episodic_backup",
    ) -> str:
        """
        Register the episodic memory backup with the cron scheduler.
        """
        expr = cron_expr or self.cron_expression
        self.cron_expression = expr
        self._scheduled_job_id = f"job_{job_name}_{uuid.uuid4().hex[:6]}"

        if self.scheduler:
            if hasattr(self.scheduler, "schedule"):
                try:
                    self.scheduler.schedule(expr, self.perform_backup_async, name=job_name)
                except Exception as ex:
                    logger.warning(f"Scheduler.schedule error: {ex}")
            elif hasattr(self.scheduler, "add_job"):
                try:
                    self.scheduler.add_job(self.perform_backup_async, "cron", id=self._scheduled_job_id)
                except Exception as ex:
                    logger.warning(f"Scheduler.add_job error: {ex}")

        logger.info(f"Successfully scheduled nightly episodic memory backup with cron '{expr}' (job_id={self._scheduled_job_id})")
        return self._scheduled_job_id

    async def perform_backup_async(self) -> BackupRecord:
        """
        Extract memories from memory source and dump to disk.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"episodic_backup_{now_str}_{uuid.uuid4().hex[:6]}.json"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        entries: List[Dict[str, Any]] = []

        try:
            # 1. Fetch entries from memory source
            if self.memory_source is not None:
                if hasattr(self.memory_source, "get_all"):
                    res = self.memory_source.get_all()
                    if inspect.isawaitable(res):
                        entries = await res
                    else:
                        entries = res
                elif hasattr(self.memory_source, "dump_episodic_memory"):
                    res = self.memory_source.dump_episodic_memory()
                    if inspect.isawaitable(res):
                        entries = await res
                    else:
                        entries = res
                elif callable(self.memory_source):
                    res = self.memory_source()
                    if inspect.isawaitable(res):
                        entries = await res
                    else:
                        entries = res
                elif isinstance(self.memory_source, list):
                    entries = list(self.memory_source)

            # Ensure entries are dicts
            normalized = []
            for item in entries:
                if hasattr(item, "to_dict"):
                    normalized.append(item.to_dict())
                elif isinstance(item, dict):
                    normalized.append(item)
                else:
                    normalized.append({"content": str(item)})

            # 2. Write backup JSON atomically
            temp_path = f"{backup_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "v3",
                    "timestamp": time.time(),
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "entry_count": len(normalized),
                    "entries": normalized,
                }, f, indent=2)

            os.replace(temp_path, backup_path)
            size = os.path.getsize(backup_path)

            record = BackupRecord(
                backup_file=backup_path,
                entries_count=len(normalized),
                status="success",
                size_bytes=size,
            )
            self._backup_history.append(record)
            logger.info(f"Episodic memory backup created successfully: {backup_path} ({len(normalized)} items, {size} bytes)")
            return record

        except Exception as ex:
            logger.error(f"Failed to create episodic memory backup: {ex}")
            rec = BackupRecord(
                backup_file=backup_path,
                entries_count=0,
                status="failed",
                error=str(ex),
            )
            self._backup_history.append(rec)
            return rec

    def perform_backup(self) -> BackupRecord:
        """Synchronous wrapper for backup execution."""
        return asyncio.run(self.perform_backup_async())

    def list_backups(self) -> List[BackupRecord]:
        """Return history of executed backups."""
        return list(self._backup_history)

    def restore_backup(self, backup_file_path: str) -> List[Dict[str, Any]]:
        """Restore memory entries from a backup JSON file."""
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")

        with open(backup_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("entries", [])

    def is_scheduled(self) -> bool:
        """Check if backup job has been scheduled."""
        return self._scheduled_job_id is not None
