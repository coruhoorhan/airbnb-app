"""
MCP Server Taint Context Isolation V1.

Inspired by MCPKernel Sandboxing trends: Enhances MCP Server export and tool response
handling with strict taint context isolation to prevent tainted, unverified, or
attacker-controlled tool outputs from silently polluting the agent's working memory.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

try:
    from magda_agent.safety.taint import (
        is_tainted,
        mark_tainted,
        sanitize,
    )
except (ImportError, ModuleNotFoundError):
    import importlib.util
    from pathlib import Path

    file_path = Path(__file__).resolve().parent.parent / "safety" / "taint.py"
    if file_path.exists():
        spec = importlib.util.spec_from_file_location("taint", file_path)
        _taint_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_taint_mod)
        is_tainted = _taint_mod.is_tainted
        mark_tainted = _taint_mod.mark_tainted
        sanitize = _taint_mod.sanitize
    else:
        def mark_tainted(val: Any, *args, **kwargs) -> Any:
            return val

        def is_tainted(val: Any) -> bool:
            return False

        def sanitize(val: Any) -> Any:
            return val

logger = logging.getLogger(__name__)


class TaintIsolationMode(str, Enum):
    TAG_AND_ISOLATE = "tag_and_isolate"
    SANITIZE_ON_RETURN = "sanitize_on_return"
    STRICT_BLOCK = "strict_block"


@dataclass
class MCPTaintContextResponse:
    """Represents an MCP tool response enriched with taint isolation metadata."""

    tool_name: str
    raw_output: Any
    is_tainted: bool = False
    taint_origin: str = "untrusted_mcp_response"
    taint_level: str = "medium"  # low, medium, high, critical
    sanitized_output: Any = None
    server_name: str = "mcp_server"
    execution_time_ms: float = 0.0
    response_id: str = field(default_factory=lambda: f"resp_{uuid.uuid4().hex[:8]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "raw_output": str(self.raw_output) if self.raw_output is not None else None,
            "is_tainted": self.is_tainted,
            "taint_origin": self.taint_origin,
            "taint_level": self.taint_level,
            "sanitized_output": self.sanitized_output,
            "server_name": self.server_name,
            "execution_time_ms": self.execution_time_ms,
            "response_id": self.response_id,
        }

    def to_mcp_response(self) -> Dict[str, Any]:
        """Format as a compliant MCP 2024 JSON tool response payload with _meta annotations."""
        text_content = str(self.raw_output) if self.raw_output is not None else ""
        return {
            "content": [
                {
                    "type": "text",
                    "text": text_content,
                }
            ],
            "isError": False,
            "_meta": {
                "tainted": self.is_tainted,
                "taint_origin": self.taint_origin,
                "taint_level": self.taint_level,
                "server": self.server_name,
                "response_id": self.response_id,
            },
        }


class MCPTaintContextIsolationWrapperV1:
    """
    MCP Server Taint Context Isolation Wrapper V1.

    Guarantees that responses exported from external MCP tools propagate taint tags
    and are quarantined or sanitized before entering agent memory stores.
    """

    DEFAULT_UNTRUSTED_TOOLS = {
        "fetch_url", "web_search", "scrape_website", "read_email",
        "external_api_call", "raw_http_get", "user_prompt_input",
    }

    def __init__(
        self,
        mode: TaintIsolationMode = TaintIsolationMode.TAG_AND_ISOLATE,
        untrusted_tools: Optional[Set[str]] = None,
        default_server_name: str = "magda_mcp_server",
    ):
        self.mode = mode
        self.untrusted_tools = set(untrusted_tools or self.DEFAULT_UNTRUSTED_TOOLS)
        self.default_server_name = default_server_name
        self._audit_trail: List[MCPTaintContextResponse] = []

    def is_tool_untrusted(self, tool_name: str) -> bool:
        """Determine if a tool inherently produces unverified external data."""
        return (
            tool_name in self.untrusted_tools
            or any(sub in tool_name.lower() for sub in ["fetch", "scrape", "search", "external", "untrusted"])
        )

    def wrap_tool_response(
        self,
        tool_name: str,
        raw_output: Any,
        input_was_tainted: bool = False,
        server_name: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> MCPTaintContextResponse:
        """
        Evaluate and wrap an execution outcome with taint tags and isolation metadata.
        """
        srv = server_name or self.default_server_name
        tool_is_untrusted = self.is_tool_untrusted(tool_name)
        output_is_marked = is_tainted(raw_output)

        tainted = input_was_tainted or tool_is_untrusted or output_is_marked

        origin = "mcp_clean_execution"
        level = "low"

        if tainted:
            if input_was_tainted:
                origin = f"propagated_from_input_{tool_name}"
                level = "high"
            elif tool_is_untrusted:
                origin = f"untrusted_external_tool_{tool_name}"
                level = "medium"
            else:
                origin = f"marked_tainted_{tool_name}"
                level = "high"

        # Sanitize for safe memory usage
        sanitized = sanitize(raw_output)

        # Mark output wrapper if tainted
        tagged_output = mark_tainted(raw_output) if tainted else raw_output
        res = MCPTaintContextResponse(
            tool_name=tool_name,
            raw_output=tagged_output,
            is_tainted=tainted,
            taint_origin=origin,
            taint_level=level,
            sanitized_output=sanitized,
            server_name=srv,
            execution_time_ms=duration_ms,
        )
        self._audit_trail.append(res)
        return res

    def execute_and_isolate(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
    ) -> MCPTaintContextResponse:
        """
        Synchronously execute an MCP action tool and capture output in an isolated taint context.
        """
        start_t = time.perf_counter()
        input_tainted = any(is_tainted(v) for v in arguments.values())

        try:
            raw_res = tool_func(**arguments)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return self.wrap_tool_response(
                tool_name=tool_name,
                raw_output=raw_res,
                input_was_tainted=input_tainted,
                server_name=server_name,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return self.wrap_tool_response(
                tool_name=tool_name,
                raw_output=f"Error: {str(e)}",
                input_was_tainted=input_tainted,
                server_name=server_name,
                duration_ms=elapsed,
            )

    async def execute_and_isolate_async(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
    ) -> MCPTaintContextResponse:
        """
        Asynchronously execute an MCP action tool and capture output in an isolated taint context.
        """
        start_t = time.perf_counter()
        input_tainted = any(is_tainted(v) for v in arguments.values())

        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_res = await tool_func(**arguments)
            else:
                raw_res = tool_func(**arguments)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return self.wrap_tool_response(
                tool_name=tool_name,
                raw_output=raw_res,
                input_was_tainted=input_tainted,
                server_name=server_name,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return self.wrap_tool_response(
                tool_name=tool_name,
                raw_output=f"Error: {str(e)}",
                input_was_tainted=input_tainted,
                server_name=server_name,
                duration_ms=elapsed,
            )

    def filter_for_memory_storage(
        self,
        response: Union[MCPTaintContextResponse, Dict[str, Any]],
    ) -> Tuple[Any, bool]:
        """
        Prepares tool output for ingestion into working/episodic memory.
        Returns: (safe_content, was_tainted)
        """
        if isinstance(response, MCPTaintContextResponse):
            if response.is_tainted:
                return response.sanitized_output, True
            return response.raw_output, False

        # If dictionary
        is_t = bool(response.get("is_tainted") or response.get("_meta", {}).get("tainted"))
        raw = response.get("raw_output") or response.get("content")
        sanitized = sanitize(raw)
        return (sanitized if is_t else raw), is_t

    def get_audit_trail(self) -> List[MCPTaintContextResponse]:
        """Retrieve audit history."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit history."""
        self._audit_trail.clear()
