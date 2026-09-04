import logging
from typing import Optional
from magda_agent.llm_client import LLMClient
from magda_agent.agents.sub_agent import SubAgent

class SubagentFactory:
    """
    Factory class that dynamically spawns isolated sub-agents with dedicated virtual contexts
    and runtime boundaries, inspired by the Claude Agent SDK pattern.
    """

    @staticmethod
    def spawn_subagent(
        role: str,
        llm: LLMClient,
        system_prompt: Optional[str] = None,
        use_isolation: bool = True
    ) -> SubAgent:
        """
        Spawns a new SubAgent pre-configured for a specific role (e.g., Planner, Evaluator).

        Args:
            role: The role of the subagent, such as 'Planner' or 'Evaluator'.
            llm: The LLM client for the subagent to use.
            system_prompt: An optional custom system prompt. If None, a role-specific default is used.
            use_isolation: Whether to use git worktree isolation (defaults to True for boundary isolation).

        Returns:
            A configured SubAgent instance.
        """
        logging.info(f"Spawning isolated sub-agent for role: {role}")

        if system_prompt is None:
            if role.lower() == "planner":
                system_prompt = (
                    "You are an isolated Planner Sub-Agent. Your task is to analyze the given context "
                    "and generate a step-by-step execution plan without performing the actions yourself."
                )
            elif role.lower() == "evaluator":
                system_prompt = (
                    "You are an isolated Evaluator Sub-Agent. Your task is to review the given context "
                    "and outputs, critically evaluating their correctness, safety, and alignment with the goal."
                )
            else:
                system_prompt = f"You are an isolated Sub-Agent dedicated to the role of: {role}."

        return SubAgent(
            llm=llm,
            system_prompt=system_prompt,
            use_isolation=use_isolation
        )
