import logging
from typing import Any, Dict

from magda_agent.agents.sub_agent import SubAgent


class HandoffContext:
    """
    Represents the execution context and partial results transferred during a hand-off.
    """

    def __init__(self, original_task: str, context: str, partial_results: Dict[str, Any]) -> None:
        """
        Initialize the hand-off context.
        """
        self.original_task = original_task
        self.context = context
        self.partial_results = partial_results


class HandoffProtocol:
    """
    Manages the secure transfer of execution context from one sub-agent to another.
    Inspired by OpenAI Agents SDK hand-off trends.
    """

    @staticmethod
    async def execute_handoff(
        source_agent: SubAgent,
        target_agent: SubAgent,
        handoff_context: HandoffContext,
        handoff_reason: str = "Delegating specialized task"
    ) -> str:
        """
        Executes the hand-off, preserving context and invoking the target agent.
        """
        logging.info(f"Initiating hand-off: {handoff_reason}")

        unified_context = (
            f"--- Handoff Context ---\n"
            f"Original Task: {handoff_context.original_task}\n"
            f"Reason for Handoff: {handoff_reason}\n"
            f"Previous Context: {handoff_context.context}\n"
            f"Partial Results:\n"
        )
        for key, val in handoff_context.partial_results.items():
            unified_context += f"  - {key}: {val}\n"

        unified_context += "--- End Handoff Context ---\n"

        return await target_agent.execute(
            task=handoff_context.original_task,
            context=unified_context
        )
