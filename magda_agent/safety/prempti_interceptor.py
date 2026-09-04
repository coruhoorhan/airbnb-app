import time
import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast
from magda_agent.safety.audit_trail import AuditTrail
from magda_agent.safety.taint import is_tainted

F = TypeVar('F', bound=Callable[..., Any])

class PremptiInterceptor:
    """
    An interceptor that wraps tool executions to trace all tool calls globally,
    logging tainted boundaries into the AuditTrail.
    Inspired by Prempti/Falco trend.
    """

    def __init__(self, audit_trail: AuditTrail) -> None:
        """
        Initializes the PremptiInterceptor.

        Args:
            audit_trail: The AuditTrail instance to use for logging.
        """
        self.audit_trail = audit_trail

    def _extract_args(self, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Dict[str, Any]:
        """Extracts all arguments into a dictionary mapping names to values."""
        try:
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)
        except Exception:
            # Fallback if signature binding fails
            extracted: Dict[str, Any] = {}
            for i, v in enumerate(args):
                extracted[f"arg_{i}"] = v
            extracted.update(kwargs)
            return extracted

    def intercept(self, tool_name: Optional[str] = None, why: str = "intercepted call") -> Callable[[F], F]:
        """
        A decorator that intercepts a tool call and logs its execution details,
        checking for tainted data boundaries.

        Args:
            tool_name: The name of the tool. If not provided, func.__name__ is used.
            why: The reason for the call.
        """
        def decorator(func: F) -> F:
            name_to_use = tool_name if tool_name else func.__name__

            if inspect.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    all_args = self._extract_args(func, args, kwargs)

                    # Check for taint in arguments
                    has_taint = any(is_tainted(v) for v in all_args.values())

                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)

                        # Check result taint
                        if is_tainted(result):
                            has_taint = True

                        duration = time.time() - start_time

                        # Add taint boundary metadata
                        log_args = dict(all_args)
                        log_args["_tainted_boundary_crossover"] = has_taint

                        self.audit_trail.log_call(name_to_use, log_args, why, result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        log_args = dict(all_args)
                        log_args["_tainted_boundary_crossover"] = has_taint
                        self.audit_trail.log_call(name_to_use, log_args, why, str(e), duration)
                        raise
                return cast(F, async_wrapper)
            else:
                @wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    all_args = self._extract_args(func, args, kwargs)

                    # Check for taint in arguments
                    has_taint = any(is_tainted(v) for v in all_args.values())

                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)

                        # Check result taint
                        if is_tainted(result):
                            has_taint = True

                        duration = time.time() - start_time

                        log_args = dict(all_args)
                        log_args["_tainted_boundary_crossover"] = has_taint

                        self.audit_trail.log_call(name_to_use, log_args, why, result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        log_args = dict(all_args)
                        log_args["_tainted_boundary_crossover"] = has_taint
                        self.audit_trail.log_call(name_to_use, log_args, why, str(e), duration)
                        raise
                return cast(F, sync_wrapper)
        return decorator
