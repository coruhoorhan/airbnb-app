"""
Agent Teams Git Worktree Synchronization V5.

Inspired by Claude Agent SDK patterns: Manages independent Git worktrees for
concurrent Agent Teams, providing automated synchronization back to a central
repository/branch using configurable merge/rebase strategies and conflict avoidance.
"""

import asyncio
import logging
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class GitWorktreeError(Exception):
    """Exception raised for errors during git worktree operations."""
    pass


class GitSyncError(Exception):
    """Exception raised when worktree synchronization fails."""
    pass


class GitSyncStrategy(str, Enum):
    FAST_FORWARD = "fast_forward"
    REBASE = "rebase"
    MERGE_COMMIT = "merge_commit"
    SQUASH = "squash"


@dataclass
class SyncResult:
    """Outcome of synchronizing an agent's worktree back to the central repository branch."""

    agent_id: str
    branch_name: str
    success: bool
    target_branch: str = "main"
    commits_synced: int = 0
    conflict_detected: bool = False
    strategy_used: GitSyncStrategy = GitSyncStrategy.REBASE
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy_used"] = (
            self.strategy_used.value
            if isinstance(self.strategy_used, GitSyncStrategy)
            else str(self.strategy_used)
        )
        return d


class AgentWorktreeIsolationV5:
    """
    Manages creation, execution isolation, and synchronization of Git worktrees
    for individual sub-agents.
    """

    def __init__(
        self,
        base_dir: str = "/tmp/magda_agent_teams_v5",
        repo_dir: Optional[str] = None,
    ) -> None:
        self.base_dir = base_dir
        self.repo_dir = repo_dir or os.getcwd()
        os.makedirs(self.base_dir, exist_ok=True)
        self.active_worktrees: Dict[str, str] = {}
        self.active_branches: Dict[str, str] = {}

    async def _run_git(
        self,
        args: List[str],
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """Execute git command via async subprocess."""
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd or self.repo_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()

    async def create_worktree(
        self,
        agent_id: str,
        branch_name: Optional[str] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """
        Creates an independent Git worktree on a dedicated branch for an agent.
        """
        if agent_id in self.active_worktrees:
            raise ValueError(f"Worktree already active for agent '{agent_id}'")

        branch = branch_name or f"agent/{agent_id}_{uuid.uuid4().hex[:6]}"
        worktree_path = os.path.join(self.base_dir, f"wt_{agent_id}")

        code, out, err = await self._run_git([
            "worktree", "add", "-b", branch, worktree_path, "HEAD"
        ])

        if code != 0:
            logger.error(f"Git worktree creation failed for agent {agent_id}: {err}")
            raise GitWorktreeError(f"Git worktree creation failed: {err}")

        self.active_worktrees[agent_id] = worktree_path
        self.active_branches[agent_id] = branch

        isolated_env = {
            "MAGDA_AGENT_ID": agent_id,
            "MAGDA_WORKTREE_PATH": worktree_path,
            "MAGDA_BRANCH": branch,
            "MAGDA_ISOLATED": "true",
        }

        logger.info(f"Created worktree for agent {agent_id} at {worktree_path} on branch {branch}")
        return worktree_path, isolated_env

    async def commit_changes(
        self,
        agent_id: str,
        message: str = "Agent automated subtask commit",
    ) -> bool:
        """Stage and commit all changes within the agent's worktree."""
        worktree_path = self.active_worktrees.get(agent_id)
        if not worktree_path:
            raise ValueError(f"No active worktree for agent '{agent_id}'")

        # Stage changes
        code_add, _, err_add = await self._run_git(["add", "-A"], cwd=worktree_path)
        if code_add != 0:
            logger.warning(f"Git add failed in {worktree_path}: {err_add}")

        # Check status
        code_status, out_status, _ = await self._run_git(["status", "--porcelain"], cwd=worktree_path)
        if not out_status:
            return False  # Nothing to commit

        code_commit, _, err_commit = await self._run_git(["commit", "-m", message], cwd=worktree_path)
        if code_commit != 0:
            raise GitWorktreeError(f"Git commit failed in worktree {worktree_path}: {err_commit}")

        return True

    async def sync_worktree(
        self,
        agent_id: str,
        target_branch: str = "main",
        strategy: GitSyncStrategy = GitSyncStrategy.REBASE,
    ) -> SyncResult:
        """
        Synchronize agent's branch back to the target branch.
        """
        start_t = time.perf_counter()
        worktree_path = self.active_worktrees.get(agent_id)
        branch = self.active_branches.get(agent_id)

        if not worktree_path or not branch:
            return SyncResult(
                agent_id=agent_id,
                branch_name="",
                success=False,
                target_branch=target_branch,
                error_message=f"Agent '{agent_id}' does not have an active worktree",
                duration_ms=(time.perf_counter() - start_t) * 1000.0,
            )

        # 1. Commit any remaining uncommitted work
        try:
            await self.commit_changes(agent_id, message=f"Pre-sync snapshot for agent {agent_id}")
        except Exception as ex:
            logger.warning(f"Pre-sync commit note: {ex}")

        # 2. Count commits ahead of target
        code_cnt, out_cnt, _ = await self._run_git([
            "rev-list", "--count", f"{target_branch}..{branch}"
        ], cwd=worktree_path)
        commits_synced = int(out_cnt) if (code_cnt == 0 and out_cnt.isdigit()) else 1

        # 3. Synchronize using selected strategy
        if strategy == GitSyncStrategy.REBASE:
            code_sync, out_sync, err_sync = await self._run_git(
                ["rebase", target_branch],
                cwd=worktree_path,
            )
            if code_sync != 0:
                # Abort rebase on conflict
                await self._run_git(["rebase", "--abort"], cwd=worktree_path)
                return SyncResult(
                    agent_id=agent_id,
                    branch_name=branch,
                    success=False,
                    target_branch=target_branch,
                    conflict_detected=True,
                    strategy_used=strategy,
                    error_message=f"Rebase conflict on branch {branch}: {err_sync}",
                    duration_ms=(time.perf_counter() - start_t) * 1000.0,
                )

        elif strategy == GitSyncStrategy.MERGE_COMMIT:
            code_sync, out_sync, err_sync = await self._run_git(
                ["merge", target_branch, "--no-ff", "-m", f"Sync {target_branch} into {branch}"],
                cwd=worktree_path,
            )
            if code_sync != 0:
                await self._run_git(["merge", "--abort"], cwd=worktree_path)
                return SyncResult(
                    agent_id=agent_id,
                    branch_name=branch,
                    success=False,
                    target_branch=target_branch,
                    conflict_detected=True,
                    strategy_used=strategy,
                    error_message=f"Merge conflict on branch {branch}: {err_sync}",
                    duration_ms=(time.perf_counter() - start_t) * 1000.0,
                )

        elif strategy == GitSyncStrategy.FAST_FORWARD:
            code_sync, out_sync, err_sync = await self._run_git(
                ["merge", "--ff-only", target_branch],
                cwd=worktree_path,
            )
            if code_sync != 0:
                return SyncResult(
                    agent_id=agent_id,
                    branch_name=branch,
                    success=False,
                    target_branch=target_branch,
                    conflict_detected=True,
                    strategy_used=strategy,
                    error_message=f"Fast-forward failed on branch {branch}: {err_sync}",
                    duration_ms=(time.perf_counter() - start_t) * 1000.0,
                )

        logger.info(f"Successfully synchronized agent {agent_id} ({branch}) with {target_branch}")
        return SyncResult(
            agent_id=agent_id,
            branch_name=branch,
            success=True,
            target_branch=target_branch,
            commits_synced=commits_synced,
            conflict_detected=False,
            strategy_used=strategy,
            duration_ms=(time.perf_counter() - start_t) * 1000.0,
        )

    async def remove_worktree(self, agent_id: str) -> None:
        """Clean up and remove worktree and branch for an agent."""
        worktree_path = self.active_worktrees.get(agent_id)
        if not worktree_path:
            return

        code, _, err = await self._run_git(["worktree", "remove", "--force", worktree_path])
        if code != 0:
            logger.warning(f"Git worktree remove failed for {agent_id}: {err}. Performing aggressive cleanup.")
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path, ignore_errors=True)

        self.active_worktrees.pop(agent_id, None)
        self.active_branches.pop(agent_id, None)


class AgentTeamManagerV5:
    """
    Coordinates Agent Teams with isolated Git worktrees and automated synchronization.
    """

    def __init__(
        self,
        isolation_manager: Optional[AgentWorktreeIsolationV5] = None,
    ) -> None:
        self.isolation_manager = isolation_manager or AgentWorktreeIsolationV5()
        self.agents: List[str] = []
        self.agent_envs: Dict[str, Dict[str, str]] = {}
        self.sync_history: List[SyncResult] = []

    async def spawn_agent(
        self,
        agent_id: str,
        branch_name: Optional[str] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """Spawn a sub-agent with its isolated Git worktree."""
        if agent_id in self.agents:
            raise ValueError(f"Agent '{agent_id}' is already spawned in this team.")

        worktree_path, isolated_env = await self.isolation_manager.create_worktree(
            agent_id=agent_id,
            branch_name=branch_name,
        )

        self.agents.append(agent_id)
        self.agent_envs[agent_id] = isolated_env
        return worktree_path, isolated_env

    def get_agent_env(self, agent_id: str) -> Optional[Dict[str, str]]:
        """Retrieve isolated environment variables for a sub-agent."""
        return self.agent_envs.get(agent_id)

    async def commit_agent_work(
        self,
        agent_id: str,
        message: str = "Agent automated commit",
    ) -> bool:
        """Commit work in a sub-agent's worktree."""
        return await self.isolation_manager.commit_changes(agent_id, message)

    async def synchronize_agent(
        self,
        agent_id: str,
        target_branch: str = "main",
        strategy: GitSyncStrategy = GitSyncStrategy.REBASE,
    ) -> SyncResult:
        """Synchronize a single sub-agent's worktree back to target branch."""
        res = await self.isolation_manager.sync_worktree(
            agent_id=agent_id,
            target_branch=target_branch,
            strategy=strategy,
        )
        self.sync_history.append(res)
        return res

    async def synchronize_all(
        self,
        target_branch: str = "main",
        strategy: GitSyncStrategy = GitSyncStrategy.REBASE,
    ) -> Dict[str, SyncResult]:
        """Synchronize all active agent worktrees back to target branch."""
        results: Dict[str, SyncResult] = {}
        for agent_id in list(self.agents):
            res = await self.synchronize_agent(
                agent_id=agent_id,
                target_branch=target_branch,
                strategy=strategy,
            )
            results[agent_id] = res
        return results

    async def disband_agent(self, agent_id: str) -> None:
        """Disband an agent and clean up its worktree."""
        if agent_id in self.agents:
            await self.isolation_manager.remove_worktree(agent_id)
            self.agents.remove(agent_id)
            self.agent_envs.pop(agent_id, None)

    async def disband_all(self) -> None:
        """Disband all active agents."""
        for agent_id in list(self.agents):
            await self.disband_agent(agent_id)
