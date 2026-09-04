import json
import logging
from typing import Any, Dict, List

from magda_agent.llm_client import LLMClient


class AssertEvaluator:
    """
    ASSERT Policy Evaluation Framework.

    This class implements a policy-driven evaluation framework to validate
    inputs, such as tool calls, against explicit safety policies.
    """

    def __init__(self, llm: LLMClient) -> None:
        """
        Initialize the AssertEvaluator.

        Args:
            llm (LLMClient): The LLM client used to evaluate policies.
        """
        self.llm = llm

    async def evaluate_input(self, input_data: Dict[str, Any], policies: List[str]) -> Dict[str, Any]:
        """
        Evaluate an input, such as a tool call, against a list of explicit safety policies.

        Args:
            input_data (Dict[str, Any]): The input data to evaluate.
            policies (List[str]): A list of policies to evaluate against.

        Returns:
            Dict[str, Any]: A dictionary containing the evaluation result with
                            keys 'is_compliant' (bool) and 'violations' (List[str]).
        """
        formatted_policies = "\n".join([f"- {policy}" for policy in policies])
        input_json = json.dumps(input_data, indent=2)

        prompt = (
            "Evaluate the following input against the provided safety policies.\n"
            "Determine if the input violates ANY of these policies.\n\n"
            f"Policies:\n{formatted_policies}\n\n"
            f"Input:\n{input_json}\n\n"
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
                is_compliant = bool(evaluation.get("is_compliant", False))
                violations = evaluation.get("violations", [])

                if not is_compliant and violations:
                    logging.warning(f"ASSERT Framework: Input violation detected! Violations: {violations}")

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
