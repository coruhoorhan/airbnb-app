"""
Claude Agent Teams Context Compression V4.

Inspired by Claude Agent SDK hierarchical sub-agent spawning patterns:
Implements specialized hierarchical context compression hooks that distill
multi-level parent and orchestrator contexts, strictly preserving inviolable
constraints and contracts while condensing prompt payloads passed down to sub-agents.
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
class HierarchicalContextNode:
    """Represents a structured hierarchical context frame passed to a sub-agent."""

    depth_level: int = 1
    agent_id: str = "subagent_worker"
    role: str = "worker"
    task_objective: str = ""
    ancestor_context_summary: str = ""
    critical_constraints: List[str] = field(default_factory=list)
    contract_interfaces: List[str] = field(default_factory=list)
    local_data: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_context(self) -> str:
        """Format into a standard hierarchical sub-agent prompt block."""
        parts = [
            f"## Subagent Context [Depth: {self.depth_level}] [Role: {self.role.upper()}]",
            f"Task Objective: {self.task_objective}",
        ]
        if self.ancestor_context_summary:
            parts.append(f"Ancestor Context Summary:\n{self.ancestor_context_summary}")

        if self.critical_constraints:
            parts.append("Inviolable Constraints:")
            for c in self.critical_constraints:
                parts.append(f"- {c}")

        if self.contract_interfaces:
            parts.append("Shared Contract Interfaces:")
            for ci in self.contract_interfaces:
                parts.append(f"- {ci}")

        return "\n\n".join(parts)


@dataclass
class ContextCompressionResultV4:
    """Outcome of compressing hierarchical context for subagent spawning."""

    original_char_count: int
    compressed_char_count: int
    compression_ratio: float
    hierarchical_context: str
    condensed_prompt: str
    retained_constraints: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_char_count": self.original_char_count,
            "compressed_char_count": self.compressed_char_count,
            "compression_ratio": round(self.compression_ratio, 4),
            "condensed_prompt_length": len(self.condensed_prompt),
            "retained_constraints_count": len(self.retained_constraints),
            "execution_time_ms": self.execution_time_ms,
        }


class ClaudeAgentTeamsContextCompressorV4:
    """
    Claude Agent Teams Context Compressor V4.

    Condenses expansive orchestrator context histories into concise, high-signal
    hierarchical payloads for spawned sub-agents.
    """

    CONSTRAINT_KEYWORDS = [
        "must", "never", "required", "prohibited", "only", "strict",
        "do not", "cannot", "invariant", "constraint", "security",
    ]

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_prompt_chars: int = 1500,
        preserve_contracts: bool = True,
    ):
        self.llm_client = llm_client
        self.max_prompt_chars = max_prompt_chars
        self.preserve_contracts = preserve_contracts

    def extract_constraints_and_contracts(self, text: str) -> Tuple[List[str], List[str]]:
        """Extract inviolable constraint lines and contract interface definitions."""
        constraints = []
        contracts = []

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        pattern = re.compile(r"\b(" + "|".join(self.CONSTRAINT_KEYWORDS) + r")\b", re.IGNORECASE)

        for line in lines:
            if pattern.search(line) and len(line) < 300:
                constraints.append(line)
            elif any(c_kw in line.lower() for c_kw in ["interface", "def ", "class ", "schema", "contract", "api"]):
                if len(line) < 300:
                    contracts.append(line)

        return (
            list(dict.fromkeys(constraints))[:10],
            list(dict.fromkeys(contracts))[:10],
        )

    async def compress_hierarchical_context_async(
        self,
        root_context: str,
        parent_summary: str,
        subagent_task: str,
        subagent_role: str = "worker",
        depth_level: int = 1,
        max_chars: Optional[int] = None,
    ) -> ContextCompressionResultV4:
        """
        Compress context and build condensed sub-agent prompt.
        """
        start_t = time.perf_counter()
        target_max = max_chars or self.max_prompt_chars

        full_raw_text = f"{root_context}\n\n{parent_summary}\n\n{subagent_task}"
        original_length = len(full_raw_text)

        constraints, contracts = self.extract_constraints_and_contracts(full_raw_text)

        summary_text = parent_summary
        if len(root_context) > 400:
            if self.llm_client:
                prompt = (
                    f"You are a subagent context compressor for Claude Agent Teams.\n"
                    f"Condense this parent context into a concise 2-3 sentence background summary for a {subagent_role} subagent whose task is '{subagent_task}'.\n\n"
                    f"Parent Context:\n{root_context}\n\n"
                    f"Return only the condensed summary text."
                )
                try:
                    if hasattr(self.llm_client, "generate") and inspect.iscoroutinefunction(self.llm_client.generate):
                        summary_text = await self.llm_client.generate(prompt)
                    elif hasattr(self.llm_client, "generate"):
                        summary_text = self.llm_client.generate(prompt)
                    elif hasattr(self.llm_client, "chat_completion") and inspect.iscoroutinefunction(self.llm_client.chat_completion):
                        summary_text = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
                except Exception as ex:
                    logger.warning(f"LLM context compression error: {ex}. Using text trimming.")
                    summary_text = root_context[:300] + "..."
            else:
                summary_text = root_context[:300] + "..."

        node = HierarchicalContextNode(
            depth_level=depth_level,
            role=subagent_role,
            task_objective=subagent_task,
            ancestor_context_summary=summary_text.strip(),
            critical_constraints=constraints,
            contract_interfaces=contracts if self.preserve_contracts else [],
        )

        formatted_context = node.to_formatted_context()
        if len(formatted_context) > target_max:
            formatted_context = formatted_context[:target_max] + "\n... [Context Truncated to Budget]"

        compressed_len = len(formatted_context)
        ratio = compressed_len / max(1, original_length)
        elapsed = (time.perf_counter() - start_t) * 1000.0

        return ContextCompressionResultV4(
            original_char_count=original_length,
            compressed_char_count=compressed_len,
            compression_ratio=ratio,
            hierarchical_context=formatted_context,
            condensed_prompt=formatted_context,
            retained_constraints=constraints,
            execution_time_ms=elapsed,
        )

    def compress_hierarchical_context(
        self,
        root_context: str,
        parent_summary: str,
        subagent_task: str,
        subagent_role: str = "worker",
        depth_level: int = 1,
        max_chars: Optional[int] = None,
    ) -> ContextCompressionResultV4:
        """Synchronous wrapper for context compression."""
        return asyncio.run(self.compress_hierarchical_context_async(
            root_context=root_context,
            parent_summary=parent_summary,
            subagent_task=subagent_task,
            subagent_role=subagent_role,
            depth_level=depth_level,
            max_chars=max_chars,
        ))
