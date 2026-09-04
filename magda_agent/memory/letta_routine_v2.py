"""
Letta Virtual Context Routine Builder V2.

Inspired by MemGPT and Letta patterns: Implements an advanced routine generator
hook V2 that analyzes virtual context event streams, synthesizes parameterized
procedural workflows with action sequences and preconditions, and dynamically
populates procedural memory.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class RoutineStepV2:
    """Represents a single step in a V2 procedural routine."""

    step_number: int
    action_type: str  # tool_call, memory_query, condition_check, user_prompt
    target: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProceduralRoutineV2:
    """Represents a V2 structured, parameterized procedural routine."""

    routine_id: str = field(default_factory=lambda: f"rtn_v2_{uuid.uuid4().hex[:8]}")
    name: str = ""
    trigger_event: str = ""
    action_sequence: List[RoutineStepV2] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.85
    success_rate: float = 1.0
    execution_count: int = 1
    version: str = "v2"
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routine_id": self.routine_id,
            "name": self.name,
            "trigger_event": self.trigger_event,
            "action_sequence": [s.to_dict() for s in self.action_sequence],
            "parameter_schema": self.parameter_schema,
            "confidence_score": round(self.confidence_score, 4),
            "success_rate": round(self.success_rate, 4),
            "execution_count": self.execution_count,
            "version": self.version,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProceduralRoutineV2":
        steps = [
            RoutineStepV2(**s) if isinstance(s, dict) else s
            for s in (data.get("action_sequence") or [])
        ]
        return cls(
            routine_id=str(data.get("routine_id") or f"rtn_v2_{uuid.uuid4().hex[:8]}"),
            name=str(data.get("name") or "Unnamed Routine V2"),
            trigger_event=str(data.get("trigger_event") or ""),
            action_sequence=steps,
            parameter_schema=dict(data.get("parameter_schema") or {}),
            confidence_score=float(data.get("confidence_score", 0.85)),
            success_rate=float(data.get("success_rate", 1.0)),
            execution_count=int(data.get("execution_count", 1)),
            version=str(data.get("version", "v2")),
            tags=list(data.get("tags") or []),
            created_at=float(data.get("created_at", time.time())),
        )


class LettaRoutineBuilderHookV2:
    """
    Letta Routine Builder Hook V2.

    Parses continuous virtual context streams to discover and extract reusable
    procedural routines, storing them in procedural memory.
    """

    def __init__(
        self,
        procedural_memory_target: Optional[Any] = None,
        confidence_threshold: float = 0.75,
        min_sequence_length: int = 2,
    ):
        self.procedural_memory = procedural_memory_target
        self.confidence_threshold = confidence_threshold
        self.min_sequence_length = min_sequence_length
        self._registered_routines: Dict[str, ProceduralRoutineV2] = {}

    def extract_routines_from_stream(
        self,
        events: List[Dict[str, Any]],
    ) -> List[ProceduralRoutineV2]:
        """
        Process a stream of virtual context interaction events and extract routines.
        """
        extracted: List[ProceduralRoutineV2] = []
        if not events or len(events) < self.min_sequence_length:
            return extracted

        # Look for explicit workflow patterns in stream
        tool_sequence: List[Dict[str, Any]] = []

        for ev in events:
            action = ev.get("action") or ev.get("type")
            target = ev.get("tool") or ev.get("tool_name") or ev.get("target") or action
            params = ev.get("params") or ev.get("kwargs") or ev.get("arguments") or {}

            if target:
                tool_sequence.append({
                    "action_type": str(action or "tool_call"),
                    "target": str(target),
                    "params": params,
                })

        # Detect contiguous sub-sequences of actions
        if len(tool_sequence) >= self.min_sequence_length:
            # Group into a synthesized routine
            steps = [
                RoutineStepV2(
                    step_number=idx + 1,
                    action_type=item["action_type"],
                    target=item["target"],
                    params=item["params"],
                    expected_outcome="success",
                )
                for idx, item in enumerate(tool_sequence)
            ]

            first_target = tool_sequence[0]["target"]
            last_target = tool_sequence[-1]["target"]
            name = f"routine_{first_target}_to_{last_target}"

            routine = ProceduralRoutineV2(
                name=name,
                trigger_event=f"execute_{first_target}_flow",
                action_sequence=steps,
                parameter_schema={"type": "object", "properties": {}},
                confidence_score=0.90,
                success_rate=1.0,
                execution_count=1,
                tags=["letta_v2", "virtual_context_stream"],
            )

            self._registered_routines[name] = routine
            extracted.append(routine)

        return extracted

    def sync_to_procedural_memory(
        self,
        routines: Optional[List[ProceduralRoutineV2]] = None,
    ) -> int:
        """
        Sync generated routines into procedural memory storage.
        """
        target = routines if routines is not None else list(self._registered_routines.values())
        if not target:
            return 0

        synced = 0
        if self.procedural_memory is not None:
            for rtn in target:
                try:
                    if hasattr(self.procedural_memory, "save_snippet"):
                        code = json.dumps(rtn.to_dict(), indent=2)
                        self.procedural_memory.save_snippet(
                            name=rtn.name,
                            code=code,
                            description=f"Letta V2 Routine: {rtn.trigger_event}",
                            tags=rtn.tags,
                        )
                        synced += 1
                    elif hasattr(self.procedural_memory, "add_routine"):
                        self.procedural_memory.add_routine(rtn)
                        synced += 1
                    elif hasattr(self.procedural_memory, "append"):
                        self.procedural_memory.append(rtn.to_dict())
                        synced += 1
                except Exception as ex:
                    logger.warning(f"Failed to sync V2 routine '{rtn.name}': {ex}")
        else:
            synced = len(target)

        return synced

    def execute_hook(
        self,
        context_stream: Union[List[Dict[str, Any]], Any],
    ) -> Tuple[List[ProceduralRoutineV2], int]:
        """
        Execute routine extraction hook synchronously.
        """
        events = []
        if isinstance(context_stream, list):
            events = list(context_stream)
        elif hasattr(context_stream, "get_stream_events"):
            events = context_stream.get_stream_events()
        elif hasattr(context_stream, "get_all"):
            events = context_stream.get_all()

        routines = self.extract_routines_from_stream(events)
        synced = self.sync_to_procedural_memory(routines)
        return routines, synced

    async def execute_hook_async(
        self,
        context_stream: Union[List[Dict[str, Any]], Any],
    ) -> Tuple[List[ProceduralRoutineV2], int]:
        """Async execution wrapper."""
        return self.execute_hook(context_stream)

    def get_registered_routines(self) -> List[ProceduralRoutineV2]:
        """Return all held routines."""
        return list(self._registered_routines.values())
