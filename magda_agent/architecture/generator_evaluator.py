"""
Generator/Evaluator Subagent Spawning.

This module provides the PairedSubagentSpawner class which enables dynamic
subagent spawning of paired Generator and Evaluator sub-agents for complex
code synthesis tasks, inspired by the Claude Agent SDK three-agent architecture trend.
"""

import logging
from typing import List, Dict, Any

from magda_agent.architecture.subagent_spawning import SubagentSpawner


class PairedSubagentSpawner(SubagentSpawner):
    """
    Manages the dynamic spawning of paired Generator and Evaluator sub-agents.
    """

    def __init__(self, max_context_tokens: int = 4000) -> None:
        """
        Initialize the PairedSubagentSpawner.

        Args:
            max_context_tokens: Maximum allowed token threshold for context.
        """
        super().__init__(max_context_tokens=max_context_tokens)

    async def spawn_paired_agents(
        self,
        task_description: str,
        full_context: List[Dict[str, Any]],
        generator_executor: Any,
        evaluator_executor: Any,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Spawns paired Generator and Evaluator sub-agents to execute a specific task.
        The Generator proposes a solution, and the Evaluator checks it. If the Evaluator
        rejects it, the feedback is fed back to the Generator for a retry.

        Args:
            task_description: The task the subagents should perform.
            full_context: The full conversation or execution context.
            generator_executor: An async callable or object with an `execute` method
                                that runs the Generator subagent.
            evaluator_executor: An async callable or object with an `execute` method
                                that runs the Evaluator subagent. Expected to return
                                a dict with "approved" (bool) and "feedback" (str).
            max_retries: The maximum number of generation attempts.

        Returns:
            The final result of the generation process as a dict.
        """
        compressed_context = self.compress_context(full_context)

        execution_context = compressed_context.copy()
        execution_context.append({
            "role": "user",
            "content": f"Task: {task_description}"
        })

        for attempt in range(1, max_retries + 1):
            logging.info(f"Spawn Paired Agents: Attempt {attempt} of {max_retries} for task: {task_description}")

            # Run Generator
            if hasattr(generator_executor, "execute") and callable(generator_executor.execute):
                proposal = await generator_executor.execute(execution_context)
            elif callable(generator_executor):
                proposal = await generator_executor(execution_context)
            else:
                raise TypeError("generator_executor must be callable or have an execute method")

            # Prepare Evaluator context
            eval_context = [
                {"role": "system", "content": "You are the Evaluator subagent. Review the proposal against the task."},
                {"role": "user", "content": f"Task: {task_description}\nProposal: {proposal}"}
            ]

            # Run Evaluator
            if hasattr(evaluator_executor, "execute") and callable(evaluator_executor.execute):
                evaluation = await evaluator_executor.execute(eval_context)
            elif callable(evaluator_executor):
                evaluation = await evaluator_executor(eval_context)
            else:
                raise TypeError("evaluator_executor must be callable or have an execute method")

            # Try to handle MagicMock objects for testing context if it is mimicking a dict
            if not isinstance(evaluation, dict) and not (hasattr(evaluation, "__getitem__") and hasattr(evaluation, "get")):
                logging.warning("Evaluator response malformed, defaulting to rejected.")
                evaluation = {"approved": False, "feedback": "Malformed evaluation response"}
            elif isinstance(evaluation, dict) and "approved" not in evaluation:
                logging.warning("Evaluator response malformed, defaulting to rejected.")
                evaluation = {"approved": False, "feedback": "Malformed evaluation response"}
            elif not isinstance(evaluation, dict) and hasattr(evaluation, "get"):
                try:
                    if evaluation.get("approved") is None and evaluation.get("feedback") is None:
                        # Probably a MagicMock not configured properly, but fallback
                        pass
                except Exception:
                    logging.warning("Evaluator response malformed, defaulting to rejected.")
                    evaluation = {"approved": False, "feedback": "Malformed evaluation response"}

            if evaluation.get("approved"):
                logging.info(f"Evaluator approved proposal on attempt {attempt}")
                return {
                    "status": "success",
                    "proposal": proposal,
                    "attempts": attempt,
                    "final_feedback": evaluation.get("feedback", "")
                }
            else:
                feedback = evaluation.get("feedback", "No feedback provided.")
                logging.info(f"Evaluator rejected proposal on attempt {attempt}: {feedback}")

                # Append rejection feedback to Generator context for next attempt
                execution_context.append({"role": "assistant", "content": str(proposal)})
                execution_context.append({"role": "user", "content": f"Feedback: {feedback}. Please revise."})

        logging.error(f"Paired agents failed to reach approval after {max_retries} attempts.")
        return {
            "status": "failed",
            "attempts": max_retries,
            "last_feedback": evaluation.get("feedback", "Max retries reached") if 'evaluation' in locals() else ""
        }
