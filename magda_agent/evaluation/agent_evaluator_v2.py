import json
import logging
from typing import Dict, Any, List, Optional
from magda_agent.llm_client import LLMClient
from magda_agent.agents.sub_agent import SubAgent

class AgentEvaluatorV2:
    """
    Agent Teams Evaluator V2.
    Evaluates the output of a specific generator agent against a dynamic rubric.
    Inspired by Claude Agent SDK Agent Teams Evaluator pattern.
    """
    def __init__(self, llm: LLMClient) -> None:
        """
        Initializes the AgentEvaluatorV2.

        Args:
            llm: The LLM client for cognitive evaluation.
        """
        self.llm = llm
        self.evaluator_agent = SubAgent(
            llm=llm,
            system_prompt="You are an isolated Evaluator Agent responsible for strictly evaluating the output of generator agents against a dynamic rubric.",
            use_isolation=False
        )

    async def evaluate_generator_output(
        self,
        task_description: str,
        generator_output: str,
        rubric: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Evaluates the generator output against the provided rubric.

        Args:
            task_description (str): The description of the task assigned to the generator.
            generator_output (str): The output produced by the generator agent.
            rubric (Dict[str, str]): A mapping of criteria names to their descriptions.

        Returns:
            Dict[str, Any]: Evaluation result containing scores per criteria, overall approved status, and feedback.
        """
        logging.info("Starting AgentEvaluatorV2 generator output review...")

        rubric_str = "\n".join([f"- {criterion}: {description}" for criterion, description in rubric.items()])

        task = (
            "You are an Evaluator Agent. Your task is to evaluate the output of a generator agent against the provided rubric.\n\n"
            f"Original Task Description: {task_description}\n\n"
            f"Rubric:\n{rubric_str}\n\n"
            "Evaluate the generator output for each criterion in the rubric. Score each criterion from 1 to 10.\n"
            "Determine if the output is approved overall (e.g. average score >= 7 and no critical failures).\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "scores": {"criterion_1": 8, "criterion_2": 6},\n'
            '  "approved": true,\n'
            '  "feedback": "Detailed reasoning for the evaluation"\n'
            "}"
        )

        context = (
            f"Generator Output:\n{generator_output}"
        )

        max_retries = 3

        for attempt in range(max_retries):
            try:
                evaluation_text = await self.evaluator_agent.execute(task=task, context=context, temperature=0.1)

                # Remove any markdown formatting (e.g. ```json)
                if "```" in evaluation_text:
                    evaluation_text = evaluation_text.split("```")[1]
                    if evaluation_text.startswith("json"):
                        evaluation_text = evaluation_text[4:]

                evaluation = json.loads(evaluation_text.strip())
                return evaluation
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decoding error in evaluator attempt {attempt + 1}/{max_retries}: {e}. Retrying...")
                if attempt == max_retries - 1:
                    logging.error("Max retries reached for evaluate_generator_output JSON parsing.")
                    return {"scores": {}, "approved": False, "feedback": f"Failed to parse LLM evaluation: {e}"}
            except Exception as e:
                logging.error(f"Failed to evaluate generator output: {e}")
                return {"scores": {}, "approved": False, "feedback": f"Error during evaluation: {e}"}
