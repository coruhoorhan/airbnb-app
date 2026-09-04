from typing import Dict, Callable, Any, Optional, Tuple, TYPE_CHECKING
import logging
import time
from magda_agent.skills.telemetry_export import SkillTelemetryTracker
from magda_agent.telemetry.canvas_skills_telemetry import CanvasSkillsTelemetry

if TYPE_CHECKING:
    from magda_agent.safety.policy import PolicyLayer

class SkillRegistry:
    """
    Registry to manage and trigger available skills for the AGI agent.
    """
    def __init__(self, policy_layer: Optional["PolicyLayer"] = None, canvas_telemetry: Optional["CanvasSkillsTelemetry"] = None):
        self.skills: Dict[str, Callable] = {}
        self.descriptions: Dict[str, str] = {}
        self.policy_layer = policy_layer
        self.telemetry_tracker = SkillTelemetryTracker()
        self.canvas_telemetry = canvas_telemetry or CanvasSkillsTelemetry()

        # Initialize AgentGuard if policy_layer is provided
        from magda_agent.safety.agent_guard import AgentGuard
        self.agent_guard = AgentGuard(policy_layer) if policy_layer else None

        from magda_agent.safety.runtime_governance import RuntimeGovernanceLayer
        self.runtime_governance = RuntimeGovernanceLayer(policy_layer) if policy_layer else None

        # Initialize RealtimeGuardrail
        from magda_agent.safety.guardrails import RealtimeGuardrail
        self.realtime_guardrail = RealtimeGuardrail(policy_layer) if policy_layer else None        # Initialize ACSMemoryPolicy and chain with existing policy layer

        # Initialize RealtimeGuardrailInterceptor
        from magda_agent.safety.realtime_interceptor import RealtimeGuardrailInterceptor
        from magda_agent.safety.mcp_enforcer_v7 import MCPActionEnforcer
        self.realtime_interceptor = RealtimeGuardrailInterceptor(policy_layer) if policy_layer else None
        self.mcp_enforcer = MCPActionEnforcer()

        from magda_agent.safety.governance_layer import GovernanceLayer
        self.governance_layer = GovernanceLayer()

        from magda_agent.safety.acs_memory import ACSMemoryPolicy
        self.acs_memory_policy = ACSMemoryPolicy()

        # Initialize ACSGuard
        from magda_agent.safety.acs_guard_v2 import ACSGuardV2
        self.acs_guard = ACSGuardV2(policy_layer=policy_layer)


        # Initialize ACSMemoryPolicy
        from magda_agent.safety.acs_memory import ACSMemoryPolicy
        self.acs_memory_policy = ACSMemoryPolicy()




    def register_skill(self, name: str, func: Callable, description: str):
        self.skills[name] = func
        self.descriptions[name] = description
        logging.info(f"Skill registered: {name}")

    def has_skill(self, name: str) -> bool:
        """
        Checks whether a skill with the given name is registered.

        Args:
            name (str): The name of the skill to check.

        Returns:
            bool: True if the skill exists, False otherwise.
        """
        return name in self.skills

    def execute_skill(self, name: str, **kwargs) -> Any:
        if name not in self.skills:
            return f"Error: Skill '{name}' not found."

        # Emit skill start event asynchronously via a new event loop if needed, or by dispatching it
        # Since execute_skill might be called synchronously, we will use a fire-and-forget approach
        def _dispatch_telemetry(coro):
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(coro)
            except RuntimeError:
                # Fallback to run a single task without replacing the loop,
                # though usually if no loop is running we can create one
                try:
                    new_loop = asyncio.new_event_loop()
                    new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

        if self.canvas_telemetry:
            _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_start(name, kwargs))

        try:
            if hasattr(self, 'mcp_enforcer') and self.mcp_enforcer and self.policy_layer:
                self.mcp_enforcer.enforce(name, kwargs, self.policy_layer)
            # 1. Prepare workflow data for ACS Checkpoints
            workflow_data = {
                "action": name,
                "tool": name,
                "current_state": "idle", # Simplified state handling for tools
                "next_state": "executing",
                "kwargs": kwargs
            }

            # 2. Intercept before execution
            if hasattr(self, 'acs_guard') and self.acs_guard:
                self.acs_guard.intercept_action(workflow_data)

            # 3. Execute with appropriate guard
            import time
            import asyncio
            start_time = time.time()
            try:
                if getattr(self, 'realtime_interceptor', None) is not None:
                    # We can't use asyncio.run if there is a running event loop, and run_until_complete
                    # cannot be called from a running event loop either.
                    # We will invoke a synchronous version or use a separate thread
                    import threading

                    def run_async_in_thread(coro: Any) -> Tuple[bool, Any]:
                        """Runs an async coroutine in a separate thread and returns the result."""
                        res = []
                        def _thread_target() -> None:
                            try:
                                res.append(asyncio.run(coro))
                            except Exception as e:
                                res.append((False, f"Thread execution error: {e}"))
                        t = threading.Thread(target=_thread_target)
                        t.start()
                        t.join()
                        return res[0] if res else (False, "Thread execution failed")


                    async def fallback_action(**kwargs: Any) -> str:
                        """
                        Provides a safe fallback action when the primary skill execution is blocked by the Realtime Guardrail.

                        Args:
                            **kwargs (Any): The arguments originally intended for the primary skill.

                        Returns:
                            str: A safe fallback message.
                        """
                        return f"Action '{name}' blocked. Proceeding cautiously."

                    from magda_agent.safety.guardrail_fallback import GuardrailFallbackExecutor
                    executor = GuardrailFallbackExecutor()
                    success, result = run_async_in_thread(
                        executor.execute_with_fallback(
                            self.realtime_interceptor,
                            self.skills[name],
                            name,
                            kwargs,
                            fallback_action,
                            kwargs
                        )
                    )
                elif self.realtime_guardrail is not None:
                    result = self.realtime_guardrail.execute_with_guardrails(self.skills[name], name, **kwargs)
                elif self.runtime_governance is not None:
                    result = self.runtime_governance.execute_tool(self.skills[name], name, **kwargs)
                elif self.agent_guard is not None:
                    result = self.agent_guard.execute_tool(self.skills[name], name, **kwargs)
                else:
                    result = self.skills[name](**kwargs)
                duration = time.time() - start_time
            except Exception as e:
                duration = time.time() - start_time
                if hasattr(self, 'acs_guard') and self.acs_guard:
                    self.acs_guard.audit_logger.log_call(
                        tool_name=name,
                        kwargs=kwargs,
                        why=f"Execution error: {e}",
                        result="error",
                        duration=duration
                    )
                raise

            import inspect
            if inspect.isawaitable(result):
                async def async_audit_wrapper(coro):
                    try:
                        actual_result = await coro
                        duration_async = time.time() - start_time
                        if hasattr(self, 'acs_guard') and self.acs_guard:
                            workflow_data["output"] = actual_result
                            passed, reason = self.acs_guard.checkpoint_5_output_sanitization(workflow_data)
                            if not passed:
                                self.acs_guard.audit_logger.log_call(
                                    tool_name=name,
                                    kwargs=kwargs,
                                    why=f"Checkpoint 5 Failed: {reason}",
                                    result="blocked",
                                    duration=duration_async
                                )
                                from magda_agent.safety.acs_guard_v2 import SecurityViolationError
                                if self.canvas_telemetry:
                                    _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_fail(name, f"Action blocked by ACS checkpoint 5: {reason}", duration_async * 1000))
                                raise SecurityViolationError(f"Action blocked by ACS checkpoint 5: {reason}")
                            self.acs_guard.audit_logger.log_call(
                                tool_name=name,
                                kwargs=kwargs,
                                why="Execution successful and sanitized.",
                                result=actual_result,
                                duration=duration_async
                            )
                        if self.canvas_telemetry:
                            _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_success(name, actual_result, duration_async * 1000))
                        return actual_result
                    except Exception as ea:
                        duration_async = time.time() - start_time
                        if hasattr(self, 'acs_guard') and self.acs_guard:
                            self.acs_guard.audit_logger.log_call(
                                tool_name=name,
                                kwargs=kwargs,
                                why=f"Execution error: {ea}",
                                result="error",
                                duration=duration_async
                            )
                        logging.error(f"Error executing skill {name}: {ea}")
                        if self.canvas_telemetry:
                            _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_fail(name, str(ea), duration_async * 1000))
                        raise
                return async_audit_wrapper(result)

            # 4. Checkpoint 5 output sanitization
            workflow_data["output"] = result
            if hasattr(self, 'acs_guard') and self.acs_guard:
                # Need to manually call it or re-intercept
                passed, reason = self.acs_guard.checkpoint_5_output_sanitization(workflow_data)
                if not passed:
                    self.acs_guard.audit_logger.log_call(
                        tool_name=name,
                        kwargs=kwargs,
                        why=f"Checkpoint 5 Failed: {reason}",
                        result="blocked",
                        duration=duration
                    )
                    from magda_agent.safety.acs_guard_v2 import SecurityViolationError
                    if self.canvas_telemetry:
                        _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_fail(name, f"Action blocked by ACS checkpoint 5: {reason}", duration * 1000))
                    raise SecurityViolationError(f"Action blocked by ACS checkpoint 5: {reason}")

                # Successful execution audit
                self.acs_guard.audit_logger.log_call(
                    tool_name=name,
                    kwargs=kwargs,
                    why="Execution successful and sanitized.",
                    result=result,
                    duration=duration
                )

            self.telemetry_tracker.record_usage(name, success=True, execution_time_ms=duration * 1000)
            if self.canvas_telemetry:
                _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_success(name, result, duration * 1000))

            return result
        except Exception as e:
            try:
                exec_time = duration * 1000
            except NameError:
                exec_time = 0.0

            self.telemetry_tracker.record_usage(name, success=False, execution_time_ms=exec_time)
            logging.error(f"Error executing skill {name}: {e}")
            if self.canvas_telemetry:
                _dispatch_telemetry(self.canvas_telemetry.broadcast_skill_fail(name, str(e), exec_time))
            return f"Error executing skill {name}: {e}"


    def get_skills_summary(self) -> str:
        summary = "Available Skills:\n"
        for name, desc in self.descriptions.items():
            summary += f"- {name}: {desc}\n"
        return summary
