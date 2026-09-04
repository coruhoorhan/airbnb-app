import asyncio
import logging
from typing import Any, Callable, Dict, List, Tuple


class UnauthorizedActionError(Exception):
    """Exception raised when an action is blocked by the governance layer policy rules."""
    pass


# A policy rule is a callable that takes a tool_name and **kwargs, and returns
# a tuple of (bool, str) where bool is True if allowed, False if blocked,
# and str is an explanation.
PolicyRule = Callable[[str, Dict[str, Any]], Tuple[bool, str]]


class GovernanceLayer:
    """
    Runtime governance layer that intercepts all agent actions and applies strict policy rules
    before allowing external tool execution.
    """

    def __init__(self) -> None:
        """
        Initializes the GovernanceLayer.
        """
        self._rules: List[PolicyRule] = []

    def register_policy_rule(self, rule: PolicyRule) -> None:
        """
        Registers a new policy rule.

        Args:
            rule (PolicyRule): A callable that evaluates a tool call and returns (is_allowed, explanation).
        """
        self._rules.append(rule)

    def evaluate_action(self, tool_name: str, **kwargs: Any) -> Tuple[bool, str]:
        """
        Evaluates an action against all registered policy rules.

        Args:
            tool_name (str): Name of the tool being called.
            kwargs (Any): Arguments passed to the tool.

        Returns:
            Tuple[bool, str]: (Success, Explanation). True if all rules allow the action.
        """
        for rule in self._rules:
            is_allowed, explanation = rule(tool_name, kwargs)
            if not is_allowed:
                logging.warning(f"GovernanceLayer: Action '{tool_name}' blocked. Reason: {explanation}")
                return False, explanation
        return True, ""

    async def intercept_tool_call(
        self,
        tool_func: Callable[..., Any],
        tool_name: str,
        **kwargs: Any
    ) -> Any:
        """
        Intercepts a tool call, evaluates it against policies, and executes it if allowed.

        Args:
            tool_func (Callable[..., Any]): The synchronous or asynchronous function representing the tool call.
            tool_name (str): Name of the tool.
            kwargs (Any): Arguments passed to the tool.

        Returns:
            Any: The result of the tool execution.

        Raises:
            UnauthorizedActionError: If the action is blocked by any policy rule.
        """
        is_allowed, explanation = self.evaluate_action(tool_name, **kwargs)
        if not is_allowed:
            raise UnauthorizedActionError(f"Action '{tool_name}' blocked: {explanation}")

        # Execute the tool if allowed
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**kwargs)
        else:
            # Run synchronous tool in a thread to avoid blocking the asyncio event loop
            return await asyncio.to_thread(tool_func, **kwargs)
