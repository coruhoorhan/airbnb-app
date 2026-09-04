import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from magda_agent.safety.policy import PolicyLayer


class PolicyViolationError(Exception):
    """Exception raised by tools when a policy violation is detected mid-execution."""
    pass


class RealtimeGuardrailInterceptor:
    """
    Interceptor that triggers a safe fallback state when external API tool calls detect policy violations mid-execution.
    """

    def __init__(self, policy_layer: Optional[PolicyLayer] = None) -> None:
        """
        Initializes the RealtimeGuardrailInterceptor.

        Args:
            policy_layer (Optional[PolicyLayer]): The policy evaluator to verify safety before execution.
        """
        self.policy_layer = policy_layer or PolicyLayer()

    async def intercept_and_execute(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        kwargs: Dict[str, Any]
    ) -> Tuple[bool, Any]:
        """
        Executes the tool function with mid-execution guardrails. If a PolicyViolationError or generic execution
        error is detected, it intercepts the issue and returns a structured tuple containing False and a fallback prompt.

        Args:
            tool_func (Callable[..., Any]): The synchronous or asynchronous function representing the tool call.
            tool_name (str): Name of the tool.
            kwargs (Dict[str, Any]): Arguments passed to the tool.

        Returns:
            Tuple[bool, Any]: (Success, Result or Fallback prompt).
        """
        # 1. Pre-execution policy check
        allow, explanation = self.policy_layer.evaluate(tool_name, **kwargs)
        if not allow:
            logging.warning(f"RealtimeInterceptor: Pre-execution policy violation for '{tool_name}'.")
            fallback_prompt = (
                f"SAFETY ALERT: Pre-execution of tool '{tool_name}' with arguments {kwargs} "
                f"was blocked due to a policy violation: {explanation}. "
                f"Please analyze the violation, dynamically revise your execution plan, and try a "
                f"different approach."
            )
            return False, fallback_prompt

        # 2. Execute the tool and intercept exceptions
        try:
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**kwargs)
            else:
                # Run synchronous tool in a thread to avoid blocking the asyncio event loop
                result = await asyncio.to_thread(tool_func, **kwargs)
            return True, result
        except PolicyViolationError as e:
            logging.error(f"RealtimeInterceptor: Mid-execution policy violation detected for '{tool_name}'. Error: {e}")
            fallback_prompt = (
                f"MID-EXECUTION SAFETY ALERT: Tool '{tool_name}' detected a policy violation mid-execution: {str(e)}. "
                f"The action was aborted to maintain safety. Please handle this dynamically and adjust your plan."
            )
            return False, fallback_prompt
        except Exception as e:
            logging.error(f"RealtimeInterceptor: Execution failure for '{tool_name}'. Error: {e}")
            fallback_prompt = (
                f"EXECUTION FAILURE: Failed to execute tool '{tool_name}'. "
                f"Error: {str(e)}. "
                f"Please adjust your strategy, handle this error dynamically, and generate an alternative plan."
            )
            return False, fallback_prompt
