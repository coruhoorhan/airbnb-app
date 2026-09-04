from typing import Optional, List, Dict, Any, Callable
from magda_agent.agents.planner_agent import PlannerAgent
from magda_agent.agents.generator_agent import GeneratorAgent
from magda_agent.agents.evaluator_agent import EvaluatorAgent
import logging

class TriadCoordinator:
    """
    Orchestrates the Triad Architecture: Planner, Generator, Evaluator.
    Inspired by Claude Agent SDK.
    """
    def __init__(
        self,
        planner_agent: PlannerAgent,
        generator_agent: GeneratorAgent,
        evaluator_agent: EvaluatorAgent
    ) -> None:
        """
        Initializes the triad coordinator with the required agents.
        """
        self.planner_agent = planner_agent
        self.generator_agent = generator_agent
        self.evaluator_agent = evaluator_agent

    async def coordinate(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        message_builder: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
        pre_generation_hook: Optional[Callable[[], None]] = None,
        policies: Optional[List[str]] = None,
        mental_state: Optional[Any] = None,
        behavior_weights: Optional[Dict[str, float]] = None,
        skill_weights: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Executes the triad flow: Plan -> Execute -> Generate -> Evaluate.
        """
        # 1. Planner Phase
        await self.planner_agent.plan(
            user_input,
            user_id=user_id,
            mental_state=mental_state,
            behavior_weights=behavior_weights,
            skill_weights=skill_weights
        )

        # 2. Execute Plan & Generate Response Phase
        plan_str = await self.generator_agent.execute_plan(user_input, user_id=user_id)

        messages = []
        if message_builder:
            messages = message_builder(plan_str)

        if pre_generation_hook:
            pre_generation_hook()

        response = await self.generator_agent.generate_response(messages)

        # Trigger learning from immediate outcome if possible (Optional, logic usually handled later)
        # 3. Evaluator Phase
        await self.evaluator_agent.evaluate(user_input, response, user_id=user_id, policies=policies)

        return response
