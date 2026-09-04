import os
import shutil
import tempfile
import uuid
import logging
import subprocess
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class MCPIsolationManagerV5:
    """
    Manages isolated git worktrees specifically tailored for MCP action tools
    to prevent state bleed.
    """
    def __init__(self, base_repo_path: str) -> None:
        """Initializes the MCPIsolationManagerV5 with a base repo path."""
        self.base_repo_path = base_repo_path
        self.active_worktrees: Dict[str, str] = {}

    def create_isolated_worktree(self, tool_name: str) -> str:
        """
        Creates an isolated git worktree for a specific MCP action tool.

        Args:
            tool_name: The name of the MCP action tool.

        Returns:
            The path to the isolated worktree.
        """
        safe_tool_name = "".join([c if c.isalnum() else "_" for c in tool_name])
        worktree_id = f"{safe_tool_name}_{uuid.uuid4().hex[:8]}"
        worktree_path = os.path.join(tempfile.gettempdir(), f"mcp_worktree_{worktree_id}")

        try:
            # Create the git worktree
            proc = subprocess.run(
                ["git", "worktree", "add", worktree_path, "-b", worktree_id],
                cwd=self.base_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if proc.returncode != 0:
                logger.error(f"Failed to create worktree: {proc.stderr.decode()}")
                raise RuntimeError(f"Git worktree creation failed: {proc.stderr.decode()}")

            self.active_worktrees[worktree_id] = worktree_path
            return worktree_path

        except Exception as e:
            logger.error(f"Error setting up isolation for {tool_name}: {e}")
            raise

    def cleanup_worktree(self, worktree_path: str) -> None:
        """
        Cleans up and removes an isolated worktree.

        Args:
            worktree_path: The path of the worktree to remove.
        """
        try:
            # Find the worktree id
            worktree_id = None
            for w_id, path in self.active_worktrees.items():
                if path == worktree_path:
                    worktree_id = w_id
                    break

            if not worktree_id:
                logger.warning(f"Worktree path {worktree_path} not tracked.")
                return

            # Remove git worktree
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_path],
                cwd=self.base_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Delete branch
            subprocess.run(
                ["git", "branch", "-D", worktree_id],
                cwd=self.base_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if worktree_path in self.active_worktrees.values():
                del self.active_worktrees[worktree_id]

        except Exception as e:
            logger.error(f"Error cleaning up worktree {worktree_path}: {e}")
