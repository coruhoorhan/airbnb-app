from contextlib import asynccontextmanager
import asyncio
import logging
import os
import shutil
from typing import AsyncGenerator, Callable, Coroutine, Dict, List, Optional, TypeVar, Any

T = TypeVar("T")

logger = logging.getLogger(__name__)

class WorkspaceProvisioner:
    """
    Isolated Workspace Provisioner for Sub-Agents.

    Inspired by Claude Agent SDK Agent Teams.
    Provisions isolated git cloned repositories for sub-agents to avoid
    overlapping git state changes and cross-contamination during multi-agent workflows.
    """

    def __init__(
        self,
        base_dir: str = "/tmp/magda_agent_workspaces",
        source_repo_path: Optional[str] = None
    ) -> None:
        """
        Initializes the Workspace Provisioner.

        Args:
            base_dir: Directory where isolated sub-agent workspaces will be created.
            source_repo_path: Path to the source git repository to clone from.
                              Defaults to current working directory if None.
        """
        self.base_dir = os.path.abspath(base_dir)
        self.source_repo_path = os.path.abspath(source_repo_path or os.getcwd())
        os.makedirs(self.base_dir, exist_ok=True)
        self.active_workspaces: Dict[str, str] = {}

    async def provision_workspace_async(
        self,
        agent_id: str,
        branch_name: Optional[str] = None
    ) -> str:
        """
        Provisions a new isolated workspace repository for a sub-agent by cloning
        the source repository.

        Args:
            agent_id: Unique identifier for the sub-agent.
            branch_name: Optional branch name to checkout/create in the cloned workspace.

        Returns:
            Absolute path to the provisioned isolated workspace directory.
        """
        workspace_path = os.path.join(self.base_dir, f"workspace_{agent_id}")

        # Clean up any pre-existing workspace directory for this agent_id
        if os.path.exists(workspace_path):
            await self.remove_workspace_async(agent_id)

        # Attempt to clone source repo locally
        cmd = ["git", "clone", "--local", self.source_repo_path, workspace_path]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # Fallback to standard git clone if --local fails
                cmd = ["git", "clone", self.source_repo_path, workspace_path]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(
                    f"Git clone failed for workspace {workspace_path}: {stderr.decode()}. "
                    "Falling back to directory copy."
                )
                # Fallback to copytree if git clone is unsupported or fails
                if os.path.exists(self.source_repo_path):
                    shutil.copytree(
                        self.source_repo_path,
                        workspace_path,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                        dirs_exist_ok=True
                    )
                else:
                    os.makedirs(workspace_path, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to execute git clone: {e}. Creating workspace directory.")
            if os.path.exists(self.source_repo_path):
                shutil.copytree(
                    self.source_repo_path,
                    workspace_path,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                    dirs_exist_ok=True
                )
            else:
                os.makedirs(workspace_path, exist_ok=True)

        # Ensure directory exists (e.g. if git process was mocked)
        os.makedirs(workspace_path, exist_ok=True)

        # Checkout branch if requested and workspace is a git repo
        if branch_name and os.path.exists(os.path.join(workspace_path, ".git")):
            checkout_cmd = ["git", "checkout", "-b", branch_name]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *checkout_cmd,
                    cwd=workspace_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            except Exception as e:
                logger.warning(f"Could not checkout branch {branch_name} in workspace {workspace_path}: {e}")

        self.active_workspaces[agent_id] = workspace_path
        logger.info(f"Provisioned isolated workspace for agent '{agent_id}' at {workspace_path}")
        return workspace_path

    async def remove_workspace_async(self, agent_id: str) -> None:
        """
        Removes a provisioned sub-agent workspace and cleans up its directory.

        Args:
            agent_id: Unique identifier for the sub-agent.
        """
        workspace_path = self.active_workspaces.pop(agent_id, None)
        if not workspace_path:
            workspace_path = os.path.join(self.base_dir, f"workspace_{agent_id}")

        if os.path.exists(workspace_path):
            try:
                shutil.rmtree(workspace_path, ignore_errors=True)
                logger.info(f"Cleaned up workspace directory for agent '{agent_id}' at {workspace_path}")
            except Exception as e:
                logger.error(f"Error removing workspace directory {workspace_path}: {e}")

    @asynccontextmanager
    async def isolated_workspace(
        self,
        agent_id: str,
        branch_name: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Async context manager providing an isolated workspace lifecycle.

        Args:
            agent_id: Unique sub-agent identifier.
            branch_name: Optional branch name to checkout/create.

        Yields:
            Absolute path to the provisioned workspace directory.
        """
        workspace_path = await self.provision_workspace_async(agent_id, branch_name=branch_name)
        try:
            yield workspace_path
        finally:
            await self.remove_workspace_async(agent_id)

    async def provision_team_workspaces_async(
        self,
        agent_ids: List[str],
        branch_names: Optional[List[Optional[str]]] = None
    ) -> Dict[str, str]:
        """
        Provisions multiple sub-agent workspaces concurrently for an Agent Team.

        Args:
            agent_ids: List of agent identifiers.
            branch_names: Optional list of branch names corresponding to agent_ids.

        Returns:
            Dictionary mapping agent_id -> workspace_path.
        """
        if not agent_ids:
            return {}

        if branch_names is None:
            branch_names = [None] * len(agent_ids)
        elif len(branch_names) < len(agent_ids):
            branch_names = list(branch_names) + [None] * (len(agent_ids) - len(branch_names))

        tasks = [
            self.provision_workspace_async(agent_id, branch_name)
            for agent_id, branch_name in zip(agent_ids, branch_names)
        ]
        paths = await asyncio.gather(*tasks)

        return dict(zip(agent_ids, paths))

    async def execute_in_workspace_async(
        self,
        agent_id: str,
        task_fn: Callable[[str], Coroutine[Any, Any, T]],
        branch_name: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> T:
        """
        Executes a task inside an isolated sub-agent workspace with timeout protection
        and automatic teardown.

        Args:
            agent_id: Unique sub-agent identifier.
            task_fn: Coroutine function accepting the workspace path as its argument.
            branch_name: Optional branch name.
            timeout: Optional maximum allowed execution time in seconds.

        Returns:
            The return value of task_fn.
        """
        async with self.isolated_workspace(agent_id, branch_name=branch_name) as workspace_path:
            coro = task_fn(workspace_path)
            if timeout is not None:
                return await asyncio.wait_for(coro, timeout=timeout)
            return await coro

    async def cleanup_all_async(self) -> None:
        """
        Cleans up all active workspaces managed by this provisioner.
        """
        agent_ids = list(self.active_workspaces.keys())
        for agent_id in agent_ids:
            await self.remove_workspace_async(agent_id)
        self.active_workspaces.clear()
