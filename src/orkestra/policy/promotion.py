"""Shadow evaluation, staged candidate promotion, and instant rollback harness."""

from __future__ import annotations

from orkestra.schemas.common import utc_now
from orkestra.schemas.learning import (
    CandidatePolicy,
    PolicyCandidateState,
)
from orkestra.schemas.performance import TaskPerformanceRecord


class PromotionHarness:
    """Evaluates candidate policies against historical performance records before promotion."""

    def run_shadow_evaluation(
        self,
        candidate: CandidatePolicy,
        task_history: list[TaskPerformanceRecord],
    ) -> float:
        """Replay candidate policy against historical task records offline.

        Calculates a shadow evaluation score:
        - Beneficial intervention (would have avoided a failure/repair): +1.0
        - Neutral intervention: 0.0
        - Detrimental restriction (would have blocked a successful task): -1.0

        Score normalized from 0.0 to 1.0.
        """
        if not task_history:
            candidate.shadow_eval_score = 0.0
            candidate.shadow_eval_tasks = 0
            candidate.state = PolicyCandidateState.SHADOW
            return 0.0

        target_provider = candidate.parameters.get("target_provider")
        target_domain = candidate.parameters.get("target_domain")

        relevant_tasks = [
            t
            for t in task_history
            if (not target_provider or t.provider.lower() == target_provider.lower())
            and (not target_domain or t.domain.lower() == target_domain.lower())
        ]

        if not relevant_tasks:
            relevant_tasks = task_history

        net_points = 0.0
        for task in relevant_tasks:
            if not task.eventual_pass or task.repair_attempts > 1:
                # Task struggled or failed in historical reality: candidate policy helps
                net_points += 1.0
            elif task.pass_at_1:
                # Task succeeded cleanly in historical reality
                # If candidate policy would unnecessarily restrict standard tier, penalize
                if candidate.parameters.get("min_tier") == "expert" and task.model != "expert":
                    net_points -= 0.5
                else:
                    net_points += 0.5

        # Normalize score into [0.0, 1.0]
        max_possible = float(len(relevant_tasks))
        normalized = max(0.0, min(1.0, (net_points + max_possible) / (2 * max_possible)))

        candidate.shadow_eval_score = round(normalized, 4)
        candidate.shadow_eval_tasks = len(relevant_tasks)
        candidate.state = PolicyCandidateState.SHADOW

        return candidate.shadow_eval_score

    def promote(
        self,
        candidate: CandidatePolicy,
        min_score: float = 0.6,
        min_tasks: int = 3,
    ) -> tuple[bool, str]:
        """Promote a candidate policy into active enforcement if criteria are satisfied."""
        if not candidate.is_security_compliant:
            candidate.state = PolicyCandidateState.REJECTED
            return False, f"Cannot promote non-compliant policy: {candidate.rollback_reason}"

        if candidate.shadow_eval_tasks < min_tasks:
            return (
                False,
                f"Insufficient shadow tasks ({candidate.shadow_eval_tasks} < {min_tasks})",
            )

        if candidate.shadow_eval_score < min_score:
            candidate.state = PolicyCandidateState.REJECTED
            return (
                False,
                f"Shadow score ({candidate.shadow_eval_score:.2f}) < threshold ({min_score:.2f})",
            )

        candidate.state = PolicyCandidateState.PROMOTED
        candidate.promoted_at = utc_now()
        return True, "Promoted successfully"

    def rollback(self, candidate: CandidatePolicy, reason: str) -> None:
        """Instantly revert a promoted candidate policy to safe baseline."""
        candidate.state = PolicyCandidateState.ROLLED_BACK
        candidate.rollback_reason = reason
