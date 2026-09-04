import logging
import time
from typing import List, Dict, Any, Optional, Callable, Tuple
from collections import Counter

from magda_agent.safety.audit_trail import AuditTrail
from magda_agent.skills.registry import SkillRegistry
from magda_agent.memory.procedural import ProceduralMemory
from magda_agent.llm_client import LLMClient


class SkillConsolidator:
    """
    Background worker / component that analyzes tool execution traces from AuditTrail,
    identifies repeated successful sequences of tool calls, and consolidates them into
    reusable procedural macros for future tasks.
    Inspired by Hermes Agent procedural skill consolidation.
    """

    def __init__(
        self,
        audit_trail: Optional[AuditTrail] = None,
        skill_registry: Optional[SkillRegistry] = None,
        procedural_memory: Optional[ProceduralMemory] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        """
        Initializes the SkillConsolidator.

        Args:
            audit_trail: The AuditTrail instance to query execution traces from.
            skill_registry: The SkillRegistry instance to register consolidated macros.
            procedural_memory: Optional ProceduralMemory instance to persist macro definitions.
            llm_client: Optional LLMClient for advanced macro naming/description synthesis.
        """
        self.audit_trail = audit_trail
        self.skill_registry = skill_registry
        self.procedural_memory = procedural_memory
        self.llm_client = llm_client
        self.consolidated_macros: Dict[str, Dict[str, Any]] = {}

    def extract_successful_traces(
        self,
        logs: Optional[List[Dict[str, Any]]] = None,
        min_duration: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Filters execution logs to extract successful tool invocation traces.

        Args:
            logs: Optional list of log dicts. If None, queries audit_trail.
            min_duration: Minimum duration filter.

        Returns:
            List of log entries representing successful tool calls.
        """
        if logs is None:
            if not self.audit_trail:
                return []
            logs = self.audit_trail.get_all()

        successful = []
        for entry in logs:
            result = entry.get("result")
            # Exclude blocked or error results
            if result == "blocked" or result == "error":
                continue
            if isinstance(result, str) and result.startswith("Error"):
                continue

            if entry.get("duration", 0.0) >= min_duration:
                successful.append(entry)

        return successful

    def detect_frequent_sequences(
        self,
        traces: List[Dict[str, Any]],
        sequence_length: int = 2,
        min_occurrences: int = 2,
        max_time_gap: float = 300.0,
    ) -> List[Tuple[Tuple[str, ...], List[List[Dict[str, Any]]]]]:
        """
        Identifies repeated sequences of tool calls in the traces.

        Args:
            traces: List of successful log entries sorted by timestamp.
            sequence_length: N-gram length for sequence pattern detection (e.g., 2 for pairs).
            min_occurrences: Minimum number of times sequence must occur to trigger consolidation.
            max_time_gap: Maximum seconds allowed between consecutive steps in a sequence.

        Returns:
            List of tuples: (sequence_tuple_of_tool_names, list_of_trace_instances)
        """
        if len(traces) < sequence_length:
            return []

        # Sort traces by timestamp
        sorted_traces = sorted(traces, key=lambda x: x.get("timestamp", 0.0))

        patterns: Dict[Tuple[str, ...], List[List[Dict[str, Any]]]] = {}

        for i in range(len(sorted_traces) - sequence_length + 1):
            sub_trace = sorted_traces[i : i + sequence_length]

            # Check time gap constraint between consecutive items in sub_trace
            valid_gap = True
            for k in range(len(sub_trace) - 1):
                t1 = sub_trace[k].get("timestamp", 0.0)
                t2 = sub_trace[k + 1].get("timestamp", 0.0)
                if (t2 - t1) > max_time_gap:
                    valid_gap = False
                    break

            if not valid_gap:
                continue

            seq_key = tuple(entry["tool_name"] for entry in sub_trace)
            if seq_key not in patterns:
                patterns[seq_key] = []
            patterns[seq_key].append(sub_trace)

        # Filter by min_occurrences
        frequent = [
            (seq, instances)
            for seq, instances in patterns.items()
            if len(instances) >= min_occurrences
        ]

        return frequent

    def build_macro_function(
        self,
        macro_name: str,
        tool_sequence: Tuple[str, ...],
        sample_instances: List[List[Dict[str, Any]]],
    ) -> Callable[..., Dict[str, Any]]:
        """
        Synthesizes a composite macro function that sequentially invokes constituent tools
        from skill_registry.

        Args:
            macro_name: Identifier for the macro skill.
            tool_sequence: Tuple of tool names in execution order.
            sample_instances: Trace instances providing sample arguments.

        Returns:
            A callable function representing the macro skill.
        """
        registry = self.skill_registry

        def macro_function(**kwargs) -> Dict[str, Any]:
            """
            Executes constituent tools sequentially.
            Accepts kwargs prefixed by tool name (e.g. toolA_arg) or step index (e.g. step_0_arg),
            or passes step-specific dict kwargs if provided under 'steps' list.
            """
            results = []
            step_kwargs_list = kwargs.get("steps", [])

            for idx, tool_name in enumerate(tool_sequence):
                step_kwargs = {}
                if idx < len(step_kwargs_list) and isinstance(step_kwargs_list[idx], dict):
                    step_kwargs = step_kwargs_list[idx]
                else:
                    # Extract args prefixed with tool name or step index
                    prefix_tool = f"{tool_name}_"
                    prefix_step = f"step_{idx}_"
                    for k, v in kwargs.items():
                        if k.startswith(prefix_tool):
                            step_kwargs[k[len(prefix_tool):]] = v
                        elif k.startswith(prefix_step):
                            step_kwargs[k[len(prefix_step):]] = v

                if registry and registry.has_skill(tool_name):
                    res = registry.execute_skill(tool_name, **step_kwargs)
                else:
                    res = f"Macro step {idx} ({tool_name}) skipped: skill not found in registry."

                results.append({"step": idx, "tool": tool_name, "kwargs": step_kwargs, "result": res})

            return {
                "macro_name": macro_name,
                "sequence": list(tool_sequence),
                "step_results": results,
                "success": all("error" not in str(r.get("result", "")).lower() for r in results),
            }

        return macro_function

    def consolidate_skills(
        self,
        sequence_length: int = 2,
        min_occurrences: int = 2,
        max_time_gap: float = 300.0,
    ) -> List[str]:
        """
        Executes a consolidation run: queries AuditTrail, detects frequent sequences,
        creates macro functions, and registers them in SkillRegistry and ProceduralMemory.

        Returns:
            List of newly registered macro skill names.
        """
        traces = self.extract_successful_traces()
        frequent_patterns = self.detect_frequent_sequences(
            traces,
            sequence_length=sequence_length,
            min_occurrences=min_occurrences,
            max_time_gap=max_time_gap,
        )

        registered_macros: List[str] = []

        for seq, instances in frequent_patterns:
            macro_name = f"macro_{'_then_'.join(seq)}"
            description = f"Procedural macro consolidating sequence: {' -> '.join(seq)}"

            macro_fn = self.build_macro_function(macro_name, seq, instances)

            if self.skill_registry:
                self.skill_registry.register_skill(
                    name=macro_name,
                    func=macro_fn,
                    description=description,
                )

            macro_info = {
                "name": macro_name,
                "sequence": list(seq),
                "description": description,
                "occurrences": len(instances),
                "created_at": time.time(),
            }
            self.consolidated_macros[macro_name] = macro_info

            if self.procedural_memory:
                code_repr = f"def {macro_name}(**kwargs):\n    # Consolidates sequence: {' -> '.join(seq)}\n    pass"
                self.procedural_memory.store_procedure(
                    name=macro_name,
                    procedure=code_repr,
                    metadata={"sequence": list(seq), "type": "procedural_macro"},
                )

            logging.info(f"Consolidated procedural skill macro: {macro_name}")
            registered_macros.append(macro_name)

        return registered_macros
