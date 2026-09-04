"""
MCP Dynamic Verification Sandbox Hook V2.

Inspired by MCP policy layer trends: Implements a dynamic execution hook for
intercepting, verifying, and sandboxing external MCP action tools during runtime.
"""

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class HookPhase(str, Enum):
    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    ON_ERROR = "on_error"
    ON_VIOLATION = "on_violation"


class HookDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_VERIFICATION = "require_verification"
    SANDBOX_ISOLATED = "sandbox_isolated"


@dataclass
class HookExecutionOutcome:
    """Represents the outcome of a sandboxed hook execution."""

    success: bool
    allowed: bool
    result: Any
    message: str
    tool_name: str
    decision: HookDecision
    sandboxed: bool = False
    execution_time_ms: float = 0.0
    hook_id: str = field(default_factory=lambda: f"hook_{uuid.uuid4().hex[:8]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPDynamicVerificationSandboxHookV2:
    """
    Dynamic verification hook that intercepts MCP tool invocations,
    applies pre-execution parameter checks, executes within a sandboxed
    boundary, and validates post-execution results.
    """

    def __init__(
        self,
        blocked_tools: Optional[Set[str]] = None,
        default_timeout: float = 20.0,
        audit_trail: Optional[Any] = None,
    ) -> None:
        self.blocked_tools = set(blocked_tools or {"mcp_kernel_reboot", "mcp_destroy_volume"})
        self.default_timeout = default_timeout
        self.audit_trail = audit_trail
        self._pre_hooks: List[Callable[[str, Dict[str, Any], Dict[str, Any]], Tuple[bool, str]]] = []
        self._post_hooks: List[Callable[[str, Any, Dict[str, Any], Dict[str, Any]], Tuple[bool, str, Any]]] = []
        self._audit_records: List[Dict[str, Any]] = []

    def register_pre_hook(
        self,
        hook_fn: Callable[[str, Dict[str, Any], Dict[str, Any]], Tuple[bool, str]],
    ) -> None:
        """Registers a dynamic pre-execution inspection hook."""
        self._pre_hooks.append(hook_fn)

    def register_post_hook(
        self,
        hook_fn: Callable[[str, Any, Dict[str, Any], Dict[str, Any]], Tuple[bool, str, Any]],
    ) -> None:
        """Registers a dynamic post-execution result validation hook."""
        self._post_hooks.append(hook_fn)

    def _log_audit(self, outcome: HookExecutionOutcome, args: Dict[str, Any]) -> None:
        record = outcome.to_dict()
        record["arguments"] = args
        self._audit_records.append(record)

        if self.audit_trail:
            try:
                if hasattr(self.audit_trail, "log"):
                    self.audit_trail.log(
                        tool_name=outcome.tool_name,
                        args=args,
                        result=outcome.result if outcome.allowed else f"BLOCKED: {outcome.message}",
                        status=outcome.decision.value,
                        why=outcome.message,
                    )
            except Exception as e:
                logger.warning(f"Failed to record to external audit trail: {e}")

    async def intercept_and_sandbox(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        isolate_sandbox: bool = True,
        timeout: Optional[float] = None,
    ) -> HookExecutionOutcome:
        """
        Intercepts tool call, evaluates pre-hooks, executes in sandboxed wrapper,
        and evaluates post-hooks on the result.
        """
        arguments = arguments or {}
        context = context or {}
        timeout_sec = timeout if timeout is not None else self.default_timeout
        start_time = time.perf_counter()

        # 1. Check blacklist
        if tool_name.lower() in self.blocked_tools:
            duration = (time.perf_counter() - start_time) * 1000.0
            outcome = HookExecutionOutcome(
                success=False,
                allowed=False,
                result=None,
                message=f"Blocked: Tool '{tool_name}' is blacklisted by dynamic verification policy.",
                tool_name=tool_name,
                decision=HookDecision.BLOCK,
                execution_time_ms=duration,
            )
            self._log_audit(outcome, arguments)
            return outcome

        # 2. Evaluate pre-execution dynamic hooks
        for pre_hook in self._pre_hooks:
            try:
                passed, reason = pre_hook(tool_name, arguments, context)
                if not passed:
                    duration = (time.perf_counter() - start_time) * 1000.0
                    outcome = HookExecutionOutcome(
                        success=False,
                        allowed=False,
                        result=None,
                        message=f"Pre-hook verification failed: {reason}",
                        tool_name=tool_name,
                        decision=HookDecision.BLOCK,
                        execution_time_ms=duration,
                    )
                    self._log_audit(outcome, arguments)
                    return outcome
            except Exception as e:
                logger.error(f"Pre-hook error for tool '{tool_name}': {e}")
                duration = (time.perf_counter() - start_time) * 1000.0
                outcome = HookExecutionOutcome(
                    success=False,
                    allowed=False,
                    result=None,
                    message=f"Pre-hook execution error: {e}",
                    tool_name=tool_name,
                    decision=HookDecision.BLOCK,
                    execution_time_ms=duration,
                )
                self._log_audit(outcome, arguments)
                return outcome

        # 3. Execute tool within sandboxed boundary & timeout
        try:
            if inspect.iscoroutinefunction(tool_func):
                coro = tool_func(**arguments)
            else:
                coro = asyncio.to_thread(tool_func, **arguments)

            raw_result = await asyncio.wait_for(coro, timeout=timeout_sec)
        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start_time) * 1000.0
            outcome = HookExecutionOutcome(
                success=False,
                allowed=True,
                result=None,
                message=f"Sandbox execution timed out after {timeout_sec}s.",
                tool_name=tool_name,
                decision=HookDecision.SANDBOX_ISOLATED,
                sandboxed=isolate_sandbox,
                execution_time_ms=duration,
            )
            self._log_audit(outcome, arguments)
            return outcome
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            outcome = HookExecutionOutcome(
                success=False,
                allowed=True,
                result=None,
                message=f"Tool runtime exception: {e}",
                tool_name=tool_name,
                decision=HookDecision.SANDBOX_ISOLATED,
                sandboxed=isolate_sandbox,
                execution_time_ms=duration,
            )
            self._log_audit(outcome, arguments)
            return outcome

        # 4. Evaluate post-execution dynamic hooks
        processed_result = raw_result
        for post_hook in self._post_hooks:
            try:
                passed, reason, sanitized_out = post_hook(tool_name, processed_result, arguments, context)
                if not passed:
                    duration = (time.perf_counter() - start_time) * 1000.0
                    outcome = HookExecutionOutcome(
                        success=False,
                        allowed=False,
                        result=None,
                        message=f"Post-hook validation denied: {reason}",
                        tool_name=tool_name,
                        decision=HookDecision.BLOCK,
                        sandboxed=isolate_sandbox,
                        execution_time_ms=duration,
                    )
                    self._log_audit(outcome, arguments)
                    return outcome
                processed_result = sanitized_out
            except Exception as e:
                logger.error(f"Post-hook error: {e}")
                duration = (time.perf_counter() - start_time) * 1000.0
                outcome = HookExecutionOutcome(
                    success=False,
                    allowed=False,
                    result=None,
                    message=f"Post-hook execution error: {e}",
                    tool_name=tool_name,
                    decision=HookDecision.BLOCK,
                    sandboxed=isolate_sandbox,
                    execution_time_ms=duration,
                )
                self._log_audit(outcome, arguments)
                return outcome

        duration = (time.perf_counter() - start_time) * 1000.0
        outcome = HookExecutionOutcome(
            success=True,
            allowed=True,
            result=processed_result,
            message="Tool verified and executed successfully in sandbox.",
            tool_name=tool_name,
            decision=HookDecision.ALLOW,
            sandboxed=isolate_sandbox,
            execution_time_ms=duration,
        )
        self._log_audit(outcome, arguments)
        return outcome

    def intercept_sync(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        isolate_sandbox: bool = True,
        timeout: Optional[float] = None,
    ) -> HookExecutionOutcome:
        """Synchronous wrapper for sandbox interception hook."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.intercept_and_sandbox(
                            tool_func=tool_func,
                            tool_name=tool_name,
                            arguments=arguments,
                            context=context,
                            isolate_sandbox=isolate_sandbox,
                            timeout=timeout,
                        )
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.intercept_and_sandbox(
                    tool_func=tool_func,
                    tool_name=tool_name,
                    arguments=arguments,
                    context=context,
                    isolate_sandbox=isolate_sandbox,
                    timeout=timeout,
                )
            )

    def hook_tool(self, tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator wrapping a tool function with dynamic sandbox hook verification."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if inspect.iscoroutinefunction(func):
                async def async_wrapper(**kwargs: Any) -> Any:
                    outcome = await self.intercept_and_sandbox(func, tool_name, kwargs)
                    if not outcome.allowed:
                        raise PermissionError(outcome.message)
                    if not outcome.success:
                        raise RuntimeError(outcome.message)
                    return outcome.result
                return async_wrapper
            else:
                def sync_wrapper(**kwargs: Any) -> Any:
                    outcome = self.intercept_sync(func, tool_name, kwargs)
                    if not outcome.allowed:
                        raise PermissionError(outcome.message)
                    if not outcome.success:
                        raise RuntimeError(outcome.message)
                    return outcome.result
                return sync_wrapper
        return decorator

    def get_audit_records(self) -> List[Dict[str, Any]]:
        return list(self._audit_records)
