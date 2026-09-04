import re
import json
import logging
from typing import Dict, Any, Optional

from magda_agent.llm_client import LLMClient
from magda_agent.memory.procedural import ProceduralMemory

class DynamicSkillCreator:
    """
    Automatically parses the user's conversational requests and extracts repeatable steps
    to create a new, reusable skill in the procedural memory.
    Inspired by Hermes Agent trend.
    """
    def __init__(self, llm_client: LLMClient, procedural_memory: Optional[ProceduralMemory] = None) -> None:
        """
        Initializes the DynamicSkillCreator.

        Args:
            llm_client: The LLM client used for code generation.
            procedural_memory: The memory layer used for storing extracted skills.
        """
        self.llm_client = llm_client
        self.procedural_memory = procedural_memory
        self.created_skills: Dict[str, Dict[str, Any]] = {}

    async def parse_and_create_skill(self, user_request: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Parses a conversational request, extracts repeatable steps, generates a reusable Python function,
        and saves it to the procedural memory.

        Args:
            user_request: The user's conversational request / request text.
            user_id: Optional user ID for memory partitioning.

        Returns:
            A dictionary containing the generated 'code', 'name', and 'description' (or 'schema'),
            or None if the creation failed or no automatable pattern was found.
        """
        prompt = (
            "Analyze the following user conversational request. Extract repeatable steps and generate a highly "
            "reusable Python function (a 'skill') that encapsulates this logic.\n"
            "Return the Python code enclosed in a ```python\n...\n``` code block.\n"
            "Also return a JSON block enclosed in a ```json\n...\n``` code block containing details about the skill.\n"
            "The JSON must contain the keys: 'name' (valid Python function identifier), 'description', and 'parameters' "
            "(an agentskills.io/JSON schema-compatible schema of arguments).\n"
            "If the request does not describe any automatable task, return exactly 'NO_PATTERN'.\n\n"
            f"User Request: {user_request}"
        )

        try:
            response = await self.llm_client.chat_completion(messages=[{"role": "user", "content": prompt}])
            response_text = response.strip()
        except Exception as e:
            logging.error(f"LLM call failed during dynamic skill creation: {e}")
            return None

        if "NO_PATTERN" in response_text or not response_text:
            logging.info("No automatable pattern detected in user request.")
            return None

        # Extract Python code
        code_match = re.search(r"```python\n?(.*?)\n?```", response_text, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            # Fallback if the LLM output is raw code or has def
            if "def " in response_text:
                code = response_text
            else:
                logging.error("Failed to extract Python code block.")
                return None

        # Extract JSON schema
        json_match = re.search(r"```json\n?(.*?)\n?```", response_text, re.DOTALL)
        schema = {}
        if json_match:
            try:
                schema = json.loads(json_match.group(1).strip())
            except Exception as e:
                logging.warning(f"Failed to parse JSON schema block: {e}")

        # Extract function name from code if not in schema
        skill_name = schema.get("name")
        if not skill_name:
            match = re.search(r"def\s+([a-zA-Z0-9_]+)\(", code)
            skill_name = match.group(1) if match else "generated_skill"

        description = schema.get("description", "Dynamically created skill from user request.")

        skill_data = {
            "name": skill_name,
            "code": code,
            "description": description,
            "schema": schema
        }

        self.created_skills[skill_name] = skill_data

        if self.procedural_memory:
            self.procedural_memory.store_procedure(
                name=skill_name,
                procedure=code,
                user_id=user_id,
                metadata={
                    "source_request": user_request,
                    "type": "dynamic_conversational_skill_v1",
                    "schema": schema,
                    "description": description
                }
            )
            logging.info(f"Dynamically generated and stored new conversational skill: {skill_name}")

        return skill_data
