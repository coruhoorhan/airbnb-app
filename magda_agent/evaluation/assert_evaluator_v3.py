import json
import logging
from typing import Dict, Any, List
from magda_agent.llm_client import LLMClient

logger = logging.getLogger(__name__)

class AssertEvaluatorV3:
    """
    ASSERT Policy-Driven Evaluation Framework V3.
    Evaluates agent outputs against defined policies.
    """
    def __init__(self, llm: LLMClient) -> None:
        """
        Initialize the evaluator with an LLMClient.

        Args:
            llm (LLMClient): The LLM client to use for evaluation.
        """
        self.llm = llm

    async def evaluate(self, output: str, policies: List[str]) -> Dict[str, Any]:
        """
        Evaluates the given output against the provided policies.

        Args:
            output (str): The agent output to evaluate.
            policies (List[str]): A list of policies to evaluate against.

        Returns:
            Dict[str, Any]: A dictionary containing evaluation results, including
                            compliance status, violations (if any), and a score.
        """
        formatted_policies = "\n".join([f"- {p}" for p in policies])
        prompt = (
            "Evaluate the following agent output against the provided policies.\n"
            f"Policies:\n{formatted_policies}\n\n"
            f"Output:\n{output}\n\n"
            "Respond ONLY with a JSON object:\n"
            "{\n"
            '  "is_compliant": true,\n'
            '  "violations": ["List of violations, if any"],\n'
            '  "score": 1.0\n'
            "}"
        )

        messages = [{"role": "system", "content": prompt}]
        try:
            evaluation_text = await self.llm.chat_completion(messages, temperature=0.1)
            if "```" in evaluation_text:
                evaluation_text = evaluation_text.split("```")[1]
                if evaluation_text.startswith("json"):
                    evaluation_text = evaluation_text[4:]

            evaluation = json.loads(evaluation_text.strip())
            return evaluation
        except Exception as e:
            logger.error(f"Failed to evaluate output: {e}")
            return {"is_compliant": False, "violations": ["Evaluation failed"], "score": 0.0}
