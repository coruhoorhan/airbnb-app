import ast
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TrajectoryStep:
    action: str
    result: str

class DynamicSkillGenerator:
    """
    Dynamically generates Python skill code based on observed successful multi-step executions.
    Inspired by Hermes Agent trend.
    """

    def __init__(self, llm_client: Any = None):
        """
        Initializes the DynamicSkillGenerator.

        Args:
            llm_client: An instance of an LLM client to generate code.
        """
        self.llm_client = llm_client

    def is_valid_python(self, code: str) -> bool:
        """
        Validates if the provided string is valid Python code using ast.parse.

        Args:
            code: The Python code string to validate.

        Returns:
            True if the code is valid Python syntax, False otherwise.
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.error(f"Syntax error in generated skill code: {e}")
            return False

    def extract_code(self, llm_response: str) -> str:
        """
        Extracts code block from LLM response.

        Args:
            llm_response: The response string from LLM.

        Returns:
            The extracted code string.
        """
        if "```python" in llm_response:
            code = llm_response.split("```python")[1].split("```")[0].strip()
            return code
        elif "```" in llm_response:
            code = llm_response.split("```")[1].split("```")[0].strip()
            return code
        return llm_response.strip()

    def generate_skill_from_logs(self, logs: List[TrajectoryStep]) -> Optional[str]:
        """
        Parses multi-step success logs and generates valid Python skill code.

        Args:
            logs: A list of TrajectoryStep objects representing the successful execution logs.

        Returns:
            A string containing the valid Python code for the new skill, or None if generation fails.
        """
        if not logs:
            logger.warning("Empty logs provided for skill generation.")
            return None

        prompt = "Create a Python skill function based on the following successful execution steps:\n"
        for i, step in enumerate(logs):
            prompt += f"Step {i+1}: Action: {step.action}, Result: {step.result}\n"

        prompt += "\nOutput only valid Python code containing the function definition."

        if not self.llm_client:
            logger.error("LLM client is not initialized.")
            return None

        # Call the LLM to generate code (mocked in tests)
        llm_response = self.llm_client.generate(prompt)

        code = self.extract_code(llm_response)

        if self.is_valid_python(code):
            return code
        else:
            logger.error("Generated code failed validation.")
            return None

    def load_skill_to_registry(self, code: str, skill_name: str, registry: Any) -> bool:
        """
        Dynamically executes the skill code and registers the function into the registry.

        Args:
            code: The valid Python code of the skill.
            skill_name: The name of the function to register.
            registry: The SkillRegistry instance.

        Returns:
            True if the skill was successfully registered, False otherwise.
        """
        try:
            # Create a restricted execution namespace
            namespace = {}
            exec(code, namespace)

            # Extract the function
            func = namespace.get(skill_name)
            if not func or not callable(func):
                logger.error(f"Function {skill_name} not found in the generated code.")
                return False

            # Use the docstring as the description, or a default one
            description = func.__doc__ if func.__doc__ else f"Dynamically generated skill: {skill_name}"

            # Register to the provided registry
            registry.register_skill(name=skill_name, func=func, description=description)
            logger.info(f"Successfully registered dynamic skill: {skill_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load dynamically generated skill {skill_name}: {e}")
            return False
