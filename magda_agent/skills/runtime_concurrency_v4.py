"""
OpenAI SDK Runtime Function Tool Concurrency V1 (V4 Engine).

Inspired by OpenAI Agents SDK parallel tool execution standards: Implements a
high-throughput runtime concurrency guardrail that executes independent function
tool calls simultaneously, preserving call order, enforcing timeout boundaries,
and isolating execution faults.
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
class FunctionToolCallSpec:
    """Specification of an individual function tool call in a concurrent batch."""

    function_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    timeout_seconds: float = 30.0
    tool_func: Optional[Callable[..., Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("tool_func", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FunctionToolCallSpec":
        fn_name = str(data.get("function_name") or data.get("name") or data.get("tool_name") or "")
        return cls(
            function_name=fn_name,
            arguments=dict(data.get("arguments") or data.get("args") or {}),
            call_id=str(data.get("call_id") or f"call_{uuid.uuid4().hex[:8]}"),
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            tool_func=data.get("tool_func"),
        )


@dataclass
class FunctionToolCallResult:
    """Outcome of an individual function tool execution."""

    call_id: str
    function_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    timed_out: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "function_name": self.function_name,
            "success": self.success,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
        }


class OpenAIRuntimeFunctionConcurrencyV4:
    """
    OpenAI SDK Runtime Function Concurrency Engine V4.

    Manages concurrent parallel execution of tool requests.
    """

    def __init__(
        self,
        max_concurrency: int = 16,
        default_timeout_seconds: float = 30.0,
    ):
        self.max_concurrency = max(1, max_concurrency)
        self.default_timeout = default_timeout_seconds
        self._registered_functions: Dict[str, Callable[..., Any]] = {}
        self._total_batches = 0
        self._total_tool_executions = 0

    def register_function(self, name: str, func: Callable[..., Any]) -> None:
        """Register a function callable with the engine."""
        self._registered_functions[name] = func
        logger.info(f"Registered runtime function '{name}'")

    async def _execute_single_tool(
        self,
        spec: FunctionToolCallSpec,
        semaphore: asyncio.Semaphore,
    ) -> FunctionToolCallResult:
        """Execute a single function tool wrapped in semaphore and timeout bounds."""
        target_fn = spec.tool_func or self._registered_functions.get(spec.function_name)
        start_t = time.perf_counter()

        if target_fn is None:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return FunctionToolCallResult(
                call_id=spec.call_id,
                function_name=spec.function_name,
                success=False,
                error=f"Function '{spec.function_name}' not registered in runtime",
                duration_ms=elapsed,
            )

        async with semaphore:
            try:
                if inspect.iscoroutinefunction(target_fn):
                    coro = target_fn(**spec.arguments)
                    raw_res = await asyncio.wait_for(coro, timeout=spec.timeout_seconds)
                else:
                    # Sync function offloaded to thread
                    raw_res = await asyncio.wait_for(
                        asyncio.to_thread(target_fn, **spec.arguments),
                        timeout=spec.timeout_seconds,
                    )

                elapsed = (time.perf_counter() - start_t) * 1000.0
                return FunctionToolCallResult(
                    call_id=spec.call_id,
                    function_name=spec.function_name,
                    success=True,
                    result=raw_res,
                    duration_ms=elapsed,
                )

            except asyncio.TimeoutError:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                return FunctionToolCallResult(
                    call_id=spec.call_id,
                    function_name=spec.function_name,
                    success=False,
                    error=f"Tool '{spec.function_name}' exceeded timeout of {spec.timeout_seconds}s",
                    timed_out=True,
                    duration_ms=elapsed,
                )
            except Exception as ex:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                return FunctionToolCallResult(
                    call_id=spec.call_id,
                    function_name=spec.function_name,
                    success=False,
                    error=str(ex),
                    duration_ms=elapsed,
                )

    async def execute_concurrent_tools(
        self,
        tool_calls: List[Union[FunctionToolCallSpec, Dict[str, Any]]],
    ) -> List[FunctionToolCallResult]:
        """
        Concurrently execute a batch of tool requests, preserving order in returned results.
        """
        if not tool_calls:
            return []

        norm_specs: List[FunctionToolCallSpec] = []
        for tc in tool_calls:
            if isinstance(tc, FunctionToolCallSpec):
                norm_specs.append(tc)
            elif isinstance(tc, dict):
                norm_specs.append(FunctionToolCallSpec.from_dict(tc))

        semaphore = asyncio.Semaphore(self.max_concurrency)
        self._total_batches += 1
        self._total_tool_executions += len(norm_specs)

        tasks = [self._execute_single_tool(spec, semaphore) for spec in norm_specs]
        results = await asyncio.gather(*tasks)
        return list(results)

    def execute_concurrent_tools_sync(
        self,
        tool_calls: List[Union[FunctionToolCallSpec, Dict[str, Any]]],
    ) -> List[FunctionToolCallResult]:
        """Synchronous wrapper for concurrent batch execution."""
        return asyncio.run(self.execute_concurrent_tools(tool_calls))

    def get_metrics(self) -> Dict[str, Any]:
        """Return runtime concurrency statistics."""
        return {
            "max_concurrency": self.max_concurrency,
            "total_batches_executed": self._total_batches,
            "total_tool_executions": self._total_tool_executions,
            "registered_functions_count": len(self._registered_functions),
        }
