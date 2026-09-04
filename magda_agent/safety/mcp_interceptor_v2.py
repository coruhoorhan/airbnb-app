"""
MCP Tool Registry Auth Interceptor V2.

Provides a runtime interceptor for the MCP dynamic tool registry to block
unsafe external calls, unauthorized server endpoints, blacklisted action tools,
and unverified external payloads.
"""

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class MCPAuthStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNAUTHORIZED = "unauthorized"


@dataclass
class MCPAuthInterceptResult:
    """Represents the outcome of an intercepted MCP tool execution."""

    success: bool
    allowed: bool
    result: Any
    message: str
    tool_name: str
    server_name: str
    status: MCPAuthStatus
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPToolRegistryAuthInterceptorV2:
    """
    Runtime security and authorization interceptor for the MCP dynamic tool registry.
    Evaluates tool and server access policies, intercepts malicious or blocked calls,
    and logs all authorization decisions to the audit trail.
    """

    DEFAULT_BLOCKED_TOOLS = {
        "mcp_system_shutdown",
        "mcp_format_disk",
        "mcp_raw_kernel_exec",
        "mcp_drop_database_all",
    }

    DEFAULT_BLOCKED_SERVERS = {
        "untrusted_external_mesh",
        "malicious_relay_server",
    }

    def __init__(
        self,
        blocked_tools: Optional[Set[str]] = None,
        blocked_servers: Optional[Set[str]] = None,
        allowed_servers: Optional[Set[str]] = None,
        require_auth_token: bool = False,
        auth_validator: Optional[Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], Tuple[bool, str]]] = None,
        audit_trail: Optional[Any] = None,
    ) -> None:
        self.blocked_tools = set(blocked_tools if blocked_tools is not None else self.DEFAULT_BLOCKED_TOOLS)
        self.blocked_servers = set(blocked_servers if blocked_servers is not None else self.DEFAULT_BLOCKED_SERVERS)
        self.allowed_servers = set(allowed_servers) if allowed_servers is not None else None
        self.require_auth_token = require_auth_token
        self.auth_validator = auth_validator
        self.audit_trail = audit_trail
        self._audit_logs: List[Dict[str, Any]] = []

    def block_tool(self, tool_name: str) -> None:
        """Adds a tool to the runtime blacklist."""
        self.blocked_tools.add(tool_name.lower())
        logger.info(f"Blocked MCP tool: {tool_name}")

    def unblock_tool(self, tool_name: str) -> None:
        """Removes a tool from the runtime blacklist."""
        self.blocked_tools.discard(tool_name.lower())
        logger.info(f"Unblocked MCP tool: {tool_name}")

    def block_server(self, server_name: str) -> None:
        """Blocks all tool calls routed to a specific server."""
        self.blocked_servers.add(server_name.lower())
        logger.info(f"Blocked MCP server: {server_name}")

    def unblock_server(self, server_name: str) -> None:
        """Unblocks a server."""
        self.blocked_servers.discard(server_name.lower())
        logger.info(f"Unblocked MCP server: {server_name}")

    def _extract_server_name(self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Extracts target server name from context, arguments, or tool name prefix."""
        context = context or {}
        if "server_name" in context:
            return str(context["server_name"])
        if "server" in arguments:
            return str(arguments["server"])

        # Check known servers from blocked_servers and allowed_servers
        known_servers = set(self.blocked_servers)
        if self.allowed_servers:
            known_servers.update(self.allowed_servers)

        for s in sorted(known_servers, key=len, reverse=True):
            if tool_name.lower().startswith(s.lower() + "_") or tool_name.lower() == s.lower():
                return s

        if "_" in tool_name:
            return tool_name.split("_", 1)[0]
        return "default"

    def is_call_authorized(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, MCPAuthStatus]:
        """
        Evaluates tool policies, server boundaries, and auth tokens.
        Returns (is_authorized, reason, auth_status).
        """
        t_lower = tool_name.lower()
        context = context or {}
        server_name = self._extract_server_name(tool_name, arguments, context).lower()

        # 1. Check blocked tools
        if t_lower in self.blocked_tools:
            return False, f"Tool '{tool_name}' is blacklisted by runtime registry security policy.", MCPAuthStatus.BLOCKED

        # 2. Check blocked servers
        for blocked_s in self.blocked_servers:
            if server_name == blocked_s or t_lower.startswith(blocked_s + "_") or f"_{blocked_s}_" in t_lower:
                return False, f"Server '{blocked_s}' is blacklisted from receiving MCP tool calls.", MCPAuthStatus.BLOCKED

        # 3. Check allowed servers whitelist (if configured)
        if self.allowed_servers is not None:
            is_whitelisted = any(
                server_name == allowed_s or t_lower.startswith(allowed_s + "_")
                for allowed_s in self.allowed_servers
            )
            if not is_whitelisted:
                return False, f"Server '{server_name}' is not in the allowed servers whitelist.", MCPAuthStatus.UNAUTHORIZED

        # 4. Check auth token requirement
        if self.require_auth_token:
            token = context.get("auth_token") or arguments.get("auth_token")
            if not token:
                return False, f"Tool '{tool_name}' requires an active auth token.", MCPAuthStatus.UNAUTHORIZED

        # 5. Check custom auth validator
        if self.auth_validator:
            try:
                valid, reason = self.auth_validator(tool_name, arguments, context)
                if not valid:
                    return False, f"Custom authorization check failed: {reason}", MCPAuthStatus.BLOCKED
            except Exception as e:
                logger.error(f"Auth validator raised exception: {e}")
                return False, f"Auth validator error: {e}", MCPAuthStatus.BLOCKED

        return True, "Call authorized.", MCPAuthStatus.ALLOWED

    def _log_audit(self, result: MCPAuthInterceptResult, arguments: Dict[str, Any]) -> None:
        entry = result.to_dict()
        entry["arguments"] = arguments
        self._audit_logs.append(entry)

        if self.audit_trail:
            try:
                if hasattr(self.audit_trail, "log"):
                    self.audit_trail.log(
                        tool_name=result.tool_name,
                        args=arguments,
                        result=result.result if result.allowed else f"BLOCKED: {result.message}",
                        status=result.status.value,
                        why=result.message,
                    )
            except Exception as e:
                logger.warning(f"Failed to record to external audit trail: {e}")

    async def intercept_and_execute(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPAuthInterceptResult:
        """
        Intercepts tool call, verifies authorization, and executes within security boundaries.
        """
        arguments = arguments or {}
        context = context or {}
        start_time = time.perf_counter()
        server_name = self._extract_server_name(tool_name, arguments, context)

        is_auth, reason, status = self.is_call_authorized(tool_name, arguments, context)

        if not is_auth:
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.warning(f"MCP Interceptor blocked call '{tool_name}': {reason}")

            result = MCPAuthInterceptResult(
                success=False,
                allowed=False,
                result=None,
                message=f"SAFETY INTERCEPT: {reason}",
                tool_name=tool_name,
                server_name=server_name,
                status=status,
                execution_time_ms=duration,
            )
            self._log_audit(result, arguments)
            return result

        # Authorized: Execute function
        try:
            if inspect.iscoroutinefunction(tool_func):
                exec_res = await tool_func(**arguments)
            else:
                exec_res = tool_func(**arguments)

            duration = (time.perf_counter() - start_time) * 1000.0
            result = MCPAuthInterceptResult(
                success=True,
                allowed=True,
                result=exec_res,
                message="Tool executed successfully.",
                tool_name=tool_name,
                server_name=server_name,
                status=MCPAuthStatus.ALLOWED,
                execution_time_ms=duration,
            )
            self._log_audit(result, arguments)
            return result
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Error executing tool '{tool_name}': {e}")
            result = MCPAuthInterceptResult(
                success=False,
                allowed=True,
                result=None,
                message=f"Execution error: {e}",
                tool_name=tool_name,
                server_name=server_name,
                status=MCPAuthStatus.ALLOWED,
                execution_time_ms=duration,
            )
            self._log_audit(result, arguments)
            return result

    def intercept_sync(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPAuthInterceptResult:
        """Synchronous wrapper for tool interception."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.intercept_and_execute(
                            tool_func=tool_func,
                            tool_name=tool_name,
                            arguments=arguments,
                            context=context,
                        )
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.intercept_and_execute(
                    tool_func=tool_func,
                    tool_name=tool_name,
                    arguments=arguments,
                    context=context,
                )
            )

    def wrap_tool(self, tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator that wraps a tool function with interception and auth checks."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if inspect.iscoroutinefunction(func):
                async def async_wrapper(**kwargs: Any) -> Any:
                    res = await self.intercept_and_execute(func, tool_name, kwargs)
                    if not res.allowed:
                        raise PermissionError(res.message)
                    if not res.success:
                        raise RuntimeError(res.message)
                    return res.result
                return async_wrapper
            else:
                def sync_wrapper(**kwargs: Any) -> Any:
                    res = self.intercept_sync(func, tool_name, kwargs)
                    if not res.allowed:
                        raise PermissionError(res.message)
                    if not res.success:
                        raise RuntimeError(res.message)
                    return res.result
                return sync_wrapper
        return decorator

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        return list(self._audit_logs)
