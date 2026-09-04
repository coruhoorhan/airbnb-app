import re
import json
import logging
from typing import Dict, Any, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.memory.procedural import ProceduralMemory

class ExperienceSkillCreatorV2:
    """
    Creates reusable Python skills dynamically from past execution experiences.
    Inspired by Hermes Agent trend. Extracts skills from raw logs and outputs
    MCP-compatible JSON-RPC schemas.
    """
    def __init__(self, llm_client: LLMClient, procedural_memory: Optional[ProceduralMemory] = None) -> None:
        """
        Initializes the ExperienceSkillCreatorV2.

        Args:
            llm_client: The LLM client used for code generation.
            procedural_memory: The memory layer used for storing extracted skills.
        """
        self.llm_client = llm_client
        self.procedural_memory = procedural_memory
        self.created_skills: Dict[str, Dict[str, Any]] = {}

    async def generate_skill_from_logs(self, problem_description: str, raw_logs: str) -> Optional[Dict[str, Any]]:
        """
        Analyzes raw execution logs and attempts to generate a Python skill.
        Also generates an MCP-compatible JSON-RPC schema for the skill.

        Args:
            problem_description: A description of the problem solved.
            raw_logs: The raw string of execution logs.

        Returns:
            A dictionary containing the generated code and MCP-compatible schema, or None if generation failed.
        """
        prompt = (
            "Analyze the following raw execution logs of a solved task.\n"
            "Generate a Python function (a 'skill') that encapsulates this logic and is highly reusable.\n"
            "Return the Python code enclosed in ```python\n...\n```.\n"
            "Also return an MCP-compatible JSON-RPC schema (v6 compliant) enclosed in ```json\n...\n```.\n"
            "The JSON schema must have 'name', 'description', and 'inputSchema' (JSON Schema dict) keys.\n\n"
            f"Problem: {problem_description}\n\n"
            f"Raw Logs:\n{raw_logs}"
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.llm_client.chat_completion(messages=messages)
        except Exception as e:
            logging.error(f"Failed to generate skill from logs: {e}")
            return None

        # Extract python code
        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        if not code_match:
            logging.error("No valid Python code found in response.")
            return None
        code = code_match.group(1).strip()

        # Extract json schema
        json_match = re.search(r"```json\n(.*?)```", response, re.DOTALL)
        if not json_match:
            logging.error("No valid JSON schema found in response.")
            return None

        try:
            schema = json.loads(json_match.group(1).strip())
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON schema: {e}")
            return None

        skill_name = schema.get("name", "generated_skill")

        skill_data = {
            "code": code,
            "schema": schema
        }

        self.created_skills[skill_name] = skill_data

        if self.procedural_memory:
            self.procedural_memory.store_procedure(
                name=skill_name,
                procedure=code,
                metadata={
                    "source_problem": problem_description,
                    "type": "hermes_experience_skill_v4",
                    "schema": schema
                }
            )

        logging.info(f"Dynamically generated and stored new skill from logs: {skill_name}")
        return skill_data
