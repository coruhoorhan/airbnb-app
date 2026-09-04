"""
MCP Action Tool Rate Limiting V1.

Inspired by MCP action tools standardization trends: Implements a strict,
configurable token-bucket rate limiting guardrail for MCP action tools to
prevent runaway side-effects, API exhaustion, and denial-of-service against
external services.
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

logger = logging.getLogger(__name__)


class MCPRateLimitExceededError(Exception):
    """Raised when an MCP action tool call exceeds allowed rate limits."""

    def __init__(self, tool_name: str, retry_after: float, reason: str):
        super().__init__(
            f"Rate limit exceeded for tool '{tool_name}'. Retry after {retry_after:.2f}s: {reason}"
        )
        self.tool_name = tool_name
        self.retry_after = retry_after
        self.reason = reason


@dataclass
class TokenBucket:
    """Standard token bucket implementation for rate limiting."""

    capacity: float
    refill_rate: float  # tokens added per second
    current_tokens: float = field(init=False)
    last_refill_timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        self.current_tokens = float(self.capacity)

    def refill(self, current_time: Optional[float] = None) -> None:
        """Refill bucket based on elapsed time since last refill."""
        now = current_time if current_time is not None else time.time()
        elapsed = max(0.0, now - self.last_refill_timestamp)
        if elapsed > 0:
            added_tokens = elapsed * self.refill_rate
            self.current_tokens = min(self.capacity, self.current_tokens + added_tokens)
            self.last_refill_timestamp = now

    def can_consume(self, tokens: float = 1.0, current_time: Optional[float] = None) -> bool:
        """Check if requested tokens can be consumed without mutating bucket state."""
        self.refill(current_time)
        return self.current_tokens >= tokens

    def consume(self, tokens: float = 1.0, current_time: Optional[float] = None) -> bool:
        """Attempt to consume tokens from the bucket."""
        self.refill(current_time)
        if self.current_tokens >= tokens:
            self.current_tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: float = 1.0, current_time: Optional[float] = None) -> float:
        """Calculate seconds until specified tokens are available in bucket."""
        self.refill(current_time)
        if self.current_tokens >= tokens:
            return 0.0
        needed = tokens - self.current_tokens
        if self.refill_rate <= 0:
            return float("inf")
        return needed / self.refill_rate


@dataclass
class RateLimitRule:
    """Configuration rule for a rate limit boundary."""

    rate_per_second: float = 10.0
    burst_capacity: float = 10.0
    cost_per_call: float = 1.0
    identifier: str = "global"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPRateLimitDecision:
    """Decision outcome of checking a tool request against rate limiting policies."""

    allowed: bool
    tool_name: str
    current_tokens_remaining: float
    cost_requested: float
    retry_after_seconds: float = 0.0
    reason: Optional[str] = None
    rule_identifier: str = "global"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RateLimitedExecutionResult:
    """Result of executing an MCP action tool under rate limit protection."""

    success: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    blocked_by_rate_limit: bool = False
    decision: Optional[MCPRateLimitDecision] = None
    execution_time_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: f"rl_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "blocked_by_rate_limit": self.blocked_by_rate_limit,
            "execution_time_ms": self.execution_time_ms,
            "audit_id": self.audit_id,
        }


class MCPActionToolRateLimiterV1:
    """
    MCP Action Tool Rate Limiter V1.

    Enforces token-bucket rate limits at Global, Server Prefix, and Tool-specific scopes.
    Blocks runaway executions and side-effects.
    """

    def __init__(
        self,
        default_rate_per_second: float = 10.0,
        default_burst_capacity: float = 10.0,
    ):
        self.default_rate = default_rate_per_second
        self.default_burst = default_burst_capacity

        self.global_bucket = TokenBucket(
            capacity=self.default_burst,
            refill_rate=self.default_rate,
        )

        self._tool_buckets: Dict[str, TokenBucket] = {}
        self._tool_costs: Dict[str, float] = {}
        self._server_buckets: Dict[str, TokenBucket] = {}
        self._audit_trail: List[RateLimitedExecutionResult] = []

    def configure_tool_limit(
        self,
        tool_name: str,
        rate_per_second: float,
        burst_capacity: float,
        cost_per_call: float = 1.0,
    ) -> None:
        """Set custom rate limit and cost for a specific tool."""
        self._tool_buckets[tool_name] = TokenBucket(
            capacity=burst_capacity,
            refill_rate=rate_per_second,
        )
        self._tool_costs[tool_name] = max(0.1, cost_per_call)
        logger.info(f"Configured rate limit for tool '{tool_name}': {rate_per_second}/s, burst={burst_capacity}")

    def configure_server_limit(
        self,
        server_prefix: str,
        rate_per_second: float,
        burst_capacity: float,
    ) -> None:
        """Set custom rate limit for an entire MCP server prefix."""
        self._server_buckets[server_prefix] = TokenBucket(
            capacity=burst_capacity,
            refill_rate=rate_per_second,
        )
        logger.info(f"Configured rate limit for server '{server_prefix}': {rate_per_second}/s, burst={burst_capacity}")

    def check_rate_limit(
        self,
        tool_name: str,
        server_prefix: Optional[str] = None,
        cost: Optional[float] = None,
        consume_if_allowed: bool = True,
    ) -> MCPRateLimitDecision:
        """
        Evaluate rate limit availability across Tool, Server, and Global buckets.
        If consume_if_allowed is True and all checks pass, consumes the tokens.
        """
        required_cost = cost if cost is not None else self._tool_costs.get(tool_name, 1.0)
        now = time.time()

        # 1. Tool-specific limit check
        if tool_name in self._tool_buckets:
            bucket = self._tool_buckets[tool_name]
            bucket.refill(now)
            if not bucket.can_consume(required_cost, now):
                retry = bucket.time_until_available(required_cost, now)
                return MCPRateLimitDecision(
                    allowed=False,
                    tool_name=tool_name,
                    current_tokens_remaining=bucket.current_tokens,
                    cost_requested=required_cost,
                    retry_after_seconds=retry,
                    reason=f"Tool-level rate limit exceeded for '{tool_name}'. Available: {bucket.current_tokens:.2f}, Required: {required_cost}",
                    rule_identifier=f"tool:{tool_name}",
                )

        # 2. Server-level limit check
        prefix = server_prefix
        if not prefix and "__" in tool_name:
            prefix = tool_name.split("__", 1)[0]

        if prefix and prefix in self._server_buckets:
            s_bucket = self._server_buckets[prefix]
            s_bucket.refill(now)
            if not s_bucket.can_consume(required_cost, now):
                retry = s_bucket.time_until_available(required_cost, now)
                return MCPRateLimitDecision(
                    allowed=False,
                    tool_name=tool_name,
                    current_tokens_remaining=s_bucket.current_tokens,
                    cost_requested=required_cost,
                    retry_after_seconds=retry,
                    reason=f"Server-level rate limit exceeded for prefix '{prefix}'. Available: {s_bucket.current_tokens:.2f}, Required: {required_cost}",
                    rule_identifier=f"server:{prefix}",
                )

        # 3. Global limit check
        self.global_bucket.refill(now)
        if not self.global_bucket.can_consume(required_cost, now):
            retry = self.global_bucket.time_until_available(required_cost, now)
            return MCPRateLimitDecision(
                allowed=False,
                tool_name=tool_name,
                current_tokens_remaining=self.global_bucket.current_tokens,
                cost_requested=required_cost,
                retry_after_seconds=retry,
                reason=f"Global MCP rate limit exceeded. Available: {self.global_bucket.current_tokens:.2f}, Required: {required_cost}",
                rule_identifier="global",
            )

        # All passed: consume from all applicable buckets if requested
        if consume_if_allowed:
            if tool_name in self._tool_buckets:
                self._tool_buckets[tool_name].consume(required_cost, now)
            if prefix and prefix in self._server_buckets:
                self._server_buckets[prefix].consume(required_cost, now)
            self.global_bucket.consume(required_cost, now)

        tokens_left = (
            self._tool_buckets[tool_name].current_tokens
            if tool_name in self._tool_buckets
            else self.global_bucket.current_tokens
        )

        return MCPRateLimitDecision(
            allowed=True,
            tool_name=tool_name,
            current_tokens_remaining=tokens_left,
            cost_requested=required_cost,
            retry_after_seconds=0.0,
            reason="Rate limit within acceptable threshold.",
            rule_identifier="allowed",
        )

    def execute_with_rate_limit(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        server_prefix: Optional[str] = None,
        cost: Optional[float] = None,
    ) -> RateLimitedExecutionResult:
        """Synchronously execute tool protected by rate limits."""
        start_t = time.perf_counter()
        decision = self.check_rate_limit(tool_name, server_prefix=server_prefix, cost=cost)

        if not decision.allowed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"MCP Rate Limit Exceeded: {decision.reason} (retry after {decision.retry_after_seconds:.2f}s)"
            logger.warning(err_msg)
            res = RateLimitedExecutionResult(
                success=False,
                tool_name=tool_name,
                error=err_msg,
                blocked_by_rate_limit=True,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        try:
            raw_out = tool_func(**arguments)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = RateLimitedExecutionResult(
                success=True,
                tool_name=tool_name,
                result=raw_out,
                blocked_by_rate_limit=False,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = RateLimitedExecutionResult(
                success=False,
                tool_name=tool_name,
                error=str(ex),
                blocked_by_rate_limit=False,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    async def execute_with_rate_limit_async(
        self,
        tool_name: str,
        tool_func: Callable[..., Any],
        arguments: Dict[str, Any],
        server_prefix: Optional[str] = None,
        cost: Optional[float] = None,
    ) -> RateLimitedExecutionResult:
        """Asynchronously execute tool protected by rate limits."""
        start_t = time.perf_counter()
        decision = self.check_rate_limit(tool_name, server_prefix=server_prefix, cost=cost)

        if not decision.allowed:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"MCP Rate Limit Exceeded: {decision.reason} (retry after {decision.retry_after_seconds:.2f}s)"
            logger.warning(err_msg)
            res = RateLimitedExecutionResult(
                success=False,
                tool_name=tool_name,
                error=err_msg,
                blocked_by_rate_limit=True,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_out = await tool_func(**arguments)
            else:
                raw_out = tool_func(**arguments)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = RateLimitedExecutionResult(
                success=True,
                tool_name=tool_name,
                result=raw_out,
                blocked_by_rate_limit=False,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            res = RateLimitedExecutionResult(
                success=False,
                tool_name=tool_name,
                error=str(ex),
                blocked_by_rate_limit=False,
                decision=decision,
                execution_time_ms=elapsed,
            )
            self._audit_trail.append(res)
            return res

    def reset_limits(self, tool_name: Optional[str] = None) -> None:
        """Reset tokens in buckets."""
        if tool_name:
            if tool_name in self._tool_buckets:
                self._tool_buckets[tool_name].current_tokens = self._tool_buckets[tool_name].capacity
        else:
            self.global_bucket.current_tokens = self.global_bucket.capacity
            for b in self._tool_buckets.values():
                b.current_tokens = b.capacity
            for s in self._server_buckets.values():
                s.current_tokens = s.capacity

    def get_audit_trail(self) -> List[RateLimitedExecutionResult]:
        """Retrieve audit history."""
        return list(self._audit_trail)

    def clear_audit_trail(self) -> None:
        """Clear audit history."""
        self._audit_trail.clear()
