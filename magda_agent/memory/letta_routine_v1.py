"""
Letta Virtual Context Routine Builder V1.

Inspired by MemGPT and Letta patterns: Implements a context manager hook
that automatically analyzes episodic interaction logs, identifies repeated
execution patterns and workflows, synthesizes structured procedural routines,
and populates procedural memory.
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
class ProceduralRoutine:
    """Represents a learned or synthesized multi-step procedural routine."""

    routine_id: str = field(default_factory=lambda: f"rtn_{uuid.uuid4().hex[:8]}")
    name: str = ""
    trigger_pattern: str = ""
    steps: List[str] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    frequency_count: int = 1
    confidence: float = 0.85
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProceduralRoutine":
        return cls(
            routine_id=str(data.get("routine_id") or f"rtn_{uuid.uuid4().hex[:8]}"),
            name=str(data.get("name") or "Unnamed Routine"),
            trigger_pattern=str(data.get("trigger_pattern") or ""),
            steps=list(data.get("steps") or []),
            parameter_schema=dict(data.get("parameter_schema") or {}),
            frequency_count=int(data.get("frequency_count", 1)),
            confidence=float(data.get("confidence", 0.85)),
            tags=list(data.get("tags") or []),
            created_at=float(data.get("created_at", time.time())),
        )


class LettaRoutineBuilderV1:
    """
    Letta Routine Builder V1.

    Scans episodic interaction logs, identifies recurrent multi-step operational patterns,
    and converts them into procedural memory routines.
    """

    DEFAULT_ROUTINE_SEEDS = [
        {
            "name": "git_sync_flow",
            "trigger_pattern": r"(git\s+sync|synchronize\s+worktree|rebase\s+main)",
            "keywords": ["git add", "git commit", "git rebase", "git push"],
            "steps": [
                "Stage modified files (git add -A)",
                "Create commit with automated message",
                "Rebase against main branch (git rebase main)",
                "Verify merge status",
            ],
            "tags": ["git", "vcs", "sync"],
        },
        {
            "name": "test_verification_flow",
            "trigger_pattern": r"(run\s+tests|verify\s+build|smoke\s+test)",
            "keywords": ["unittest", "pytest", "smoke_test", "syntax_check"],
            "steps": [
                "Run syntax smoke check on changed files",
                "Execute unit tests via runner",
                "Parse test report and verify zero failures",
            ],
            "tags": ["testing", "qa", "verification"],
        },
        {
            "name": "mcp_tool_invocation_flow",
            "trigger_pattern": r"(mcp\s+tool|execute\s+tool|call\s+action)",
            "keywords": ["check_rate_limit", "evaluate_taint", "execute_tool", "sanitize_output"],
            "steps": [
                "Check rate limits on target tool",
                "Evaluate taint on input arguments",
                "Execute tool inside sandbox",
                "Sanitize response before memory persistence",
            ],
            "tags": ["mcp", "security", "execution"],
        },
    ]

    def __init__(
        self,
        procedural_memory_target: Optional[Any] = None,
        min_pattern_occurrences: int = 2,
    ):
        self.procedural_memory = procedural_memory_target
        self.min_occurrences = max(1, min_pattern_occurrences)
        self._learned_routines: Dict[str, ProceduralRoutine] = {}

    def extract_routines_from_records(
        self,
        records: List[Dict[str, Any]],
    ) -> List[ProceduralRoutine]:
        """
        Analyze a list of episodic memory records and extract discovered procedural routines.
        """
        extracted_routines: List[ProceduralRoutine] = []
        if not records:
            return extracted_routines

        # Pattern frequency counter
        pattern_matches: Dict[str, List[Dict[str, Any]]] = {}

        for rec in records:
            content = str(rec.get("content") or rec.get("text") or rec.get("action") or "").lower()

            for seed in self.DEFAULT_ROUTINE_SEEDS:
                name = seed["name"]
                trigger_rx = re.compile(seed["trigger_pattern"], re.IGNORECASE)
                has_trigger = bool(trigger_rx.search(content))
                has_keywords = any(
                    kw in content
                    or kw.replace("_", " ") in content
                    or kw.replace(" ", "_") in content
                    for kw in seed["keywords"]
                )
                if has_trigger or has_keywords:
                    if name not in pattern_matches:
                        pattern_matches[name] = []
                    pattern_matches[name].append(rec)

        # Synthesize routines meeting occurrence threshold
        for seed in self.DEFAULT_ROUTINE_SEEDS:
            name = seed["name"]
            matched_records = pattern_matches.get(name, [])
            occurrences = len(matched_records)

            if occurrences >= self.min_occurrences:
                confidence = min(0.99, 0.70 + (0.05 * occurrences))
                routine = ProceduralRoutine(
                    name=name,
                    trigger_pattern=seed["trigger_pattern"],
                    steps=list(seed["steps"]),
                    parameter_schema={"type": "object", "properties": {"target": {"type": "string"}}},
                    frequency_count=occurrences,
                    confidence=confidence,
                    tags=list(seed["tags"]),
                )
                self._learned_routines[name] = routine
                extracted_routines.append(routine)

        # Also extract custom repetitive sequential tool calls if present
        custom_sequences = self._detect_custom_sequences(records)
        for seq in custom_sequences:
            self._learned_routines[seq.name] = seq
            extracted_routines.append(seq)

        return extracted_routines

    def _detect_custom_sequences(self, records: List[Dict[str, Any]]) -> List[ProceduralRoutine]:
        """Detect custom repeated sequences of tool invocations across episodic logs."""
        sequences = []
        tool_invocations = []

        for rec in records:
            if "tool" in rec or "tool_name" in rec:
                tname = rec.get("tool") or rec.get("tool_name")
                tool_invocations.append(tname)

        # Look for 2-step or 3-step repeat patterns
        if len(tool_invocations) >= 4:
            for i in range(len(tool_invocations) - 3):
                pair1 = (tool_invocations[i], tool_invocations[i+1])
                pair2 = (tool_invocations[i+2], tool_invocations[i+3])
                if pair1 == pair2 and pair1[0] and pair1[1]:
                    name = f"routine_{pair1[0]}_{pair1[1]}"
                    if name not in self._learned_routines:
                        routine = ProceduralRoutine(
                            name=name,
                            trigger_pattern=f"execute {pair1[0]} and {pair1[1]}",
                            steps=[f"Call {pair1[0]}", f"Call {pair1[1]}"],
                            frequency_count=2,
                            confidence=0.88,
                            tags=["auto_extracted", "sequence"],
                        )
                        sequences.append(routine)

        return sequences

    def sync_to_procedural_memory(
        self,
        routines: Optional[List[ProceduralRoutine]] = None,
    ) -> int:
        """
        Populate extracted routines into the attached ProceduralMemory store.
        """
        target_routines = routines if routines is not None else list(self._learned_routines.values())
        if not target_routines:
            return 0

        synced_count = 0
        if self.procedural_memory is not None:
            for rtn in target_routines:
                try:
                    if hasattr(self.procedural_memory, "save_snippet"):
                        code_repr = json.dumps(rtn.to_dict(), indent=2)
                        self.procedural_memory.save_snippet(
                            name=rtn.name,
                            code=code_repr,
                            description=f"Procedural routine: {rtn.trigger_pattern}",
                            tags=rtn.tags,
                        )
                        synced_count += 1
                    elif hasattr(self.procedural_memory, "add_routine"):
                        self.procedural_memory.add_routine(rtn)
                        synced_count += 1
                    elif hasattr(self.procedural_memory, "append"):
                        self.procedural_memory.append(rtn.to_dict())
                        synced_count += 1
                except Exception as ex:
                    logger.warning(f"Failed to sync routine '{rtn.name}' to procedural memory: {ex}")
        else:
            synced_count = len(target_routines)

        return synced_count

    def process_episodic_context(
        self,
        episodic_source: Any,
    ) -> Tuple[List[ProceduralRoutine], int]:
        """
        Extract routines from episodic source and sync to procedural memory.
        Returns: (extracted_routines, synced_count)
        """
        records = []
        if isinstance(episodic_source, list):
            records = list(episodic_source)
        elif hasattr(episodic_source, "get_all"):
            records = episodic_source.get_all()
        elif hasattr(episodic_source, "dump_episodic_memory"):
            records = episodic_source.dump_episodic_memory()

        routines = self.extract_routines_from_records(records)
        synced = self.sync_to_procedural_memory(routines)
        return routines, synced

    def get_known_routines(self) -> List[ProceduralRoutine]:
        """Return all routines discovered and held by this builder."""
        return list(self._learned_routines.values())
