import asyncio
import logging
from typing import List, Dict, Any, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.agents.sub_agent import SubAgent
from magda_agent.isolation.git_worktree_manager import GitWorktreeManager
from magda_agent.memory.working import WorkingMemory, MemoryEntry
from magda_agent.emotions.engine import PADState

class SubagentWorktreeSpawnerV8:
    """
    SubagentWorktreeSpawnerV8 handles highly parallel multi-agent tasks,
    providing strict Git worktree isolation AND working memory isolation
    for each subagent to prevent context bleeding.

    Inspired by Claude Agent Teams and Claude Code Git Worktree Isolation trends.
    """
    def __init__(self, llm: LLMClient, base_dir: str = "/tmp/magda_spawner_v8"):
        """
        Initializes the worktree spawner.

        Args:
            llm: The underlying LLM client to use for subagents.
            base_dir: The base directory for git worktrees.
        """
        self.llm = llm
        self.worktree_manager = GitWorktreeManager(base_dir=base_dir)

    async def spawn_parallel(self, tasks: List[Dict[str, Any]], base_context: str) -> List[Dict[str, Any]]:
        """
        Spawns multiple subagents in parallel.
        Each subagent executes in an isolated git worktree and gets an isolated memory context.

        Args:
            tasks: A list of tasks where each task is a dictionary
                   containing 'description' and 'system_prompt'.
            base_context: A shared base context provided to all tasks.

        Returns:
            A list of execution result dictionaries mapping task descriptors to outcomes.
        """
        logging.info(f"SubagentWorktreeSpawnerV8 dispatching {len(tasks)} tasks.")

        async def run_isolated_task(task_spec: Dict[str, Any]) -> Dict[str, Any]:
            """
            Executes a single subagent task in total isolation.

            Args:
                task_spec: Specification for the subtask.

            Returns:
                Dictionary with task status and result.
            """
            task_desc = task_spec.get("description", "")
            sys_prompt = task_spec.get("system_prompt", "You are an isolated agent.")

            try:
                # Use GitWorktreeManager's isolated_environment for physical isolation
                async with self.worktree_manager.isolated_environment() as worktree_path:
                    # Provide isolated memory for cognitive context isolation
                    # Note: Using a lightweight isolated WorkingMemory instead of sharing memory objects
                    # to prevent context bleeding across agents.
                    isolated_memory = WorkingMemory(limit=50)
                    entry = MemoryEntry(content=sys_prompt, importance=1.0, emotional_state=PADState(0.0, 0.0, 0.0))
                    await isolated_memory.add(entry)

                    sub_agent = SubAgent(llm=self.llm, system_prompt=sys_prompt, use_isolation=False)
                    # Inject the isolated memory into the sub_agent instance directly
                    sub_agent.working_memory = isolated_memory

                    # Augment context
                    augmented_context = (
                        f"{base_context}\n\n"
                        f"Isolated Working Directory: {worktree_path}\n"
                    )

                    # We pass the memory object if SubAgent supported it, otherwise we inject context
                    # Current SubAgent interface receives string context
                    result = await sub_agent.execute(task=task_desc, context=augmented_context)

                    return {
                        "task": task_desc,
                        "status": "success",
                        "result": result,
                        "worktree": worktree_path
                    }
            except Exception as e:
                logging.error(f"Isolated subtask failed: {e}")
                return {
                    "task": task_desc,
                    "status": "error",
                    "result": str(e)
                }

        # Execute all tasks concurrently in isolated worktrees
        results = await asyncio.gather(*(run_isolated_task(t) for t in tasks))
        return list(results)
