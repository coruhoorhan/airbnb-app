"""
MCP Action Tool Concurrency v4.

Inspired by MCP runtime concurrency trends: Safely executes MCP action tools
concurrently using server-aware rate limiting, semaphore isolation, timeout
controls, and order preservation.
"""

import asyncio
import inspect
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class MCPToolCallSpec:
    """Represents an individual tool call specification in a concurrent batch."""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    server_prefix: Optional[str] = None
    timeout_seconds: float = 30.0
    tool_func: Optional[Callable[..., Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("tool_func", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPToolCallSpec":
        name = data.get("name") or data.get("tool_name") or ""
        args = data.get("arguments") or data.get("args") or data.get("kwargs") or {}
        c_id = data.get("call_id") or data.get("id") or f"call_{uuid.uuid4().hex[:8]}"
        timeout = float(data.get("timeout_seconds", data.get("timeout", 30.0)))
        server = data.get("server_prefix")
        if not server and "_" in name:
            server = name.split("_", 1)[0]

        return cls(
            name=name,
            arguments=args,
            call_id=c_id,
            server_prefix=server or "default",
            timeout_seconds=timeout,
            tool_func=data.get("tool_func"),
        )


@dataclass
class MCPToolExecutionResult:
    """Represents the execution outcome of an individual MCP action tool."""

    call_id: str
    tool_name: str
    server_prefix: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPActionToolConcurrencyV4:
    """
    Concurrent executor for MCP action tools with server-aware rate limiting,
    dynamic per-server semaphores, timeout enforcement, and result ordering.
    """

    def __init__(
        self,
        max_global_concurrency: int = 12,
        max_per_server_concurrency: int = 4,
        default_timeout: float = 30.0,
        mcp_client: Optional[Any] = None,
        tool_resolver: Optional[Callable[[str], Optional[Callable[..., Any]]]] = None,
    ) -> None:
        self.max_global_concurrency = max_global_concurrency
        self.max_per_server_concurrency = max_per_server_concurrency
        self.default_timeout = default_timeout
        self.mcp_client = mcp_client
        self.tool_resolver = tool_resolver
        self.global_semaphore = asyncio.Semaphore(max_global_concurrency)
        self._server_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.max_per_server_concurrency)
        )
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "timed_out_calls": 0,
            "batches_executed": 0,
            "peak_concurrency": 0,
        }
        self._active_calls = 0
        self._lock = asyncio.Lock()

    def _get_server_semaphore(self, server_prefix: str) -> asyncio.Semaphore:
        return self._server_semaphores[server_prefix]

    async def _execute_single_tool(
        self,
        spec: MCPToolCallSpec,
    ) -> MCPToolExecutionResult:
        """Executes a single MCP action tool with timeout and nested semaphores."""
        server = spec.server_prefix or "default"
        server_sem = self._get_server_semaphore(server)
        start_time = time.perf_counter()

        async with self.global_semaphore:
            async with server_sem:
                async with self._lock:
                    self._active_calls += 1
                    if self._active_calls > self.metrics["peak_concurrency"]:
                        self.metrics["peak_concurrency"] = self._active_calls

                try:
                    # 1. Resolve executable function
                    func = spec.tool_func
                    if not func and self.tool_resolver:
                        func = self.tool_resolver(spec.name)

                    if not func and self.mcp_client:
                        if hasattr(self.mcp_client, "execute_tool"):
                            func = lambda **kw: self.mcp_client.execute_tool(spec.name, **kw)
                        elif hasattr(self.mcp_client, "call_tool"):
                            func = lambda **kw: self.mcp_client.call_tool(spec.name, kw)

                    if not func:
                        # Fallback mock tool execution
                        async def _mock_tool(**kwargs):
                            await asyncio.sleep(0.01)
                            return f"Mock executed {spec.name} with {kwargs}"
                        func = _mock_tool

                    # 2. Execute with timeout
                    if inspect.iscoroutinefunction(func):
                        coro = func(**spec.arguments)
                    else:
                        coro = asyncio.to_thread(func, **spec.arguments)

                    res = await asyncio.wait_for(coro, timeout=spec.timeout_seconds)
                    duration = (time.perf_counter() - start_time) * 1000.0

                    async with self._lock:
                        self.metrics["total_calls"] += 1
                        self.metrics["successful_calls"] += 1

                    return MCPToolExecutionResult(
                        call_id=spec.call_id,
                        tool_name=spec.name,
                        server_prefix=server,
                        success=True,
                        result=res,
                        duration_ms=duration,
                    )

                except asyncio.TimeoutError:
                    duration = (time.perf_counter() - start_time) * 1000.0
                    async with self._lock:
                        self.metrics["total_calls"] += 1
                        self.metrics["failed_calls"] += 1
                        self.metrics["timed_out_calls"] += 1

                    logger.warning(f"Tool {spec.name} ({spec.call_id}) timed out after {spec.timeout_seconds}s")
                    return MCPToolExecutionResult(
                        call_id=spec.call_id,
                        tool_name=spec.name,
                        server_prefix=server,
                        success=False,
                        result=None,
                        error=f"Execution timed out after {spec.timeout_seconds}s",
                        duration_ms=duration,
                        timed_out=True,
                    )

                except Exception as e:
                    duration = (time.perf_counter() - start_time) * 1000.0
                    async with self._lock:
                        self.metrics["total_calls"] += 1
                        self.metrics["failed_calls"] += 1

                    logger.error(f"Error executing tool {spec.name}: {e}")
                    return MCPToolExecutionResult(
                        call_id=spec.call_id,
                        tool_name=spec.name,
                        server_prefix=server,
                        success=False,
                        result=None,
                        error=str(e),
                        duration_ms=duration,
                    )
                finally:
                    async with self._lock:
                        self._active_calls -= 1

    async def execute_action_tools_concurrently(
        self,
        tool_calls: List[Union[Dict[str, Any], MCPToolCallSpec]],
    ) -> List[MCPToolExecutionResult]:
        """
        Executes a batch of action tools concurrently while strictly preserving
        the original list order in the returned results.
        """
        if not tool_calls:
            return []

        specs: List[MCPToolCallSpec] = []
        for call in tool_calls:
            if isinstance(call, MCPToolCallSpec):
                specs.append(call)
            elif isinstance(call, dict):
                specs.append(MCPToolCallSpec.from_dict(call))

        self.metrics["batches_executed"] += 1
        logger.info(f"Executing batch of {len(specs)} MCP action tools concurrently.")

        tasks = [self._execute_single_tool(spec) for spec in specs]
        results = await asyncio.gather(*tasks)
        return list(results)

    def execute_sync(
        self,
        tool_calls: List[Union[Dict[str, Any], MCPToolCallSpec]],
    ) -> List[MCPToolExecutionResult]:
        """Synchronous helper for executing concurrent action tool batches."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(self.execute_action_tools_concurrently(tool_calls)))
                return future.result()
        else:
            return asyncio.run(self.execute_action_tools_concurrently(tool_calls))
