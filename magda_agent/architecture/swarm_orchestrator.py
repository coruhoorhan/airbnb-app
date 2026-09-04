import json
import logging
import asyncio
from typing import List, Dict, Any
from magda_agent.llm_client import LLMClient

logger = logging.getLogger(__name__)

class SwarmAgent:
    """
    Implements a recursive, hierarchical subagent that can either handle a task
    directly or break it down and spawn specialized child subagents to execute
    the subtasks.
    """

    def __init__(self, llm: LLMClient, max_depth: int = 2):
        """
        Initializes the SwarmAgent.

        Args:
            llm (LLMClient): The LLM client to use for reasoning and execution.
            max_depth (int): The maximum depth for recursive delegation to prevent infinite loops.
        """
        self.llm = llm
        self.max_depth = max_depth

    async def execute(self, task: str, depth: int = 0) -> str:
        """
        Executes a task. It first evaluates if the task should be broken down.
        If yes (and depth < max_depth), it spawns children. Otherwise, it executes directly.

        Args:
            task (str): The task to execute.
            depth (int): The current depth in the hierarchy.

        Returns:
            str: The result of the task execution.
        """
        logger.info(f"[Depth {depth}] Evaluating task: {task}")

        if depth >= self.max_depth:
            logger.info(f"[Depth {depth}] Max depth reached. Executing directly.")
            return await self._execute_directly(task)

        should_delegate, subtasks = await self._analyze_task(task)

        if should_delegate and subtasks:
            logger.info(f"[Depth {depth}] Delegating into {len(subtasks)} subtasks.")
            results = await self._delegate_to_children(subtasks, depth)
            return await self._synthesize_results(task, results)
        else:
            logger.info(f"[Depth {depth}] Executing directly.")
            return await self._execute_directly(task)

    async def _analyze_task(self, task: str) -> tuple[bool, List[str]]:
        """
        Analyzes the task to determine if it should be broken down into subtasks.
        """
        prompt = (
            f"Analyze the following task: '{task}'\n"
            "If the task is complex and should be broken down into subtasks for parallel or specialized execution, "
            "return a JSON object with 'delegate': true and 'subtasks': [list of subtask strings]. "
            "If it's simple enough to execute directly, return 'delegate': false and 'subtasks': [].\n"
            "Respond ONLY with valid JSON."
        )
        response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
        try:
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:-3].strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response[3:-3].strip()

            parsed = json.loads(clean_response)
            return parsed.get("delegate", False), parsed.get("subtasks", [])
        except Exception as e:
            logger.error(f"Failed to parse task analysis JSON: {e}. Fallback to direct execution.")
            return False, []

    async def _delegate_to_children(self, subtasks: List[str], current_depth: int) -> List[str]:
        """
        Spawns child agents for each subtask and executes them concurrently.
        """
        children = [SwarmAgent(self.llm, self.max_depth) for _ in subtasks]
        tasks = [child.execute(subtask, depth=current_depth + 1) for child, subtask in zip(children, subtasks)]
        results = await asyncio.gather(*tasks)
        return results

    async def _execute_directly(self, task: str) -> str:
        """
        Executes the task directly using the LLM.
        """
        prompt = f"Execute the following task and return the final output:\nTask: {task}"
        response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
        return response

    async def _synthesize_results(self, original_task: str, subtask_results: List[str]) -> str:
        """
        Synthesizes the results of child subtasks into a cohesive final output for the original task.
        """
        combined_results = "\n\n".join(f"Result {i+1}:\n{res}" for i, res in enumerate(subtask_results))
        prompt = (
            f"You delegated the task '{original_task}' into subtasks. Here are the results from the sub-agents:\n\n"
            f"{combined_results}\n\n"
            "Synthesize these results into a single cohesive final answer that fulfills the original task."
        )
        response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
        return response
