import asyncio
import logging
import os
from typing import List

from magda_agent.llm_client import LLMClient
from magda_agent.architecture.agent_teams_v4 import AgentWorktreeIsolationV4

class GitConflictResolverV2:
    """
    A Git conflict resolver subagent that operates in isolated worktrees
    to automatically handle simple merge conflicts using semantic understanding.
    """

    def __init__(self, llm: LLMClient, isolation_manager: AgentWorktreeIsolationV4):
        """
        Initializes the GitConflictResolverV2.

        Args:
            llm (LLMClient): The language model client.
            isolation_manager (AgentWorktreeIsolationV4): The worktree isolation manager.
        """
        self.llm = llm
        self.isolation_manager = isolation_manager

    async def resolve_conflicts(self, agent_id: str) -> bool:
        """
        Detects conflicts in the agent's worktree and uses LLM to semantically resolve them.

        Args:
            agent_id (str): The identifier of the agent, used to find its isolated worktree.

        Returns:
            bool: True if all conflicts were resolved successfully, False otherwise.
        """
        worktree_path = self.isolation_manager.active_worktrees.get(agent_id)
        if not worktree_path:
            logging.error(f"No active worktree found for agent {agent_id}")
            return False

        try:
            # Detect conflicts
            cmd = ["git", "diff", "--name-only", "--diff-filter=U"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=worktree_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logging.error(f"Failed to check for git conflicts: {stderr.decode().strip()}")
                return False

            conflicted_files = [f for f in stdout.decode().strip().split('\n') if f]

            if not conflicted_files:
                logging.info("No git conflicts found.")
                return True

            for file_path in conflicted_files:
                full_path = os.path.join(worktree_path, file_path)
                if not os.path.exists(full_path):
                    logging.warning(f"Conflicted file not found at {full_path}")
                    continue

                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Very basic check to ensure it has conflict markers
                if "<<<<<<<" not in content or "=======" not in content or ">>>>>>>" not in content:
                    logging.warning(f"File {file_path} marked as conflicted but lacks standard markers.")
                    continue

                # Ask LLM to resolve
                prompt = (
                    f"You are an expert software engineer resolving a git merge conflict.\n"
                    f"Here is the file {file_path} containing git conflict markers (<<<<<<<, =======, >>>>>>>):\n"
                    f"```\n{content}\n```\n"
                    f"Please provide the fully resolved file content. Ensure you resolve the semantic conflict correctly. "
                    f"Return ONLY the resolved code without the conflict markers, inside a single markdown code block."
                )

                response = await self.llm.chat_completion([{"role": "user", "content": prompt}])

                # Extract code from markdown block if present
                clean_response = response.strip()
                if clean_response.startswith("```"):
                    lines = clean_response.splitlines()
                    if len(lines) > 1 and lines[0].startswith("```"):
                        lines = lines[1:]
                    if len(lines) > 0 and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    clean_response = "\n".join(lines).strip()

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(clean_response)

                # Stage the resolved file
                add_cmd = ["git", "add", file_path]
                add_process = await asyncio.create_subprocess_exec(
                    *add_cmd,
                    cwd=worktree_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                add_stdout, add_stderr = await add_process.communicate()
                if add_process.returncode != 0:
                    logging.error(f"Failed to git add resolved file {file_path}: {add_stderr.decode().strip()}")
                    return False
                logging.info(f"Successfully resolved and staged {file_path}")

            return True

        except Exception as e:
            logging.error(f"Error during conflict resolution for agent {agent_id}: {e}")
            return False
