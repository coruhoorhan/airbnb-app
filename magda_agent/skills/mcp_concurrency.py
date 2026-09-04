import asyncio
import inspect
from typing import Any, Dict, List, Optional

class MCPConcurrentSkillExecutor:
    """Executes multiple MCP server-prefixed skills concurrently using asyncio.gather.

    This class enables runtime function tool concurrency for MCP tools.
    It batches concurrent MCP tool calls heading to the same server.
    """

    def __init__(self, mcp_client: Any) -> None:
        """
        Initializes the executor with the given MCP client.

        Args:
            mcp_client: The MCP client or tool registry that can resolve and execute MCP tools.
        """
        self.mcp_client = mcp_client

    async def execute_mcp_tools_concurrently(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """
        Executes a list of MCP tool calls concurrently, batching calls to the same server.
        Each element in tool_calls must have 'name' and 'kwargs'.
        It assumes the server name is the part before the first '-' in the tool name (e.g. 'server1-tool_a').

        Args:
            tool_calls: A list of tool call dicts containing the tool name and arguments.

        Returns:
            A list of execution results corresponding to the input tool_calls.
        """
        # We need a special marker because legitimate results can be None
        _UNSET = object()

        # Batch calls by server prefix
        batches = {}
        for call in tool_calls:
            name = call.get("name", "")
            kwargs = call.get("kwargs", {})

            # Extract server prefix (e.g. 'math_server-add' -> 'math_server')
            server_prefix = name.split("-")[0] if "-" in name else name

            if server_prefix not in batches:
                batches[server_prefix] = []
            batches[server_prefix].append((name, kwargs))

        async def run_tool(n: str, kw: dict) -> Any:
            """Run a single tool.

            Args:
                n: Tool name
                kw: Keyword arguments

            Returns:
                The result of the execution.
            """
            try:
                func_to_call = None
                call_args = ()
                call_kwargs = {}

                if hasattr(self.mcp_client, "execute_tool"):
                    func_to_call = self.mcp_client.execute_tool
                    call_args = (n, kw)
                elif hasattr(self.mcp_client, "execute"):
                    func_to_call = self.mcp_client.execute
                    call_args = (n, kw)
                elif hasattr(self.mcp_client, "skills") and n in self.mcp_client.skills:
                    func_to_call = self.mcp_client.skills[n]
                    call_kwargs = kw
                else:
                    return f"Error: MCP Tool '{n}' not found or client missing execute method."

                is_async = False
                if inspect.iscoroutinefunction(func_to_call):
                    is_async = True
                elif hasattr(func_to_call, "__is_async__") and getattr(func_to_call, "__is_async__"):
                    is_async = True
                elif hasattr(func_to_call, "__call__") and inspect.iscoroutinefunction(func_to_call.__call__):
                    is_async = True

                if is_async:
                    result = func_to_call(*call_args, **call_kwargs)
                else:
                    def sync_wrapper():
                        return func_to_call(*call_args, **call_kwargs)
                    result = await asyncio.to_thread(sync_wrapper)

                if inspect.isawaitable(result):
                    return await result
                return result
            except Exception as e:
                return f"Error executing '{n}': {e}"

        # If the client supports execute_batch, we can use it. Otherwise, fallback to individual execution.
        async def process_batch(server: str, calls_in_batch: List[tuple[str, dict]]) -> Any:
            """Process a batch of tools on the given server.

            Args:
                server: The server prefix.
                calls_in_batch: A list of tuples containing tool name and kwargs.

            Returns:
                A list of execution results.
            """
            if hasattr(self.mcp_client, "execute_batch"):
                try:
                    # Assume execute_batch takes server_prefix and list of dicts with name/kwargs
                    batch_request = [{"name": n, "kwargs": kw} for n, kw in calls_in_batch]
                    results = self.mcp_client.execute_batch(server, batch_request)
                    if inspect.isawaitable(results):
                        results = await results
                    return results
                except Exception as e:
                    return [f"Error executing batch on '{server}': {e}"] * len(calls_in_batch)
            else:
                # Fallback to individual execution
                return await asyncio.gather(*(run_tool(n, kw) for n, kw in calls_in_batch))

        # Process each server batch concurrently
        batch_tasks = []
        server_order = list(batches.keys())
        for server in server_order:
            batch_tasks.append(process_batch(server, batches[server]))

        batch_results = await asyncio.gather(*batch_tasks)

        # Reconstruct the results in the original order
        final_results = [_UNSET] * len(tool_calls)
        for server, results in zip(server_order, batch_results):
            for (name, kwargs), result in zip(batches[server], results):
                # Find the original index. (Note: if there are duplicate calls, this simple find might fail.
                # So we iterate over tool_calls and find the first matching one that hasn't been filled).
                for i, call in enumerate(tool_calls):
                    if call.get("name", "") == name and call.get("kwargs", {}) == kwargs and final_results[i] is _UNSET:
                        final_results[i] = result
                        break

        return final_results


class ConcurrentSkillExecutor:
    """Executes multiple skills and MCP server-prefixed tools concurrently using asyncio.gather.

    This class enables concurrent execution of both local registry skills and
    MCP server-prefixed tools, ensuring synchronous methods do not block the event loop.
    """

    def __init__(self, registry: Any, mcp_registry: Optional[Any] = None, mcp_client: Optional[Any] = None) -> None:
        """
        Initializes the ConcurrentSkillExecutor.

        Args:
            registry (Any): The default local skill registry.
            mcp_registry (Optional[Any]): The MCP tool registry to look up metadata.
            mcp_client (Optional[Any]): The MCP client or tool registry that can execute MCP tools.
        """
        self.registry = registry
        self.mcp_registry = mcp_registry
        self.mcp_client = mcp_client or registry

    async def execute_concurrently(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """
        Executes a list of tool calls concurrently, supporting both local and MCP tools.
        Each element in tool_calls must have 'name' and 'kwargs'.

        Args:
            tool_calls: A list of tool call dictionaries.

        Returns:
            A list of execution results corresponding to the input tool_calls.
        """
        tasks = []
        for call in tool_calls:
            name = call.get("name")
            kwargs = call.get("kwargs", {})

            if not name:
                async def error_empty():
                    return "Error: Empty tool name provided."
                tasks.append(error_empty())
                continue

            # Determine if this is an MCP server-prefixed tool
            is_prefixed = "-" in name or "__" in name or ":" in name

            if is_prefixed:
                # Resolve prefix
                if "__" in name:
                    prefix, unprefixed = name.split("__", 1)
                elif "-" in name:
                    prefix, unprefixed = name.split("-", 1)
                elif ":" in name:
                    prefix, unprefixed = name.split(":", 1)
                else:
                    prefix, unprefixed = "", name

                client = self.mcp_client
                async def run_prefixed_tool(n=name, kw=kwargs, cl=client):
                    try:
                        func_to_call = None
                        call_args = ()
                        call_kwargs = {}

                        if hasattr(cl, "execute_tool"):
                            func_to_call = cl.execute_tool
                            call_args = (n, kw)
                        elif hasattr(cl, "execute"):
                            func_to_call = cl.execute
                            call_args = (n, kw)
                        elif hasattr(cl, "execute_skill") and hasattr(cl, "skills") and (n in cl.skills or unprefixed in cl.skills):
                            func_to_call = cl.execute_skill
                            skill_name = n if n in cl.skills else unprefixed
                            call_args = (skill_name,)
                            call_kwargs = kw
                        elif hasattr(cl, "skills") and (n in cl.skills or unprefixed in cl.skills):
                            skill_name = n if n in cl.skills else unprefixed
                            func_to_call = cl.skills[skill_name]
                            call_kwargs = kw
                        else:
                            return f"Error: MCP Tool '{n}' not found or client missing execution method."

                        is_async = False
                        if inspect.iscoroutinefunction(func_to_call):
                            is_async = True
                        elif hasattr(func_to_call, "__is_async__") and getattr(func_to_call, "__is_async__"):
                            is_async = True
                        elif hasattr(func_to_call, "__call__") and inspect.iscoroutinefunction(func_to_call.__call__):
                            is_async = True

                        if is_async:
                            result = func_to_call(*call_args, **call_kwargs)
                        else:
                            def sync_wrapper():
                                return func_to_call(*call_args, **call_kwargs)
                            result = await asyncio.to_thread(sync_wrapper)

                        if inspect.isawaitable(result):
                            return await result
                        return result
                    except Exception as e:
                        return f"Error executing '{n}': {e}"

                tasks.append(run_prefixed_tool())

            else:
                # Local registry skill
                if not self.registry or not hasattr(self.registry, "skills") or name not in self.registry.skills:
                    async def error_not_found(n=name):
                        return f"Error: Skill '{n}' not found."
                    tasks.append(error_not_found())
                    continue

                skill_func = self.registry.skills[name]

                is_async = False
                if self.mcp_registry and hasattr(self.mcp_registry, "get_tool"):
                    tool_metadata = self.mcp_registry.get_tool(name)
                    if tool_metadata and isinstance(tool_metadata, dict):
                        is_async = tool_metadata.get("__is_async__", False)

                if not is_async and inspect.iscoroutinefunction(skill_func):
                    is_async = True

                async def wrap_execution(n=name, k=kwargs, is_async_skill=is_async):
                    try:
                        if is_async_skill:
                            res = self.registry.execute_skill(n, **k)
                            if inspect.isawaitable(res):
                                return await res
                            return res
                        else:
                            res = await asyncio.to_thread(self.registry.execute_skill, n, **k)
                            if inspect.isawaitable(res):
                                return await res
                            return res
                    except Exception as e:
                        return f"Error executing '{n}': {e}"

                tasks.append(wrap_execution())

        return await asyncio.gather(*tasks)
