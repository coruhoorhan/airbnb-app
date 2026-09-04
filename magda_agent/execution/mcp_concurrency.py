import asyncio
import inspect
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

class MCPConcurrencyLimitError(Exception):
    """Exception raised when MCP concurrency limits or backpressure constraints are violated."""
    pass

class MCPConcurrencyManager:
    """
    A specialized concurrency manager for asynchronously executing multiple
    MCP (Model Context Protocol) server-prefixed tools and safely merging results.

    Inspired by OpenAI Agents SDK and designed for enterprise-grade safety,
    rate limiting, backpressure mitigation, and isolation of failures.
    """

    def __init__(
        self,
        mcp_client: Any = None,
        servers: Optional[Dict[str, Any]] = None,
        max_concurrency_per_server: int = 5,
        global_max_concurrency: int = 20,
        rate_limit_per_second: float = 10.0,
        separators: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        """
        Initializes the MCPConcurrencyManager.

        Args:
            mcp_client: The default MCP client or registry to invoke tools.
            servers: A dictionary mapping server prefixes to their respective server or client instances.
            max_concurrency_per_server: Maximum concurrent tasks allowed per server prefix.
            global_max_concurrency: Maximum concurrent tasks allowed globally.
            rate_limit_per_second: Global rate limit per second.
            separators: Supported prefix separators (e.g. '__', '-', '_', ':').
            timeout_seconds: Optional timeout in seconds for executing any single tool.
        """
        self.mcp_client = mcp_client
        self.servers = servers or {}
        self.separators = separators or ["__", "-", "_", ":"]
        self.timeout_seconds = timeout_seconds

        self.global_semaphore = asyncio.Semaphore(global_max_concurrency)
        self.semaphores: Dict[str, asyncio.Semaphore] = {
            prefix: asyncio.Semaphore(max_concurrency_per_server)
            for prefix in self.servers
        }
        self.default_semaphore = asyncio.Semaphore(max_concurrency_per_server)

        self.rate_limit_per_second = rate_limit_per_second
        self._last_execution_times: List[float] = []
        self._execution_lock = asyncio.Lock()

        self._active_tasks = 0
        self._max_queue_size = global_max_concurrency * 2

    async def _check_rate_limit(self) -> None:
        """
        Enforces the global rate limit. Backs off if exceeded.
        """
        while True:
            async with self._execution_lock:
                now = asyncio.get_event_loop().time()
                # Clean up old timestamps (older than 1 second)
                self._last_execution_times = [t for t in self._last_execution_times if now - t < 1.0]

                if len(self._last_execution_times) < self.rate_limit_per_second:
                    self._last_execution_times.append(now)
                    return

                oldest = self._last_execution_times[0]
                sleep_time = 1.0 - (now - oldest)

            if sleep_time > 0:
                logger.warning(f"Rate limit exceeded. Throttling for {sleep_time:.2f}s.")
                await asyncio.sleep(sleep_time)

    def _resolve_tool(self, name: str) -> Tuple[Optional[str], Optional[Any], str]:
        """
        Resolves a tool name to its respective server prefix, target server/client instance,
        and its stripped, unprefixed name.

        Args:
            name (str): The full tool name.

        Returns:
            Tuple[Optional[str], Optional[Any], str]: (prefix, target_server, unprefixed_name)
        """
        if not name:
            return None, None, ""

        # Sort prefixes by length descending to match longest prefix first
        sorted_prefixes = sorted(self.servers.keys(), key=len, reverse=True)
        for prefix in sorted_prefixes:
            if not prefix:
                continue
            for sep in self.separators:
                full_prefix = f"{prefix}{sep}"
                if name.startswith(full_prefix):
                    unprefixed = name[len(full_prefix):]
                    return prefix, self.servers[prefix], unprefixed

        return None, self.mcp_client, name

    def _unwrap_result(self, result: Any) -> Any:
        """
        Unwraps and formats standard JSON-RPC or MCP response formats into clean outputs.
        """
        if isinstance(result, dict):
            if "result" in result:
                inner = result["result"]
                if isinstance(inner, dict) and "content" in inner:
                    content = inner["content"]
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", result)
                return inner
            if "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", result)
        return result

    async def _execute_single_call(self, name: Optional[str], kwargs: Dict[str, Any]) -> Any:
        """
        Executes a single tool call with safety, rate limiting, and exception isolation.
        """
        if not name:
            return "Error: Empty tool name provided."

        if self._active_tasks >= self._max_queue_size:
            return f"Error: System under heavy load (BackpressureError). Max queue size {self._max_queue_size} exceeded."

        self._active_tasks += 1
        try:
            await self._check_rate_limit()

            prefix, server, unprefixed_name = self._resolve_tool(name)
            sem = self.semaphores.get(prefix, self.default_semaphore) if prefix else self.default_semaphore

            async with self.global_semaphore:
                async with sem:
                    try:
                        # Define execution task
                        async def task_coro():
                            if server is not None:
                                # 1. If server is MCPServer or has handle_rpc_request
                                if hasattr(server, "exporter") and hasattr(server.exporter, "handle_rpc_request"):
                                    rpc_req = {
                                        "jsonrpc": "2.0",
                                        "id": "mcp-concurrency-req",
                                        "method": unprefixed_name,
                                        "params": kwargs
                                    }
                                    res = await server.exporter.handle_rpc_request(rpc_req)
                                    if isinstance(res, dict) and "error" in res:
                                        err_msg = res["error"].get("message", "Unknown RPC error")
                                        return f"Error: {err_msg}"
                                    return self._unwrap_result(res)

                                # 2. If server has execute_tool or execute methods
                                elif hasattr(server, "execute_tool"):
                                    res = server.execute_tool(name, kwargs)
                                    if inspect.isawaitable(res):
                                        res = await res
                                    return self._unwrap_result(res)
                                elif hasattr(server, "execute"):
                                    res = server.execute(name, kwargs)
                                    if inspect.isawaitable(res):
                                        res = await res
                                    return self._unwrap_result(res)

                                # 3. If server has execute_skill or is a skill registry
                                elif hasattr(server, "execute_skill") and hasattr(server, "skills"):
                                    if unprefixed_name not in server.skills:
                                        return f"Error: Skill '{unprefixed_name}' not found on server '{prefix}'."

                                    if inspect.iscoroutinefunction(server.execute_skill):
                                        res = await server.execute_skill(unprefixed_name, **kwargs)
                                    else:
                                        skill_func = server.skills[unprefixed_name]
                                        if inspect.iscoroutinefunction(skill_func):
                                            res = server.execute_skill(unprefixed_name, **kwargs)
                                        else:
                                            res = await asyncio.to_thread(server.execute_skill, unprefixed_name, **kwargs)

                                    if inspect.isawaitable(res):
                                        res = await res
                                    return self._unwrap_result(res)

                                # 4. If server has handle_request method
                                elif hasattr(server, "handle_request"):
                                    rpc_req = {
                                        "jsonrpc": "2.0",
                                        "id": "mcp-concurrency-req",
                                        "method": name,
                                        "params": kwargs
                                    }
                                    res_str = await server.handle_request(json.dumps(rpc_req))
                                    res = json.loads(res_str)
                                    if isinstance(res, dict) and "error" in res:
                                        err_msg = res["error"].get("message", "Unknown RPC error")
                                        return f"Error: {err_msg}"
                                    return self._unwrap_result(res)

                                # 5. If server is callable
                                elif callable(server):
                                    if inspect.iscoroutinefunction(server):
                                        res = await server(unprefixed_name, **kwargs)
                                    else:
                                        res = await asyncio.to_thread(server, unprefixed_name, **kwargs)
                                    return self._unwrap_result(res)

                                else:
                                    return f"Error: Server '{prefix}' interface not supported."
                            else:
                                return f"Error: No client or server found for tool '{name}'."

                        if self.timeout_seconds is not None:
                            return await asyncio.wait_for(task_coro(), timeout=self.timeout_seconds)
                        else:
                            return await task_coro()

                    except asyncio.TimeoutError:
                        return f"Error: Tool execution timed out after {self.timeout_seconds}s."
                    except Exception as e:
                        return f"Error: Tool execution failed: {str(e)}"
        finally:
            self._active_tasks -= 1

    async def execute_concurrently(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """
        Executes multiple MCP server-prefixed tool calls concurrently using asyncio.gather.

        Args:
            tool_calls (List[Dict[str, Any]]): A list of dictionaries representing tool calls,
                                              where each dict contains 'name' and optionally 'kwargs'.

        Returns:
            List[Any]: A list of results corresponding to the completed tasks in the original order.
        """
        tasks = []
        for call in tool_calls:
            name = call.get("name")
            kwargs = call.get("kwargs", {})
            tasks.append(self._execute_single_call(name, kwargs))

        return await asyncio.gather(*tasks)
