"""
Subagent Spawning and Context Compression V5.

This module provides the SubagentSpawnerV5 class which enables dynamic
subagent spawning for parallel execution with advanced context passing
to optimize token usage, inspired by the Claude Agent SDK context compression trends.
It leverages AgentTeamManagerV4 for strict sandboxing and ClaudeContextCompressorV8
for intelligent context trimming and recursive summarization.
"""

import asyncio
import logging
import uuid
import inspect
from typing import List, Dict, Any, Optional
from magda_agent.architecture.agent_teams_v4 import AgentTeamManagerV4
from magda_agent.memory.compression_v8 import ClaudeContextCompressorV8
from magda_agent.memory.working import MemoryEntry

logger = logging.getLogger(__name__)

class SubagentSpawnerV5:
    """
    Manages the dynamic spawning of subagents with isolated context boundaries and isolated git worktrees.
    Leverages AgentTeamManagerV4 for sandboxing and aggressive cleanup, and ClaudeContextCompressorV8 for context compression.
    """

    def __init__(
        self,
        max_context_tokens: int = 4000,
        team_manager: Optional[AgentTeamManagerV4] = None,
        compressor: Optional[ClaudeContextCompressorV8] = None
    ):
        """
        Initialize the SubagentSpawnerV5.

        Args:
            max_context_tokens: Maximum allowed token threshold for context.
            team_manager: AgentTeamManagerV4 instance for worktree isolation.
            compressor: ClaudeContextCompressorV8 instance for LLM-based context compression.
        """
        self.max_context_tokens = max_context_tokens
        self.team_manager = team_manager or AgentTeamManagerV4()
        self.compressor = compressor or ClaudeContextCompressorV8()

    async def compress_context(self, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compress the context to optimize token usage before passing it to a subagent
        using ClaudeContextCompressorV8.

        Converts the raw context dicts into MemoryEntry objects to use the V8 compressor,
        then unwraps the result back into a format suitable for the subagent.

        Args:
            context: The full context, typically a list of message dicts.

        Returns:
            The compressed context as a list of message dicts.
        """
        if not context:
            return []

        # Convert context list of dicts to MemoryEntry objects
        entries = []
        for msg in context:
            content = msg.get("content", "")
            if isinstance(content, str):
                entries.append(
                    MemoryEntry(
                        content=f"{msg.get('role', 'unknown')}: {content}",
                        importance=0.5,
                        emotional_state="neutral",
                        tags=[],
                        user_id="subagent_user"
                    )
                )

        if not entries:
            return context

        try:
            compressed_entry = await self.compressor.compress_entries(
                entries, token_limit=self.max_context_tokens
            )
            # Reconstruct the compressed context
            # Typically, we provide the compressed context as a single system/user prompt
            # depending on the setup. We'll return it as a system prompt representing the compressed history.
            return [{"role": "system", "content": f"Compressed Context:\n{compressed_entry.content}"}]
        except Exception as e:
            logger.error(f"Failed to compress context: {e}")
            # Fallback to naive logic similar to V4 if compression fails
            if len(context) > 5:
                return [context[0]] + context[-4:]
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

        compressed_context = await self.compress_context(full_context)

        # Append the specific task to the compressed context
        execution_context = compressed_context.copy()
        execution_context.append({
            "role": "user",
            "content": f"Task: {task_description}"
        })

        worktree_path, isolated_env = await self.team_manager.spawn_agent(
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
            await self.team_manager.disband_agent(agent_id)
