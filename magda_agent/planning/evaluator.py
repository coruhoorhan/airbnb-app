import json
import logging
from typing import List, Dict, Any

from magda_agent.llm_client import LLMClient


class PlannerEvaluator:
    """
    Evaluator for critique of generated plans before execution starts.
    Inspired by Claude Agent SDK.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def evaluate_plan(self, plan: List[Dict[str, Any]], user_input: str) -> Dict[str, Any]:
        """
        Evaluates a generated plan against the user input.

        Args:
            plan (List[Dict[str, Any]]): The generated plan steps.
            user_input (str): The original user request.

        Returns:
            Dict[str, Any]: Evaluation result, e.g. {"approved": True, "feedback": ""}
        """
        logging.info("Evaluating generated plan.")

        system_prompt = (
            "You are the Evaluator Sub-agent of an AI system.\n"
            "Your job is to critique a generated execution plan before it starts.\n"
            "Check for logic errors, missing dependencies, unnecessary complexity, and alignment with the user's goal.\n"
            "Return a JSON object with the following keys:\n"
            "- 'approved': boolean, whether the plan is safe and logical to execute\n"
            "- 'feedback': string, explanation or suggestions for improvement if rejected, or empty if approved.\n"
            "Respond ONLY with valid JSON."
        )

        plan_str = json.dumps(plan, indent=2, ensure_ascii=False)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Input:\n{user_input}\n\nGenerated Plan:\n{plan_str}"}
        ]

        try:
            response_text = await self.llm.chat_completion(messages)

            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            result = json.loads(response_text.strip())

            if "approved" not in result or "feedback" not in result:
                logging.warning("Evaluator response missing required keys, defaulting to approved.")
                return {"approved": True, "feedback": "Fallback: missing keys in evaluation."}

            return result
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode evaluator JSON: {e}")
            return {"approved": True, "feedback": "Fallback: evaluation parsing failed."}
        except Exception as e:
            logging.error(f"Error during plan evaluation: {e}")
            return {"approved": True, "feedback": f"Fallback: evaluation error {e}"}
