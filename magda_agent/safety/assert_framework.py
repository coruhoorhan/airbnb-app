import json
import logging
from typing import Dict, Any, List

from magda_agent.llm_client import LLMClient

class AssertActionEvaluator:
    """
    ASSERT Policy Evaluation Framework Integration.
    Intercepts final agent actions and evaluates them against predefined safety policies before execution.
    """

    def __init__(self, llm: LLMClient) -> None:
        """
        Initializes the AssertActionEvaluator.

        Args:
            llm: The LLM client to use for evaluation.
        """
        self.llm = llm

    async def evaluate_action(self, action: Dict[str, Any], policies: List[str]) -> Dict[str, Any]:
        """
        Evaluates a single agent action against a set of predefined policies.

        Args:
            action: A dictionary representing the agent action (e.g., tool call).
            policies: A list of policy strings to evaluate against.

        Returns:
            A dictionary containing 'is_compliant' (bool) and 'violations' (List[str]).
        """
        formatted_policies = "\n".join([f"- {policy}" for policy in policies])
        action_json = json.dumps(action, indent=2)

        prompt = (
            "Evaluate the following agent action against the provided safety policies.\n"
            "Determine if the action violates ANY of these policies.\n\n"
            f"Policies:\n{formatted_policies}\n\n"
            f"Agent Action:\n{action_json}\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "is_compliant": true,\n'
            '  "violations": ["Policy description if violated, else empty"]\n'
            "}"
        )

        messages = [{"role": "system", "content": prompt}]
        max_retries = 3

        for attempt in range(max_retries):
            try:
                evaluation_text = await self.llm.chat_completion(messages, temperature=0.1)

                if "```" in evaluation_text:
                    evaluation_text = evaluation_text.split("```")[1]
                    if evaluation_text.startswith("json"):
                        evaluation_text = evaluation_text[4:]

                evaluation = json.loads(evaluation_text.strip())
                is_compliant = evaluation.get("is_compliant", False)
                violations = evaluation.get("violations", [])

                if not is_compliant and violations:
                    logging.warning(f"ASSERT Framework: Action violation detected! Violations: {violations}")

                return {
                    "is_compliant": is_compliant,
                    "violations": violations
                }

            except json.JSONDecodeError as e:
                logging.warning(f"ASSERT Framework JSON decoding error attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    logging.error("ASSERT Framework reached max retries. Failing closed (is_compliant=False).")
                    return {"is_compliant": False, "violations": ["Evaluation failed due to JSON decoding error."]}
            except Exception as e:
                logging.error(f"ASSERT Framework failed: {e}")
                return {"is_compliant": False, "violations": [f"Evaluation failed: {str(e)}"]}

        return {"is_compliant": False, "violations": ["Unknown error"]}
