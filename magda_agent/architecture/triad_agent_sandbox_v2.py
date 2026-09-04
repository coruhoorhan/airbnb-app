"""
Claude Triad Agent Sandbox V2.

Expands planner-evaluator isolation to allow for intermediate checkpointing
and rollback during failure states.
"""

from typing import Any, Protocol, Dict, Optional


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


class TriadAgentSandboxV2:
    """
    Orchestrates the Planner/Generator/Evaluator triad workflow with checkpointing.

    Allows for intermediate checkpointing and rollback of internal state during
    failure conditions (e.g., if the evaluator rejects the generator's output).
    """

    def __init__(
        self,
        planner: PlannerProtocol,
        generator: GeneratorProtocol,
        evaluator: EvaluatorProtocol
    ) -> None:
        """
        Initialize the Triad Agent Sandbox V2.

        Args:
            planner: An instance conforming to PlannerProtocol.
            generator: An instance conforming to GeneratorProtocol.
            evaluator: An instance conforming to EvaluatorProtocol.
        """
        self.planner = planner
        self.generator = generator
        self.evaluator = evaluator
        self._state: Dict[str, Any] = {}
        self._checkpoint: Optional[Dict[str, Any]] = None

    def set_state(self, key: str, value: Any) -> None:
        """Set a value in the sandbox's internal state."""
        self._state[key] = value

    def get_state(self, key: str) -> Any:
        """Get a value from the sandbox's internal state."""
        return self._state.get(key)

    def checkpoint(self) -> None:
        """Create a checkpoint of the current internal state."""
        self._checkpoint = self._state.copy()

    def rollback(self) -> None:
        """Rollback the internal state to the last checkpoint."""
        if self._checkpoint is not None:
            self._state = self._checkpoint.copy()
        else:
            raise RuntimeError("No checkpoint available to rollback.")

    def execute(self, task_prompt: str) -> str:
        """
        Execute the full triad workflow with checkpointing.

        Args:
            task_prompt: The initial instruction or task description.

        Returns:
            The final generated output if it passes evaluation.

        Raises:
            ValueError: If the Evaluator rejects the output.
        """
        self.checkpoint()
        self.set_state("task_prompt", task_prompt)

        try:
            plan = self.planner.plan(task_prompt)
            self.set_state("plan", plan)

            output = self.generator.generate(plan)
            self.set_state("output", output)

            if not self.evaluator.evaluate(task_prompt, plan, output):
                raise ValueError("Generator output failed Evaluator validation.")

            return output
        except Exception:
            self.rollback()
            raise
