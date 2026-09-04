"""
Claude-inspired Planner/Generator/Evaluator Workflow Sandbox.

This module implements a triad workflow sandbox where a Planner generates a plan,
a Generator executes the plan, and an Evaluator validates the output before it
can be considered final.
"""

from typing import Any, Protocol


class PlannerProtocol(Protocol):
    """Protocol for a planner agent."""
    def plan(self, task_prompt: str) -> str:
        """Generate a plan from the given task prompt."""
        ...


class GeneratorProtocol(Protocol):
    """Protocol for a generator agent."""
    def generate(self, plan: str) -> str:
        """Generate an output based on the given plan."""
        ...


class EvaluatorProtocol(Protocol):
    """Protocol for an evaluator agent."""
    def evaluate(self, task_prompt: str, plan: str, output: str) -> bool:
        """Evaluate if the output satisfies the prompt and plan."""
        ...


class TriadSandbox:
    """
    Orchestrates the Planner/Generator/Evaluator triad workflow.

    Enforces that every Planner-generated task is evaluated by an Evaluator
    subagent before the Generator output is considered final.
    """

    def __init__(
        self,
        planner: PlannerProtocol,
        generator: GeneratorProtocol,
        evaluator: EvaluatorProtocol
    ) -> None:
        """
        Initialize the Triad Sandbox.

        Args:
            planner: An instance conforming to PlannerProtocol.
            generator: An instance conforming to GeneratorProtocol.
            evaluator: An instance conforming to EvaluatorProtocol.
        """
        self.planner = planner
        self.generator = generator
        self.evaluator = evaluator

    def execute(self, task_prompt: str) -> str:
        """
        Execute the full triad workflow.

        Args:
            task_prompt: The initial instruction or task description.

        Returns:
            The final generated output if it passes evaluation.

        Raises:
            ValueError: If the Evaluator rejects the output.
        """
        plan = self.planner.plan(task_prompt)
        output = self.generator.generate(plan)

        if not self.evaluator.evaluate(task_prompt, plan, output):
            raise ValueError("Generator output failed Evaluator validation.")

        return output
