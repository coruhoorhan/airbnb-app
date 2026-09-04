import asyncio
import logging
from typing import Any, Callable, Dict, List, Awaitable
from magda_agent.planning.planner import PlanStep, TypedPlan

logger = logging.getLogger(__name__)

class ParallelPlanner:
    """
    A planner designed for orchestrating parallel task execution based on dependencies.
    Inspired by Hermes parallel execution trends.
    """

    def __init__(self, skill_executor_func: Callable[[str, Dict[str, Any]], Awaitable[Any]]) -> None:
        """
        Initializes the ParallelPlanner.

        Args:
            skill_executor_func: An async function that takes a skill name and kwargs and executes the skill.
                                 This allows wiring the planner to any execution backend in the existing architecture.
        """
        self.skill_executor_func = skill_executor_func

    def parse_intent(self, plan: TypedPlan) -> List[PlanStep]:
        """
        Parses a TypedPlan (which captures the user's intent as a DAG) and prepares it for execution.
        Validates dependencies to ensure there are no missing references, outputting a safe list of steps
        ready for gathered concurrent execution.

        Args:
            plan: The TypedPlan object containing steps and their dependencies.

        Returns:
            A validated list of PlanStep objects ready for execution.
        """
        logger.info(f"Parsing parallel intent for plan with {len(plan.steps)} steps.")
        step_ids = {step.id for step in plan.steps}

        for step in plan.steps:
            # We must iterate over a copy of the list since we might modify it
            for dep in list(step.dependencies):
                if dep not in step_ids:
                    logger.warning(f"Step {step.id} depends on unknown step {dep}. Removing dependency.")
                    step.dependencies.remove(dep)

        return plan.steps

    async def execute_plan(self, steps: List[PlanStep]) -> Dict[str, Any]:
        """
        Executes a plan (list of PlanStep objects) concurrently, respecting their dependencies
        via an asyncio gathered execution tree.

        Args:
            steps: A list of PlanStep objects representing the execution plan.

        Returns:
            A dictionary mapping step IDs to their execution results.
        """
        logger.info(f"Executing parallel plan with {len(steps)} steps.")

        results: Dict[str, Any] = {}
        events: Dict[str, asyncio.Event] = {step.id: asyncio.Event() for step in steps}

        async def _execute_step(step: PlanStep) -> None:
            # Wait for all dependencies to finish
            for dep in step.dependencies:
                if dep in events:
                    await events[dep].wait()
                    # If a dependency failed, we also fail this step
                    if isinstance(results.get(dep), Exception):
                        results[step.id] = Exception(f"Dependency {dep} failed.")
                        events[step.id].set()
                        return

            # Execute the current step
            try:
                if step.skill:
                    kwargs = step.skill_kwargs or {}
                    result = await self.skill_executor_func(step.skill, kwargs)
                    results[step.id] = result
                else:
                    results[step.id] = None
            except Exception as e:
                logger.error(f"Error executing step {step.id}: {e}")
                results[step.id] = e
            finally:
                events[step.id].set()

        # Create an asyncio gathered execution tree
        tasks = [asyncio.create_task(_execute_step(step)) for step in steps]

        # Gather all tasks to run them concurrently, handling dependencies via events
        await asyncio.gather(*tasks)

        return results
