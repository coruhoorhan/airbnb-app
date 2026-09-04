"""
Hermes-inspired Dynamic Skill Optimizer V2.

Inspired by the Hermes Agent learning loop: Observes skill execution patterns,
tracks consecutive successful executions, and dynamically generates and registers
optimized, cached versions of skills to minimize latency and token expenditure.
"""

import asyncio
import inspect
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class SkillExecutionRecord:
    """Record representing a single execution of a skill."""

    skill_name: str
    input_args: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    success: bool = True
    latency_ms: float = 0.0
    token_usage: int = 0
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizedSkill:
    """Represents a dynamically optimized and cached version of a skill."""

    skill_name: str
    original_func: Optional[Callable[..., Any]] = None
    optimized_func: Optional[Callable[..., Any]] = None
    cache_strategy: str = "exact_match"
    consecutive_success_threshold: int = 3
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    miss_count: int = 0
    estimated_token_savings: int = 0
    estimated_latency_savings_ms: float = 0.0
    cache_store: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("original_func", None)
        d.pop("optimized_func", None)
        d.pop("cache_store", None)
        return d


class DynamicSkillOptimizerV2:
    """
    Dynamic Skill Optimizer V2.

    Monitors executions of registered skills. Once a skill reaches a configured
    number of consecutive successful executions, generates an optimized wrapper
    with intelligent caching, latency reduction, and token tracking.
    """

    def __init__(
        self,
        consecutive_success_threshold: int = 3,
        cache_strategy: str = "exact_match",
        cache_max_size: int = 1000,
        skill_registry: Optional[Any] = None,
    ):
        self.consecutive_success_threshold = max(1, consecutive_success_threshold)
        self.cache_strategy = cache_strategy
        self.cache_max_size = cache_max_size
        self.skill_registry = skill_registry

        self._history: Dict[str, List[SkillExecutionRecord]] = {}
        self._consecutive_successes: Dict[str, int] = {}
        self._optimized_skills: Dict[str, OptimizedSkill] = {}
        self._registered_original_funcs: Dict[str, Callable[..., Any]] = {}

    def register_original_skill(
        self,
        name: str,
        func: Callable[..., Any],
    ) -> None:
        """Register the baseline function for a given skill name."""
        self._registered_original_funcs[name] = func

    def record_execution(
        self,
        skill_name: str,
        input_args: Dict[str, Any],
        output: Any,
        success: bool = True,
        latency_ms: float = 0.0,
        token_usage: int = 0,
        error: Optional[str] = None,
    ) -> Optional[OptimizedSkill]:
        """
        Record a skill execution outcome.

        If consecutive successes reach threshold, generates and registers an optimized version.
        """
        record = SkillExecutionRecord(
            skill_name=skill_name,
            input_args=input_args,
            output=output,
            success=success,
            latency_ms=latency_ms,
            token_usage=token_usage,
            timestamp=time.time(),
            error=error,
        )

        if skill_name not in self._history:
            self._history[skill_name] = []
        self._history[skill_name].append(record)

        if success:
            self._consecutive_successes[skill_name] = (
                self._consecutive_successes.get(skill_name, 0) + 1
            )
        else:
            self._consecutive_successes[skill_name] = 0

        # Check threshold
        if (
            self._consecutive_successes[skill_name] >= self.consecutive_success_threshold
            and skill_name not in self._optimized_skills
        ):
            original_func = self._registered_original_funcs.get(skill_name)
            return self.optimize_skill(
                skill_name=skill_name,
                original_func=original_func,
                cache_strategy=self.cache_strategy,
            )

        return self._optimized_skills.get(skill_name)

    def _hash_arguments(self, kwargs: Dict[str, Any]) -> str:
        """Serialize kwargs to a deterministic key."""
        try:
            return json.dumps(kwargs, sort_keys=True, default=str)
        except Exception:
            return str(sorted(kwargs.items(), key=lambda x: str(x[0])))

    def optimize_skill(
        self,
        skill_name: str,
        original_func: Optional[Callable[..., Any]] = None,
        cache_strategy: Optional[str] = None,
    ) -> OptimizedSkill:
        """
        Generates and registers an optimized cached version of a skill.
        """
        strategy = cache_strategy or self.cache_strategy
        func = original_func or self._registered_original_funcs.get(skill_name)

        optimized = OptimizedSkill(
            skill_name=skill_name,
            original_func=func,
            cache_strategy=strategy,
            consecutive_success_threshold=self.consecutive_success_threshold,
            created_at=time.time(),
        )

        # Build optimized wrapper
        def optimized_sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = self._hash_arguments(kwargs)
            if key in optimized.cache_store:
                optimized.hit_count += 1
                # Estimate savings from average historical latency & tokens
                hist = self._history.get(skill_name, [])
                if hist:
                    avg_tokens = sum(r.token_usage for r in hist) / len(hist)
                    avg_latency = sum(r.latency_ms for r in hist) / len(hist)
                    optimized.estimated_token_savings += int(avg_tokens)
                    optimized.estimated_latency_savings_ms += avg_latency
                return optimized.cache_store[key]

            optimized.miss_count += 1
            start_t = time.perf_counter()
            if func is not None:
                result = func(*args, **kwargs)
            else:
                result = None
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if len(optimized.cache_store) < self.cache_max_size:
                optimized.cache_store[key] = result

            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=result,
                success=True,
                latency_ms=elapsed_ms,
            )
            return result

        async def optimized_async_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = self._hash_arguments(kwargs)
            if key in optimized.cache_store:
                optimized.hit_count += 1
                hist = self._history.get(skill_name, [])
                if hist:
                    avg_tokens = sum(r.token_usage for r in hist) / len(hist)
                    avg_latency = sum(r.latency_ms for r in hist) / len(hist)
                    optimized.estimated_token_savings += int(avg_tokens)
                    optimized.estimated_latency_savings_ms += avg_latency
                return optimized.cache_store[key]

            optimized.miss_count += 1
            start_t = time.perf_counter()
            if func is not None:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            else:
                result = None
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if len(optimized.cache_store) < self.cache_max_size:
                optimized.cache_store[key] = result

            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=result,
                success=True,
                latency_ms=elapsed_ms,
            )
            return result

        if func and inspect.iscoroutinefunction(func):
            optimized.optimized_func = optimized_async_wrapper
        else:
            optimized.optimized_func = optimized_sync_wrapper

        self._optimized_skills[skill_name] = optimized

        # If external skill registry is attached, register the optimized version
        if self.skill_registry:
            if hasattr(self.skill_registry, "register_skill"):
                try:
                    self.skill_registry.register_skill(
                        skill_name,
                        optimized.optimized_func,
                        f"Dynamic Hermes-optimized cached version of {skill_name}",
                    )
                except Exception as ex:
                    logger.warning(f"Could not register with skill_registry: {ex}")
            elif hasattr(self.skill_registry, "register"):
                try:
                    self.skill_registry.register(
                        name=skill_name,
                        func=optimized.optimized_func,
                        description=f"Dynamic Hermes-optimized cached version of {skill_name}",
                    )
                except Exception as ex:
                    logger.warning(f"Could not register with skill_registry: {ex}")

        logger.info(
            f"Skill '{skill_name}' successfully optimized after {self.consecutive_success_threshold} consecutive successes."
        )
        return optimized

    def execute_skill(
        self,
        skill_name: str,
        original_func: Optional[Callable[..., Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a skill using the optimized version if available, falling back to original."""
        if original_func and skill_name not in self._registered_original_funcs:
            self.register_original_skill(skill_name, original_func)

        optimized = self._optimized_skills.get(skill_name)
        if optimized and optimized.optimized_func:
            return optimized.optimized_func(*args, **kwargs)

        func = original_func or self._registered_original_funcs.get(skill_name)
        if func is None:
            raise ValueError(f"No execution target found for skill '{skill_name}'")

        start_t = time.perf_counter()
        try:
            res = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=res,
                success=True,
                latency_ms=elapsed,
            )
            return res
        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=None,
                success=False,
                latency_ms=elapsed,
                error=str(e),
            )
            raise

    async def execute_skill_async(
        self,
        skill_name: str,
        original_func: Optional[Callable[..., Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Async execution of a skill via optimized wrapper or original."""
        if original_func and skill_name not in self._registered_original_funcs:
            self.register_original_skill(skill_name, original_func)

        optimized = self._optimized_skills.get(skill_name)
        if optimized and optimized.optimized_func:
            if inspect.iscoroutinefunction(optimized.optimized_func):
                return await optimized.optimized_func(*args, **kwargs)
            return optimized.optimized_func(*args, **kwargs)

        func = original_func or self._registered_original_funcs.get(skill_name)
        if func is None:
            raise ValueError(f"No execution target found for skill '{skill_name}'")

        start_t = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(func):
                res = await func(*args, **kwargs)
            else:
                res = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_t) * 1000.0
            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=res,
                success=True,
                latency_ms=elapsed,
            )
            return res
        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            self.record_execution(
                skill_name=skill_name,
                input_args=kwargs,
                output=None,
                success=False,
                latency_ms=elapsed,
                error=str(e),
            )
            raise

    def is_optimized(self, skill_name: str) -> bool:
        """Check if a skill currently has an active optimized version."""
        return skill_name in self._optimized_skills

    def get_consecutive_successes(self, skill_name: str) -> int:
        """Get current consecutive success count for a skill."""
        return self._consecutive_successes.get(skill_name, 0)

    def get_optimized_skill(self, skill_name: str) -> Optional[OptimizedSkill]:
        """Get the OptimizedSkill data object if registered."""
        return self._optimized_skills.get(skill_name)

    def get_optimization_stats(self, skill_name: Optional[str] = None) -> Dict[str, Any]:
        """Get summary metrics on optimization savings and hits."""
        if skill_name:
            opt = self._optimized_skills.get(skill_name)
            if not opt:
                return {
                    "is_optimized": False,
                    "consecutive_successes": self.get_consecutive_successes(skill_name),
                }
            return {
                "is_optimized": True,
                "hit_count": opt.hit_count,
                "miss_count": opt.miss_count,
                "estimated_token_savings": opt.estimated_token_savings,
                "estimated_latency_savings_ms": opt.estimated_latency_savings_ms,
                "cache_size": len(opt.cache_store),
            }

        return {
            "total_optimized_skills": len(self._optimized_skills),
            "skills": {
                name: {
                    "hit_count": opt.hit_count,
                    "miss_count": opt.miss_count,
                    "estimated_token_savings": opt.estimated_token_savings,
                    "estimated_latency_savings_ms": opt.estimated_latency_savings_ms,
                    "cache_size": len(opt.cache_store),
                }
                for name, opt in self._optimized_skills.items()
            },
        }

    def clear_cache(self, skill_name: Optional[str] = None) -> None:
        """Clear cache store for one or all optimized skills."""
        if skill_name:
            if skill_name in self._optimized_skills:
                self._optimized_skills[skill_name].cache_store.clear()
        else:
            for opt in self._optimized_skills.values():
                opt.cache_store.clear()
