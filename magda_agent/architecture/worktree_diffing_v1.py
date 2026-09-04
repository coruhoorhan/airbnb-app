"""
Agent Teams Worktree State Diffing V1.

Inspired by Claude Agent SDK Agent Teams: Implements a robust state diffing
utility that analyzes file state snapshots across sub-agent git worktrees prior to
merges, strictly identifying isolation leaks, overlapping modifications, and
cross-contamination.
"""

import asyncio
import hashlib
import inspect
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class IsolationLeakType(str, Enum):
    OVERLAPPING_MODIFICATION = "overlapping_modification"
    OUT_OF_BOUNDS_WRITE = "out_of_bounds_write"
    UNTRACKED_FILE_SPILL = "untracked_file_spill"
    CROSS_CONTAMINATION = "cross_contamination"
    SHARED_TEMP_FILE = "shared_temp_file"


@dataclass
class IsolationLeak:
    """Represents an identified isolation leak or cross-contamination incident."""

    leak_type: IsolationLeakType
    file_path: str
    involved_agents: List[str]
    description: str
    severity: str = "high"  # critical, high, medium, low
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["leak_type"] = (
            self.leak_type.value
            if isinstance(self.leak_type, IsolationLeakType)
            else str(self.leak_type)
        )
        return d


@dataclass
class WorktreeStateSnapshot:
    """Snapshot of file mutations and additions within an agent's worktree."""

    agent_id: str
    worktree_path: str
    modified_files: Set[str] = field(default_factory=set)
    added_files: Set[str] = field(default_factory=set)
    deleted_files: Set[str] = field(default_factory=set)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "worktree_path": self.worktree_path,
            "modified_files": sorted(list(self.modified_files)),
            "added_files": sorted(list(self.added_files)),
            "deleted_files": sorted(list(self.deleted_files)),
            "file_hashes": self.file_hashes,
            "timestamp": self.timestamp,
        }

    @property
    def all_touched_files(self) -> Set[str]:
        return self.modified_files | self.added_files | self.deleted_files


@dataclass
class WorktreeDiffReport:
    """Comprehensive diff and isolation audit report across active sub-agent worktrees."""

    is_clean: bool
    leaks_detected: List[IsolationLeak] = field(default_factory=list)
    conflicting_files: List[str] = field(default_factory=list)
    agent_file_ownership: Dict[str, List[str]] = field(default_factory=dict)
    summary: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "leaks_detected": [l.to_dict() for l in self.leaks_detected],
            "conflicting_files": self.conflicting_files,
            "agent_file_ownership": self.agent_file_ownership,
            "summary": self.summary,
            "duration_ms": self.duration_ms,
        }


class WorktreeStateDifferV1:
    """
    Worktree State Differ V1.

    Evaluates state diffs between concurrent agent worktrees to identify
    isolation leaks, cross-contamination, and merge collisions prior to state consolidation.
    """

    def __init__(
        self,
        allowed_shared_files: Optional[Set[str]] = None,
        base_worktree_dir: Optional[str] = None,
    ):
        self.allowed_shared_files = set(allowed_shared_files or {
            ".gitignore", "package.json", "requirements.txt", "README.md"
        })
        self.base_worktree_dir = base_worktree_dir

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return ""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def capture_snapshot_from_data(
        self,
        agent_id: str,
        worktree_path: str,
        modified_files: Optional[Set[str]] = None,
        added_files: Optional[Set[str]] = None,
        deleted_files: Optional[Set[str]] = None,
        file_hashes: Optional[Dict[str, str]] = None,
    ) -> WorktreeStateSnapshot:
        """Create a snapshot from explicit file sets (useful for testing or git diff outputs)."""
        return WorktreeStateSnapshot(
            agent_id=agent_id,
            worktree_path=worktree_path,
            modified_files=set(modified_files or []),
            added_files=set(added_files or []),
            deleted_files=set(deleted_files or []),
            file_hashes=dict(file_hashes or {}),
            timestamp=time.time(),
        )

    def capture_filesystem_snapshot(
        self,
        agent_id: str,
        worktree_path: str,
    ) -> WorktreeStateSnapshot:
        """Scan a directory to capture the current state of files and their hashes."""
        added = set()
        hashes = {}

        if os.path.exists(worktree_path):
            for root, _, files in os.walk(worktree_path):
                if ".git" in root:
                    continue
                for fname in files:
                    full_p = os.path.join(root, fname)
                    rel_p = os.path.relpath(full_p, worktree_path)
                    added.add(rel_p)
                    hashes[rel_p] = self._compute_file_hash(full_p)

        return WorktreeStateSnapshot(
            agent_id=agent_id,
            worktree_path=worktree_path,
            added_files=added,
            file_hashes=hashes,
            timestamp=time.time(),
        )

    def evaluate_isolation_leaks(
        self,
        snapshots: Dict[str, WorktreeStateSnapshot],
        allowed_shared: Optional[Set[str]] = None,
    ) -> WorktreeDiffReport:
        """
        Evaluate pair-wise and aggregate snapshots across all active subagent worktrees.
        Detects:
        - Overlapping modifications across agents
        - Out of bounds writes escaping agent worktree root
        - Cross-contamination where Agent A mutates Agent B's domain
        """
        start_t = time.perf_counter()
        shared = set(allowed_shared if allowed_shared is not None else self.allowed_shared_files)
        leaks: List[IsolationLeak] = []
        conflicts: Set[str] = set()
        ownership: Dict[str, List[str]] = {}

        # 1. Map file -> list of agents touching it
        file_to_agents: Dict[str, List[str]] = {}

        for agent_id, snap in snapshots.items():
            ownership[agent_id] = sorted(list(snap.all_touched_files))

            for rel_file in snap.all_touched_files:
                # Check out-of-bounds write
                if rel_file.startswith("..") or "/../" in rel_file or rel_file.startswith("/"):
                    leaks.append(IsolationLeak(
                        leak_type=IsolationLeakType.OUT_OF_BOUNDS_WRITE,
                        file_path=rel_file,
                        involved_agents=[agent_id],
                        description=f"Agent '{agent_id}' attempted out-of-bounds file access: '{rel_file}'",
                        severity="critical",
                    ))
                    continue

                # Check if touching another agent's worktree directly
                for other_id, other_snap in snapshots.items():
                    if other_id != agent_id:
                        other_wt_name = os.path.basename(other_snap.worktree_path)
                        if other_wt_name and (other_wt_name in rel_file or other_id in rel_file):
                            leaks.append(IsolationLeak(
                                leak_type=IsolationLeakType.CROSS_CONTAMINATION,
                                file_path=rel_file,
                                involved_agents=[agent_id, other_id],
                                description=f"Cross-contamination: Agent '{agent_id}' directly touched agent '{other_id}' worktree namespace: '{rel_file}'",
                                severity="critical",
                            ))

                if rel_file not in file_to_agents:
                    file_to_agents[rel_file] = []
                file_to_agents[rel_file].append(agent_id)

        # 2. Check overlapping modifications across agents
        for fpath, agents in file_to_agents.items():
            if len(agents) > 1 and fpath not in shared:
                conflicts.add(fpath)
                leaks.append(IsolationLeak(
                    leak_type=IsolationLeakType.OVERLAPPING_MODIFICATION,
                    file_path=fpath,
                    involved_agents=agents,
                    description=f"Overlapping modification on unshared file '{fpath}' across agents: {agents}",
                    severity="high",
                ))

        is_clean = len(leaks) == 0
        elapsed = (time.perf_counter() - start_t) * 1000.0

        if is_clean:
            summary = f"Clean isolation: {len(snapshots)} sub-agents evaluated with zero leaks."
        else:
            summary = f"Isolation leaks detected: {len(leaks)} violation(s) across {len(conflicts)} conflicting file(s)."

        return WorktreeDiffReport(
            is_clean=is_clean,
            leaks_detected=leaks,
            conflicting_files=sorted(list(conflicts)),
            agent_file_ownership=ownership,
            summary=summary,
            duration_ms=elapsed,
        )

    def evaluate_worktree_paths(
        self,
        worktree_paths: Dict[str, str],
        allowed_shared: Optional[Set[str]] = None,
    ) -> WorktreeDiffReport:
        """Convenience method scanning physical worktree paths and auditing diffs."""
        snapshots = {}
        for agent_id, wt_path in worktree_paths.items():
            snapshots[agent_id] = self.capture_filesystem_snapshot(agent_id, wt_path)
        return self.evaluate_isolation_leaks(snapshots, allowed_shared)

    async def evaluate_worktree_paths_async(
        self,
        worktree_paths: Dict[str, str],
        allowed_shared: Optional[Set[str]] = None,
    ) -> WorktreeDiffReport:
        """Async convenience wrapper for worktree evaluation."""
        return self.evaluate_worktree_paths(worktree_paths, allowed_shared)
