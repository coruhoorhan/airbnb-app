import logging
from typing import Optional
from magda_agent.skills.registry import SkillRegistry

class SkillPrunerV2:
    """
    SkillPrunerV2 evaluates skill usage metrics from telemetry and unregisters
    skills that have high failure rates or zero usage over a significant time period.
    This helps keep the context window optimized.
    """

    def __init__(self, registry: SkillRegistry) -> None:
        """
        Initializes the SkillPrunerV2.

        Args:
            registry (SkillRegistry): The registry containing skills to prune.
        """
        self.logger = logging.getLogger(__name__)
        self.registry = registry

    def evaluate_and_prune(
        self,
        min_calls: int = 5,
        failure_threshold: float = 0.5,
        prune_zero_usage: bool = True
    ) -> None:
        """
        Evaluates current telemetry metrics and prunes underperforming skills
        from the SkillRegistry.

        Args:
            min_calls (int): The minimum number of calls a skill must have before
                             its failure rate is evaluated.
            failure_threshold (float): The maximum allowed failure rate. Skills with
                                       a failure rate above this threshold are pruned.
            prune_zero_usage (bool): Whether to prune skills that have zero calls.
        """
        if not hasattr(self.registry, 'telemetry_tracker'):
            self.logger.warning("SkillRegistry does not have a telemetry_tracker. Skipping pruning.")
            return

        tracker = self.registry.telemetry_tracker
        metrics = tracker.get_aggregated_metrics()

        min_success_rate = 1.0 - failure_threshold
        skills_to_remove = []

        for skill_name, data in metrics.items():
            if skill_name not in self.registry.skills:
                continue

            total_calls = data.get("total_calls", 0)
            success_rate = data.get("success_rate", 0.0)

            if total_calls == 0 and prune_zero_usage:
                self.logger.info(f"Pruning skill '{skill_name}' due to zero usage.")
                skills_to_remove.append(skill_name)
            elif total_calls >= min_calls and success_rate < min_success_rate:
                self.logger.info(
                    f"Pruning skill '{skill_name}' due to high failure rate "
                    f"(success_rate: {success_rate:.2f}, calls: {total_calls})."
                )
                skills_to_remove.append(skill_name)

        # Apply pruning
        for skill_name in skills_to_remove:
            if skill_name in self.registry.skills:
                del self.registry.skills[skill_name]
            if skill_name in self.registry.descriptions:
                del self.registry.descriptions[skill_name]
