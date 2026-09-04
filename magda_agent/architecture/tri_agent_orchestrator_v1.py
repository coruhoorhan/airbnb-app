"""
Tri-Agent Orchestration V1.

This module implements a tri-agent architecture (Planner, Generator, Evaluator)
for task execution using dependency graphs, inspired by the Claude Agent SDK.
"""

import logging
from typing import List, Dict, Any, Optional, Set, Callable, Union

from magda_agent.architecture.dependency_graph import DependencyGraph


class PlannerComponent:
    """
    Planner component responsible for decomposing tasks into dependency graph steps.
    """

    def __init__(self, plan_fn: Optional[Union[Callable[..., Any], Any]] = None) -> None:
        self.plan_fn = plan_fn

    async def create_plan(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Creates a list of plan steps with dependency metadata.

        Args:
            task_description: High-level goal or task to decompose.
            context: Additional contextual information.

        Returns:
            List of plan step dictionaries containing 'id', 'description', and 'dependencies'.
        """
        if self.plan_fn:
            if hasattr(self.plan_fn, "create_plan") and callable(self.plan_fn.create_plan):
                result = self.plan_fn.create_plan(task_description, context)
                if hasattr(result, "__await__"):
                    result = await result
            elif callable(self.plan_fn):
                result = self.plan_fn(task_description, context)
                if hasattr(result, "__await__"):
                    result = await result
            else:
                raise TypeError("plan_fn must be callable or have a create_plan method")
            return result

        # Default single-step fallback plan if no plan_fn provided
        return [
            {
                "id": "step_1",
                "description": task_description,
                "dependencies": []
            }
        ]


class GeneratorComponent:
    """
    Generator component responsible for executing plan steps to produce proposals/results.
    """

    def __init__(self, execute_fn: Optional[Union[Callable[..., Any], Any]] = None) -> None:
        self.execute_fn = execute_fn

    async def execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        feedback: Optional[str] = None
    ) -> Any:
        """
        Executes a single step.

        Args:
            step: Step specification dictionary.
            context: Execution context containing outputs of previous steps.
            feedback: Optional evaluator feedback for retry attempts.

        Returns:
            Output/result of step execution.
        """
        if self.execute_fn:
            if hasattr(self.execute_fn, "execute_step") and callable(self.execute_fn.execute_step):
                result = self.execute_fn.execute_step(step, context, feedback)
                if hasattr(result, "__await__"):
                    result = await result
            elif callable(self.execute_fn):
                result = self.execute_fn(step, context, feedback)
                if hasattr(result, "__await__"):
                    result = await result
            else:
                raise TypeError("execute_fn must be callable or have an execute_step method")
            return result

        return f"Completed step: {step.get('description', step.get('id'))}"


class EvaluatorComponent:
    """
    Evaluator component responsible for reviewing generated step outputs against acceptance criteria.
    """

    def __init__(self, evaluate_fn: Optional[Union[Callable[..., Any], Any]] = None) -> None:
        self.evaluate_fn = evaluate_fn

    async def evaluate_step(
        self,
        step: Dict[str, Any],
        proposal: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates a step proposal.

        Args:
            step: Step specification dictionary.
            proposal: Result produced by GeneratorComponent.
            context: Accumulated execution context.

        Returns:
            Dictionary with 'approved' (bool) and 'feedback' (str).
        """
        if self.evaluate_fn:
            if hasattr(self.evaluate_fn, "evaluate_step") and callable(self.evaluate_fn.evaluate_step):
                result = self.evaluate_fn.evaluate_step(step, proposal, context)
                if hasattr(result, "__await__"):
                    result = await result
            elif callable(self.evaluate_fn):
                result = self.evaluate_fn(step, proposal, context)
                if hasattr(result, "__await__"):
                    result = await result
            else:
                raise TypeError("evaluate_fn must be callable or have an evaluate_step method")
            return result

        # Default evaluation approves proposal
        return {
            "approved": True,
            "feedback": "Step output meets requirements"
        }


class TriAgentOrchestratorV1:
    """
    Manages the orchestration loop between Planner, Generator, and Evaluator components
    resolving step dependencies via DependencyGraph.
    """

    def __init__(
        self,
        planner: Optional[PlannerComponent] = None,
        generator: Optional[GeneratorComponent] = None,
        evaluator: Optional[EvaluatorComponent] = None,
        max_retries: int = 3
    ) -> None:
        self.planner = planner or PlannerComponent()
        self.generator = generator or GeneratorComponent()
        self.evaluator = evaluator or EvaluatorComponent()
        self.max_retries = max_retries

    async def execute_task(
        self,
        task_description: str,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a task by planning, resolving dependencies, generating outputs, and evaluating steps.

        Args:
            task_description: The goal or problem statement.
            initial_context: Initial context data.

        Returns:
            Execution summary dictionary with status, outputs, and completed steps.
        """
        context: Dict[str, Any] = dict(initial_context or {})
        plan_steps = await self.planner.create_plan(task_description, context)

        if not plan_steps:
            return {
                "status": "failed",
                "error": "Planner generated an empty plan",
                "completed_steps": [],
                "step_outputs": {}
            }

        # Validate DAG topology (raises ValueError if cyclic)
        try:
            sorted_steps = DependencyGraph.topological_sort(plan_steps)
        except ValueError as exc:
            logging.error(f"Cycle detected in plan dependencies: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "completed_steps": [],
                "step_outputs": {}
            }

        completed_step_ids: Set[str] = set()
        completed_steps_order: List[str] = []
        step_outputs: Dict[str, Any] = {}

        while len(completed_step_ids) < len(plan_steps):
            executable_steps = DependencyGraph.get_executable_steps(plan_steps, completed_step_ids)
            if not executable_steps:
                logging.error("No executable steps remaining; unresolvable dependencies exist.")
                return {
                    "status": "failed",
                    "error": "Unresolvable step dependencies",
                    "completed_steps": list(completed_steps_order),
                    "step_outputs": step_outputs
                }

            for step in executable_steps:
                step_id = step["id"]
                step_context = {
                    "task_description": task_description,
                    "initial_context": context,
                    "completed_outputs": step_outputs
                }

                approved = False
                feedback: Optional[str] = None
                last_proposal: Any = None

                for attempt in range(1, self.max_retries + 1):
                    logging.info(f"Orchestrator: Executing step '{step_id}' attempt {attempt}/{self.max_retries}")
                    proposal = await self.generator.execute_step(step, step_context, feedback)
                    last_proposal = proposal

                    eval_res = await self.evaluator.evaluate_step(step, proposal, step_context)
                    if not isinstance(eval_res, dict):
                        eval_res = {"approved": False, "feedback": "Evaluation result was not a dict"}

                    if eval_res.get("approved"):
                        approved = True
                        step_outputs[step_id] = proposal
                        completed_step_ids.add(step_id)
                        completed_steps_order.append(step_id)
                        logging.info(f"Step '{step_id}' approved on attempt {attempt}")
                        break
                    else:
                        feedback = eval_res.get("feedback", "No feedback provided")
                        logging.warning(f"Step '{step_id}' rejected on attempt {attempt}: {feedback}")

                if not approved:
                    return {
                        "status": "failed",
                        "error": f"Step '{step_id}' failed evaluation after {self.max_retries} attempts",
                        "failed_step": step_id,
                        "last_feedback": feedback,
                        "last_proposal": last_proposal,
                        "completed_steps": list(completed_steps_order),
                        "step_outputs": step_outputs
                    }

        return {
            "status": "success",
            "task_description": task_description,
            "plan": plan_steps,
            "completed_steps": completed_steps_order,
            "step_outputs": step_outputs
        }
