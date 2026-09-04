import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from magda_agent.llm_client import LLMClient

logger = logging.getLogger(__name__)


class MagenticOneWorkerV3:
    """
    A specialized worker agent in Microsoft's Magentic-One orchestration pattern (V3).
    Capable of executing subtasks with shared state awareness and returning structured results.
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm: LLMClient,
        specialties: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.llm = llm
        self.specialties = specialties or []

    async def execute_subtask(
        self,
        subtask: str,
        context: List[str],
        shared_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a given subtask with access to context history and shared state.
        Returns a structured dictionary containing worker output and execution status.
        """
        prompt = (
            f"You are {self.name}, a specialized worker.\n"
            f"Role Description: {self.description}\n"
            f"Specialties: {', '.join(self.specialties) if self.specialties else 'General'}\n\n"
            f"Subtask to execute:\n{subtask}\n\n"
            f"Current Shared State:\n{json.dumps(shared_state or {}, default=str, indent=2)}\n\n"
            f"Historical Context:\n{json.dumps(context, default=str, indent=2)}\n\n"
            "Execute the assigned subtask thoroughly and provide your output, findings, and any generated artifacts."
        )

        try:
            response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
            return {
                "worker": self.name,
                "subtask": subtask,
                "result": response.strip(),
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Worker {self.name} encountered an error: {e}")
            return {
                "worker": self.name,
                "subtask": subtask,
                "result": f"Error in worker {self.name}: {e}",
                "status": "error",
            }


class MagenticOneStateMergerV3:
    """
    Integrates intermediate outputs and artifacts from multiple workers into a unified shared state.
    """

    def merge_results(
        self,
        current_state: Dict[str, Any],
        worker_outputs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Integrates worker execution outputs into current_state['history'] and updates current_state['artifacts'].
        """
        if "history" not in current_state:
            current_state["history"] = []
        if "artifacts" not in current_state:
            current_state["artifacts"] = {}
        if "last_outputs" not in current_state:
            current_state["last_outputs"] = []

        current_state["last_outputs"] = worker_outputs

        for output in worker_outputs:
            current_state["history"].append(output)
            worker_name = output.get("worker", "UnknownWorker")
            subtask_key = output.get("subtask", f"subtask_{len(current_state['history'])}")
            result_val = output.get("result", "")

            if worker_name not in current_state["artifacts"]:
                current_state["artifacts"][worker_name] = {}
            current_state["artifacts"][worker_name][subtask_key] = result_val

        return current_state


class MagenticOneOrchestratorV3:
    """
    Orchestrator implementing Magentic-One V3 multi-agent coordination.
    Deconstructs complex tasks, intelligently routes subtasks to specialized workers,
    executes them concurrently via asyncio.gather, and manages unified state across iterations.
    """

    def __init__(
        self,
        llm: LLMClient,
        workers: Optional[List[MagenticOneWorkerV3]] = None,
        max_concurrency: int = 5,
    ) -> None:
        self.llm = llm
        self.max_concurrency = max_concurrency
        self.merger = MagenticOneStateMergerV3()

        if workers:
            self.workers = workers
        else:
            self.workers = [
                MagenticOneWorkerV3(
                    name="Coder",
                    description="Handles code generation, debugging, refactoring, and software implementation",
                    specialties=["coding", "debugging", "python", "software", "implementation", "refactoring"],
                    llm=self.llm,
                ),
                MagenticOneWorkerV3(
                    name="WebSurfer",
                    description="Handles web research, documentation lookup, scraping, and information retrieval",
                    specialties=["web", "search", "scraping", "research", "retrieval", "documentation"],
                    llm=self.llm,
                ),
                MagenticOneWorkerV3(
                    name="FileSurfer",
                    description="Handles file inspection, directory exploration, filesystem operations, and disk artifacts",
                    specialties=["files", "directories", "inspection", "filesystem", "io", "reading", "parsing"],
                    llm=self.llm,
                ),
                MagenticOneWorkerV3(
                    name="Orchestrator",
                    description="General reasoning, task planning, coordination, and synthesis",
                    specialties=["planning", "reasoning", "general", "synthesis", "coordination", "review"],
                    llm=self.llm,
                ),
            ]

    def _find_worker_by_name(self, name: str) -> Optional[MagenticOneWorkerV3]:
        for worker in self.workers:
            if worker.name.lower() == name.lower():
                return worker
        return None

    def _match_worker_by_specialties(self, subtask_text: str) -> MagenticOneWorkerV3:
        subtask_lower = subtask_text.lower()
        best_worker = self.workers[0]
        max_matches = -1

        for worker in self.workers:
            matches = sum(1 for spec in worker.specialties if spec.lower() in subtask_lower)
            if matches > max_matches:
                max_matches = matches
                best_worker = worker

        return best_worker

    def _select_worker_for_subtask(self, subtask_item: Dict[str, Any]) -> MagenticOneWorkerV3:
        worker_hint = subtask_item.get("worker") or subtask_item.get("assigned_worker")
        if worker_hint:
            matched = self._find_worker_by_name(str(worker_hint))
            if matched:
                return matched

        subtask_text = subtask_item.get("subtask") or subtask_item.get("description") or str(subtask_item)
        return self._match_worker_by_specialties(subtask_text)

    async def route_and_execute_parallel(
        self,
        subtasks: List[Dict[str, Any]],
        context: List[str],
        shared_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Intelligently routes subtasks to appropriate workers and executes them concurrently using asyncio.gather.
        """
        if not subtasks:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _run_single(subtask_item: Dict[str, Any]) -> Dict[str, Any]:
            worker = self._select_worker_for_subtask(subtask_item)
            subtask_text = subtask_item.get("subtask") or subtask_item.get("description") or str(subtask_item)
            async with semaphore:
                try:
                    return await worker.execute_subtask(subtask_text, context, shared_state)
                except Exception as e:
                    logger.error(f"Execution error for subtask '{subtask_text}' on worker {worker.name}: {e}")
                    return {
                        "worker": worker.name,
                        "subtask": subtask_text,
                        "result": f"Execution error: {e}",
                        "status": "error",
                    }

        tasks = [_run_single(item) for item in subtasks]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    async def _plan(
        self,
        task: str,
        context: List[str],
        shared_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Prompts LLM to break down the task into parallelizable subtasks with assigned worker hints.
        """
        worker_roster = "\n".join(
            [f"- {w.name}: {w.description} (Specialties: {', '.join(w.specialties)})" for w in self.workers]
        )

        prompt = (
            f"You are the Lead Orchestrator in a Magentic-One Multi-Agent system.\n"
            f"Overall Task: {task}\n\n"
            f"Available Workers:\n{worker_roster}\n\n"
            f"Current Shared State Summary:\n{json.dumps(shared_state.get('artifacts', {}), default=str)}\n\n"
            f"Context:\n{json.dumps(context, default=str)}\n\n"
            "Deconstruct the task into subtasks that can be executed concurrently by specialized workers.\n"
            "Respond ONLY with a JSON list of objects. Each object must have:\n"
            "- \"subtask\": Description of the subtask\n"
            "- \"worker\": Name of the assigned worker (e.g. Coder, WebSurfer, FileSurfer, Orchestrator)\n"
            "Example:\n"
            '[{"subtask": "Search documentation for API", "worker": "WebSurfer"}, {"subtask": "Inspect local config file", "worker": "FileSurfer"}]'
        )

        try:
            response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
            cleaned = response.strip()
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if json_match:
                cleaned = json_match.group(1).strip()

            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0:
                valid_subtasks = []
                for item in parsed:
                    if isinstance(item, dict):
                        valid_subtasks.append(item)
                    elif isinstance(item, str):
                        valid_subtasks.append({"subtask": item, "worker": "Orchestrator"})
                if valid_subtasks:
                    return valid_subtasks
        except Exception as e:
            logger.warning(f"Failed to parse LLM plan as JSON: {e}. Falling back to default plan.")

        return [
            {
                "subtask": f"Execute main task: {task}",
                "worker": self.workers[0].name,
            }
        ]

    async def _review(
        self,
        task: str,
        context: List[str],
        shared_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Reviews progress against the original task and determines if completion criteria are met.
        """
        prompt = (
            f"Task: {task}\n"
            f"Shared State Artifacts:\n{json.dumps(shared_state.get('artifacts', {}), default=str, indent=2)}\n"
            f"Recent Worker Outputs:\n{json.dumps(shared_state.get('last_outputs', []), default=str, indent=2)}\n"
            f"Context:\n{json.dumps(context, default=str)}\n\n"
            "Evaluate if the overall task is fully accomplished.\n"
            "If complete, start your response with 'YES' followed by a comprehensive summary.\n"
            "If incomplete or further steps are required, start your response with 'NO' followed by specific feedback on missing elements."
        )

        try:
            response = await self.llm.chat_completion([{"role": "user", "content": prompt}])
            cleaned = response.strip()
            is_complete = cleaned.upper().startswith("YES")
            return is_complete, cleaned
        except Exception as e:
            logger.error(f"Error during review: {e}")
            return False, f"Review error: {e}"

    async def orchestrate(
        self,
        task: str,
        max_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Main orchestration loop: Planning -> Parallel Routing & Execution -> State Merging -> Review.
        Returns final shared state dictionary with execution history and synthesis.
        """
        shared_state: Dict[str, Any] = {
            "task": task,
            "history": [],
            "artifacts": {},
            "last_outputs": [],
            "status": "in_progress",
            "iterations": 0,
        }
        context: List[str] = []

        for iteration in range(max_iterations):
            shared_state["iterations"] = iteration + 1
            logger.info(f"Starting Magentic-One V3 iteration {iteration + 1}/{max_iterations}")

            # 1. Plan
            subtasks = await self._plan(task, context, shared_state)

            # 2. Route & Execute in Parallel
            worker_outputs = await self.route_and_execute_parallel(subtasks, context, shared_state)

            # 3. State Merging
            shared_state = self.merger.merge_results(shared_state, worker_outputs)

            # 4. Context aggregation
            for out in worker_outputs:
                context.append(f"[{out.get('worker', 'Worker')}]: {out.get('result', '')}")

            # 5. Review
            is_complete, review_feedback = await self._review(task, context, shared_state)
            if is_complete:
                shared_state["status"] = "completed"
                shared_state["summary"] = review_feedback
                logger.info(f"Task completed successfully in iteration {iteration + 1}")
                return shared_state

        shared_state["status"] = "max_iterations_reached"
        shared_state["summary"] = f"Task incomplete after {max_iterations} iterations."
        return shared_state
