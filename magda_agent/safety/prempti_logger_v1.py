from typing import Any, Callable, Dict, Optional, TypeVar, cast
import inspect
import time
from functools import wraps
from magda_agent.safety.audit_trail import AuditTrail

F = TypeVar('F', bound=Callable[..., Any])

class PremptiLoggerV1:
    """
    A logger that intercepts tool calls and records pre-execution metadata
    into the AuditTrail. Inspired by Prempti (Falco).
    """

    def __init__(self, audit_trail: Optional[AuditTrail] = None) -> None:
        """
        Initializes the PremptiLoggerV1.

        Args:
            audit_trail: The AuditTrail instance to use for logging.
        """
        self.audit_trail = audit_trail or AuditTrail()

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

    def intercept(self, tool_name: Optional[str] = None, why: str = "pre-execution intercept") -> Callable[[F], F]:
        """
        A decorator that intercepts a tool call and logs its execution metadata before the call.

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

                    # Pre-execution log
                    self.audit_trail.log_call(
                        tool_name=name_to_use,
                        kwargs=all_args,
                        why=why,
                        result="PENDING",
                        duration=0.0
                    )

                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        duration = time.time() - start_time
                        self.audit_trail.log_call(name_to_use, all_args, f"{why} (completed)", result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        self.audit_trail.log_call(name_to_use, all_args, f"{why} (failed)", str(e), duration)
                        raise
                return cast(F, async_wrapper)
            else:
                @wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    all_args = self._extract_args(func, args, kwargs)

                    # Pre-execution log
                    self.audit_trail.log_call(
                        tool_name=name_to_use,
                        kwargs=all_args,
                        why=why,
                        result="PENDING",
                        duration=0.0
                    )

                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time
                        self.audit_trail.log_call(name_to_use, all_args, f"{why} (completed)", result, duration)
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        self.audit_trail.log_call(name_to_use, all_args, f"{why} (failed)", str(e), duration)
                        raise
                return cast(F, sync_wrapper)
        return decorator
