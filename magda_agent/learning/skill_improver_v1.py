"""
Hermes Agent Experience Skill Improvement V1.

Inspired by Hermes Agent experience learning trends: Implements a dynamic learning
module that extracts, distills, and iteratively refines executable Python skills
from episodic agent interaction logs and execution traces.
"""

import asyncio
import inspect
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class DistilledSkill:
    """Represents a reusable executable skill distilled from agent experience."""

    skill_name: str
    description: str
    code_implementation: str
    version: int = 1
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    derived_from_memory_ids: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    refinement_count: int = 0
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistilledSkill":
        return cls(
            skill_name=str(data.get("skill_name") or "unnamed_distilled_skill"),
            description=str(data.get("description") or ""),
            code_implementation=str(data.get("code_implementation") or ""),
            version=int(data.get("version", 1)),
            parameters_schema=dict(data.get("parameters_schema") or {}),
            derived_from_memory_ids=list(data.get("derived_from_memory_ids") or []),
            success_rate=float(data.get("success_rate", 1.0)),
            refinement_count=int(data.get("refinement_count", 0)),
            created_at=float(data.get("created_at", time.time())),
            tags=list(data.get("tags") or []),
        )


class HermesSkillImproverV1:
    """
    Hermes Skill Improver V1.

    Distills new skills and refines existing skills from episodic memory experiences.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        skill_registry: Optional[Any] = None,
    ):
        self.llm_client = llm_client
        self.skill_registry = skill_registry
        self._skills: Dict[str, DistilledSkill] = {}

    def _extract_code_block(self, text: str) -> str:
        """Extract Python code block from LLM response or markdown."""
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match_generic = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match_generic:
            return match_generic.group(1).strip()
        return text.strip()

    async def distill_skill_from_experience_async(
        self,
        experience_records: List[Dict[str, Any]],
        skill_name_hint: Optional[str] = None,
    ) -> DistilledSkill:
        """
        Distill a new skill from successful episodic interaction records.
        """
        if not experience_records:
            raise ValueError("No experience records provided for skill distillation.")

        memory_ids = [str(r.get("id") or f"mem_{i}") for i, r in enumerate(experience_records)]
        combined_text = "\n".join(
            f"- [{r.get('source', 'log')}] {r.get('content', '')}" for r in experience_records
        )

        name = skill_name_hint or f"skill_{uuid.uuid4().hex[:6]}"
        description = f"Distilled skill from {len(experience_records)} episodic experiences."
        code = ""

        if self.llm_client:
            prompt = (
                f"You are the Hermes Skill Distiller. Convert the following successful task execution experience into a clean, reusable Python function named '{name}'.\n\n"
                f"Experience Logs:\n{combined_text}\n\n"
                f"Return only the Python function code block."
            )
            try:
                if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                    raw = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "generate"):
                    raw = self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                    raw = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                else:
                    raw = ""

                code = self._extract_code_block(raw)
            except Exception as ex:
                logger.warning(f"LLM skill distillation error: {ex}. Using heuristic fallback.")

        if not code:
            code = (
                f"def {name}(**kwargs):\n"
                f"    \"\"\"{description}\"\"\"\n"
                f"    # Auto-synthesized baseline\n"
                f"    return {{'status': 'success', 'input': kwargs}}\n"
            )

        skill = DistilledSkill(
            skill_name=name,
            description=description,
            code_implementation=code,
            version=1,
            derived_from_memory_ids=memory_ids,
            tags=["hermes_distilled", "experience_v1"],
        )

        self.register_distilled_skill(skill)
        return skill

    def distill_skill_from_experience(
        self,
        experience_records: List[Dict[str, Any]],
        skill_name_hint: Optional[str] = None,
    ) -> DistilledSkill:
        """Synchronous wrapper for skill distillation."""
        return asyncio.run(self.distill_skill_from_experience_async(experience_records, skill_name_hint))

    async def refine_existing_skill_async(
        self,
        existing_skill_name: str,
        failure_records: List[Dict[str, Any]],
    ) -> DistilledSkill:
        """
        Refine an existing skill by patching its code to resolve failure modes.
        """
        skill = self.get_skill(existing_skill_name)
        if not skill:
            raise ValueError(f"Skill '{existing_skill_name}' not found for refinement.")

        error_logs = "\n".join(
            f"- Error: {r.get('error', r.get('content', ''))}" for r in failure_records
        )

        new_code = skill.code_implementation
        if self.llm_client:
            prompt = (
                f"You are the Hermes Skill Refiner. Fix and improve the following Python skill function to handle these error cases:\n\n"
                f"Existing Code:\n{skill.code_implementation}\n\n"
                f"Failure Logs:\n{error_logs}\n\n"
                f"Return only the updated Python code block."
            )
            try:
                if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                    raw = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "generate"):
                    raw = self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                    raw = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                else:
                    raw = ""

                extracted = self._extract_code_block(raw)
                if extracted:
                    new_code = extracted
            except Exception as ex:
                logger.warning(f"LLM refinement error: {ex}.")

        # Increment version and track refinement
        skill.version += 1
        skill.refinement_count += 1
        skill.code_implementation = new_code
        skill.derived_from_memory_ids.extend([
            str(r.get("id") or f"fail_{i}") for i, r in enumerate(failure_records)
        ])

        logger.info(f"Refined skill '{skill.skill_name}' to version {skill.version}")
        return skill

    def refine_existing_skill(
        self,
        existing_skill_name: str,
        failure_records: List[Dict[str, Any]],
    ) -> DistilledSkill:
        """Synchronous wrapper for skill refinement."""
        return asyncio.run(self.refine_existing_skill_async(existing_skill_name, failure_records))

    def register_distilled_skill(self, skill: DistilledSkill) -> None:
        """Store distilled skill locally and in attached SkillRegistry."""
        self._skills[skill.skill_name] = skill

        if self.skill_registry:
            if hasattr(self.skill_registry, "register_skill"):
                try:
                    self.skill_registry.register_skill(
                        name=skill.skill_name,
                        description=skill.description,
                        code=skill.code_implementation,
                    )
                except Exception as ex:
                    logger.warning(f"Could not register with SkillRegistry: {ex}")

    def get_skill(self, skill_name: str) -> Optional[DistilledSkill]:
        """Fetch distilled skill by name."""
        return self._skills.get(skill_name)

    def list_skills(self) -> List[DistilledSkill]:
        """List all held distilled skills."""
        return list(self._skills.values())
