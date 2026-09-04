import asyncio
import time
from enum import Enum
from typing import Callable, Any, TypeVar, Awaitable

T = TypeVar('T')

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    """Exception raised when the circuit breaker is OPEN."""
    pass

class A2ACircuitBreaker:
    """
    A circuit breaker for A2A delegation to prevent continuous failures to unresponsive peer agents.
    """
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """
        Executes the given async function subject to circuit breaker rules.
        """
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN. Peer is unresponsive.")

        try:
            result = await func(*args, **kwargs)
            # On success, reset the breaker
            self.reset()
            return result
        except Exception as e:
            if isinstance(e, CircuitBreakerOpenException):
                raise

            self.record_failure()
            raise

    def record_failure(self) -> None:
        """Records a failure and potentially transitions state."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = time.time()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_failure_time = time.time()

    def reset(self) -> None:
        """Resets the circuit breaker to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
