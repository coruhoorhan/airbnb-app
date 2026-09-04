import logging
import json
from typing import List, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.architecture.magentic_one_v2 import MagenticOneWorkerV2


class MagenticOneOrchestrationRouterV2:
    """
    Implements a hierarchical orchestration router based on Microsoft's Magentic-One pattern.
    Routes tasks to the most appropriate active sub-agent (worker).
    """

    def __init__(self, llm: LLMClient, workers: List[MagenticOneWorkerV2]) -> None:
        """
        Initializes the MagenticOneOrchestrationRouterV2.

        Args:
            llm (LLMClient): The language model client.
            workers (List[MagenticOneWorkerV2]): The list of available workers.
        """
        self.llm = llm
        self.workers = workers

    async def route(self, task: str, context: List[str]) -> str:
        """
        Routes the task to the most appropriate worker based on the task description
        and the available workers' specialties.

        Args:
            task (str): The task to be executed.
            context (List[str]): Context strings for the current run.

        Returns:
            str: The output of the task execution by the selected worker.
        """
        if not self.workers:
            logging.error("No workers available for routing.")
            return "Error: No workers available."

        worker_descriptions = "\n".join(
            [f"- {worker.name}: {worker.description}" for worker in self.workers]
        )

        prompt = (
            f"Task: {task}\n"
            f"Context: {context}\n"
            f"Available workers:\n{worker_descriptions}\n"
            "Analyze the task and select the best worker to execute it. "
            "Return ONLY the exact name of the selected worker. Do not include any other text."
        )

        try:
            response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
            selected_worker_name = response.strip()

            selected_worker = self._find_worker(selected_worker_name)

            if not selected_worker:
                logging.warning(f"Worker '{selected_worker_name}' not found. Falling back to the first available worker.")
                selected_worker = self.workers[0]

            logging.info(f"Routing task to worker: {selected_worker.name}")
            return await selected_worker.execute_subtask(task, context)

        except Exception as e:
            logging.error(f"Routing failed: {e}")
            return f"Routing error: {e}"

    def _find_worker(self, name: str) -> Optional[MagenticOneWorkerV2]:
        for worker in self.workers:
            if worker.name == name:
                return worker
        return None
