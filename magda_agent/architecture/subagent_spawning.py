"""
Subagent Spawning and Context Compression.

This module provides the SubagentSpawner class which enables dynamic
subagent spawning for parallel execution with compressed context passing
to optimize token usage, inspired by the Claude Agent SDK.
"""

import asyncio
import logging
import uuid
import inspect
from typing import List, Dict, Any, Optional
from magda_agent.architecture.agent_teams_v4 import AgentWorktreeIsolationV4

logger = logging.getLogger(__name__)

class SubagentSpawner:
    """
    Manages the dynamic spawning of subagents with isolated context boundaries and isolated git worktrees.
    """

    def __init__(self, max_context_tokens: int = 4000):
        """
        Initialize the SubagentSpawner.

        Args:
            max_context_tokens: Maximum allowed token threshold for context.
        """
        self.max_context_tokens = max_context_tokens
        self.isolation_manager = AgentWorktreeIsolationV4()

    def compress_context(self, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compress the context to optimize token usage before passing it to a subagent.

        Currently implements a naive strategy: if context has more than 5 messages,
        it keeps the first one (usually system prompt) and the last 4.

        Args:
            context: The full context, typically a list of message dicts.

        Returns:
            The compressed context.
        """
        if not context:
            return []

        # Naive compression logic: keep system prompt and last N messages
        if len(context) > 5:  # naive usage ignores self.max_context_tokens for now
            compressed = [context[0]] + context[-4:]
            return compressed

        return context

    async def spawn_subagent(
        self,
        task_description: str,
        full_context: List[Dict[str, Any]],
        agent_executor: Any,
        agent_id: Optional[str] = None,
        branch_name: Optional[str] = None,
        merge_results: bool = False
    ) -> Any:
        """
        Spawn a subagent to execute a specific task with compressed context in an isolated git worktree.

        Args:
            task_description: The task the subagent should perform.
            full_context: The full conversation or execution context.
            agent_executor: An async callable or object with an `execute` method
                            that runs the subagent.
            agent_id: Optional unique identifier for the subagent.
            branch_name: Optional branch name to use for the subagent's worktree.
            merge_results: Whether to merge the results from the branch into the main branch after execution.

        Returns:
            The result of the subagent's execution.
        """
        if agent_id is None:
            agent_id = str(uuid.uuid4())[:8]

        compressed_context = self.compress_context(full_context)

        # We append the specific task to the compressed context
        execution_context = compressed_context.copy()
        execution_context.append({
            "role": "user",
            "content": f"Task: {task_description}"
        })

        worktree_path, isolated_env = await self.isolation_manager.create_worktree(
            agent_id, branch_name=branch_name
        )

        try:
            if hasattr(agent_executor, "execute") and callable(agent_executor.execute):
                sig = inspect.signature(agent_executor.execute)
                kwargs = {}
                if "worktree_path" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    kwargs["worktree_path"] = worktree_path
                if "isolated_env" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    kwargs["isolated_env"] = isolated_env

                result = await agent_executor.execute(
                    execution_context,
                    **kwargs
                )
            elif callable(agent_executor):
                sig = inspect.signature(agent_executor)
                kwargs = {}
                if "worktree_path" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    kwargs["worktree_path"] = worktree_path
                if "isolated_env" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    kwargs["isolated_env"] = isolated_env

                result = await agent_executor(
                    execution_context,
                    **kwargs
                )
            else:
                raise TypeError("agent_executor must be callable or have an execute method")

            if merge_results and branch_name:
                cmd = ["git", "merge", branch_name, "--no-edit"]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    logger.error(f"Failed to merge branch {branch_name} for agent {agent_id}: {stderr.decode().strip()}")
                    raise RuntimeError(f"Git merge failed: {stderr.decode().strip()}")
                else:
                    logger.info(f"Successfully merged branch {branch_name} for agent {agent_id}")

            return result
        finally:
            await self.isolation_manager.remove_worktree(agent_id)
