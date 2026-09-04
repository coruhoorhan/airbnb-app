"""MCP Tool Taint Tracking Sandbox v5."""
import inspect
import functools
from typing import Any, Callable, List, Optional
from magda_agent.security.mcp_kernel_taint import is_tainted, mark_tainted, PolicyViolationError

class TaintSandboxError(PolicyViolationError):
    """Raised when tainted data violates policy during MCP tool execution."""
    pass

def _check_taint_by_path(value: Any, path: List[str]) -> bool:
    """Helper to check if a nested dictionary path is tainted."""
    if not path:
        return is_tainted(value)

    current = value
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False
    return is_tainted(current)


def mcp_action_taint_sandbox(critical_params: Optional[List[str]] = None) -> Callable[..., Any]:
    """
    Decorator for MCP action tools to track taint and block unsafe calls.
    Supports dot-notation in critical_params to check nested dictionary fields.

    Args:
        critical_params: List of parameter names (or dot-paths) that must not receive tainted data.

    Returns:
        A decorator for taint tracking.
    """
    if critical_params is None:
        critical_params = []

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Map args and kwargs to parameter names
            sig: inspect.Signature = inspect.signature(func)
            bound_args: inspect.BoundArguments = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Block if any critical parameter receives tainted data
            for crit_param in critical_params:
                parts = crit_param.split(".")
                param_name = parts[0]
                if param_name in bound_args.arguments:
                    param_value = bound_args.arguments[param_name]
                    if _check_taint_by_path(param_value, parts[1:]):
                        raise TaintSandboxError(
                            f"Critical parameter '{crit_param}' in '{func.__name__}' received tainted data."
                        )

            # Execute the function
            result: Any = func(*args, **kwargs)

            # Outputs from external MCP action tools are inherently untrusted and thus tainted
            return mark_tainted(result)

        return wrapper
    return decorator


def advanced_mcp_taint_tracker() -> Callable[..., Any]:
    """
    Decorator for MCP action tools to track data flow of taint.
    If any input (arg or kwarg) is tainted, the output is also tainted.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if any arg is tainted
            args_tainted = any(is_tainted(arg) for arg in args)
            # Check if any kwarg is tainted
            kwargs_tainted = any(is_tainted(val) for val in kwargs.values())

            # Execute the function
            result: Any = func(*args, **kwargs)

            # If inputs were tainted, taint the output
            if args_tainted or kwargs_tainted:
                return mark_tainted(result)
            return result

        return wrapper
    return decorator
