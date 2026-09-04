import asyncio
import logging
from typing import Any, Callable, Dict, Tuple

from magda_agent.safety.realtime_interceptor import RealtimeGuardrailInterceptor


class GuardrailFallbackExecutor:
    """
    Executor that attempts a fallback action if the RealtimeGuardrailInterceptor blocks the primary action.
    """

    async def execute_with_fallback(
        self,
        interceptor: RealtimeGuardrailInterceptor,
        tool_func: Callable[..., Any],
        tool_name: str,
        kwargs: Dict[str, Any],
        fallback_func: Callable[..., Any],
        fallback_kwargs: Dict[str, Any],
    ) -> Tuple[bool, Any]:
        """
        Executes a tool function using the provided interceptor. If the execution is blocked or fails,
        it catches the failure, logs a warning, and executes the fallback function.

        Args:
            interceptor (RealtimeGuardrailInterceptor): The interceptor to use for the primary tool call.
            tool_func (Callable[..., Any]): The primary tool function to execute.
            tool_name (str): The name of the primary tool.
            kwargs (Dict[str, Any]): The arguments for the primary tool.
            fallback_func (Callable[..., Any]): The fallback function to execute if the primary fails.
            fallback_kwargs (Dict[str, Any]): The arguments for the fallback function.

        Returns:
            Tuple[bool, Any]: A tuple containing a boolean indicating success and the result of the execution.
        """
        success, result = await interceptor.intercept_and_execute(tool_func, tool_name, kwargs)

        if not success:
            logging.warning(
                f"GuardrailFallbackExecutor: Primary tool '{tool_name}' blocked or failed. "
                f"Reason: {result}. Attempting fallback."
            )

            try:
                if asyncio.iscoroutinefunction(fallback_func):
                    fallback_result = await fallback_func(**fallback_kwargs)
                else:
                    # Run synchronous fallback in a thread
                    fallback_result = await asyncio.to_thread(fallback_func, **fallback_kwargs)
                return True, fallback_result
            except Exception as e:
                logging.error(f"GuardrailFallbackExecutor: Fallback execution also failed: {e}")
                return False, f"Both primary tool and fallback failed. Fallback error: {e}"

        return True, result
