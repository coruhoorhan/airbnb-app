import asyncio
import logging
import os
import shutil
import uuid
from typing import List, Dict, Any, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.isolation.git_worktree_manager import GitWorktreeManager
from magda_agent.memory.virtual_context import VirtualContextManager
from magda_agent.memory.working import WorkingMemory, MemoryEntry
from magda_agent.memory.episodic import EpisodicMemory
from magda_agent.emotions.engine import PADState

class ParallelWorktreeSubagentSpawner:
    """
    ParallelWorktreeSubagentSpawner spawns and coordinates highly parallelized subagents.
    Provides strict file system isolation via V13 Git Worktree Manager and strict
    memory context isolation by instantiating dedicated, thread-safe memory managers
    and partitioning memories with unique user/session IDs for each subagent task execution.
    Inspired by Claude Agent SDK Agent Teams.
    """

    def __init__(
        self,
        llm: LLMClient,
        worktree_manager: Optional[GitWorktreeManager] = None,
        base_dir: str = "/tmp/magda_worktrees_enhanced",
        cleanup_memory_dirs: bool = True
    ) -> None:
        """
        Initializes the ParallelWorktreeSubagentSpawner.

        Args:
            llm: The Language Model client for subagents.
            worktree_manager: Optional GitWorktreeManagerV13 instance.
            base_dir: Directory where isolated git worktrees are managed.
            cleanup_memory_dirs: Whether to clean up individual episodic memory directories on task completion.
        """
        self.llm = llm
        self.worktree_manager = worktree_manager or GitWorktreeManager(base_dir=base_dir)
        self.cleanup_memory_dirs = cleanup_memory_dirs

    async def run_parallel_tasks(self, tasks: List[Dict[str, Any]], base_context: str) -> List[str]:
        """
        Executes multiple tasks concurrently, ensuring absolute file system and memory isolation.

        Args:
            tasks: A list of task specifications (dicts) with 'description' and optional 'system_prompt'.
            base_context: Shared context seed to initialize the isolated memory context.

        Returns:
            A list of execution results corresponding to the input tasks.
        """
        logging.info(f"ParallelWorktreeSubagentSpawner: Executing {len(tasks)} tasks in parallel.")

        async def run_task(task_spec: Dict[str, Any]) -> str:
            agent_id = f"subagent_{uuid.uuid4().hex[:8]}"
            task_description = task_spec.get("description", "Perform execution task.")
            system_prompt = task_spec.get("system_prompt", "You are an isolated Sub-Agent executing a task.")

            # Generate a unique integer user ID to partition memories strictly
            user_id_int = int(uuid.uuid4().hex[:8], 16)

            # Generate a unique persist directory for ChromaDB to achieve physical database-level isolation
            unique_mem_dir = f"/tmp/magda_episodic_{agent_id}"

            # 1. Isolate Memory Context
            # By instantiating a dedicated VirtualContextManager with a private persist_directory,
            # we achieve 100% isolated memory space per execution.
            isolated_vcm = VirtualContextManager(
                llm_client=self.llm,
                persist_directory=unique_mem_dir,
                working_memory=WorkingMemory(limit=10),
                episodic_memory=EpisodicMemory(persist_directory=unique_mem_dir)
            )

            # Seed isolated memory with base context under the unique partitioned ID
            if base_context:
                entry = MemoryEntry(
                    content=base_context,
                    importance=1.0,
                    emotional_state=PADState(0.0, 0.0, 0.0),
                    user_id=user_id_int
                )
                await isolated_vcm.working_memory.add(entry)

            # 2. Isolate File System via Git Worktree
            worktree_path = None
            try:
                # Create a detached worktree asynchronously
                worktree_path = await self.worktree_manager.create_worktree_async()
                logging.info(f"Spawned {agent_id} in isolated worktree: {worktree_path}")
            except Exception as e:
                logging.error(f"Failed to create isolated Git worktree for {agent_id}: {e}")
                # Clean up memory dir on early failure
                if os.path.exists(unique_mem_dir):
                    try:
                        shutil.rmtree(unique_mem_dir)
                    except Exception:
                        pass
                return f"Error: Git worktree creation failed - {e}"

            try:
                # Assemble isolated context from VirtualContextManager using the unique partitioned ID
                context_items = isolated_vcm.working_memory.get_entries(user_id=user_id_int)
                assembled_context = await isolated_vcm.assemble(
                    context_items=context_items,
                    metadata={"user_id": user_id_int}
                )

                # Augment context with worktree details
                augmented_context = (
                    f"{assembled_context}\n\n"
                    f"Isolated Git Worktree Path: {worktree_path}\n\n"
                    f"Assigned Task:\n{task_description}"
                )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": augmented_context}
                ]

                # Store user interaction in episodic memory of the isolated spawner under the unique partitioned ID
                isolated_vcm.episodic_memory.store_event(
                    text=f"Task: {task_description}",
                    metadata={"task_id": agent_id},
                    user_id=user_id_int
                )

                # Execute LLM completion with isolated context
                result = await self.llm.chat_completion(messages)

                # Store completion result in episodic memory
                isolated_vcm.episodic_memory.store_event(
                    text=f"Response: {result}",
                    metadata={"task_id": agent_id},
                    user_id=user_id_int
                )

                return result

            except Exception as e:
                logging.error(f"Execution failed for {agent_id}: {e}")
                return f"Error: Task execution failed - {e}"

            finally:
                # 3. Clean up Git Worktree
                if worktree_path:
                    try:
                        await self.worktree_manager.remove_worktree_async(worktree_path)
                        logging.info(f"Cleaned up Git worktree for {agent_id}")
                    except Exception as cleanup_err:
                        logging.error(f"Cleanup failed for Git worktree {worktree_path}: {cleanup_err}")

                # 4. Clean up Memory Directory
                if self.cleanup_memory_dirs and os.path.exists(unique_mem_dir):
                    try:
                        shutil.rmtree(unique_mem_dir)
                        logging.info(f"Cleaned up memory directory for {agent_id}")
                    except Exception as cleanup_err:
                        logging.error(f"Cleanup failed for memory directory {unique_mem_dir}: {cleanup_err}")

        # Gather parallel executions concurrently
        results = await asyncio.gather(*(run_task(task) for task in tasks))
        return list(results)
