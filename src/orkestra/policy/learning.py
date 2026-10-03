"""Continuous Learning Engine: pattern observation, clustering, hypotheses, and guardrails."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

from orkestra.schemas.common import utc_now
from orkestra.schemas.learning import (
    CandidatePolicy,
    PatternObservation,
    PolicyCandidateState,
    PolicyHypothesis,
)

# Inviolable kernel security rules that cannot be weakened by learned policies
FORBIDDEN_POLICY_KEYS = {
    "disable_verification",
    "bypass_gates",
    "bypass_lint",
    "skip_tests",
    "allow_self_review",
    "bypass_auth",
    "bypass_quota",
}


class LearningEngine:
    """Observes execution patterns, clusters failure modes, and proposes candidate policies."""

    def __init__(self) -> None:
        self._observations: list[PatternObservation] = []
        self._hypotheses: dict[str, PolicyHypothesis] = {}
        self._candidates: dict[str, CandidatePolicy] = {}

    def observe(self, observation: PatternObservation) -> None:
        """Record an atomic observation from an agent execution or verification run."""
        self._observations.append(observation)

    def synthesize_hypotheses(self, min_cluster_size: int = 3) -> list[PolicyHypothesis]:
        """Cluster observations by (provider, domain, trigger) and form hypotheses.

        When recurring failures are detected under specific conditions, an empirical hypothesis
        is generated to constrain or guide future dispatches.
        """
        failures = [o for o in self._observations if o.outcome in ("failure", "repair_loop")]
        clusters: dict[tuple[str, str, str], list[PatternObservation]] = defaultdict(list)

        for obs in failures:
            clusters[(obs.provider, obs.domain, obs.trigger)].append(obs)

        generated: list[PolicyHypothesis] = []
        for (provider, domain, trigger), items in clusters.items():
            if len(items) >= min_cluster_size:
                hypo_id = f"hypo_{uuid4().hex[:8]}"
                avg_confidence = round(sum(i.confidence for i in items) / len(items), 2)
                h = PolicyHypothesis(
                    hypothesis_id=hypo_id,
                    title=f"Recurring {trigger} failures on {provider}",
                    description=(
                        f"Detected {len(items)} failures on provider '{provider}' "
                        f"in domain '{domain}' with trigger '{trigger}'."
                    ),
                    supporting_observations=[i.observation_id for i in items],
                    confidence=avg_confidence,
                    suggested_rule=f"require_expert_tier_or_escalate_for_{trigger}",
                    target_domain=domain,
                    target_provider=provider,
                    created_at=utc_now(),
                )
                self._hypotheses[hypo_id] = h
                generated.append(h)

        return generated

    def validate_security_guardrails(self, candidate: CandidatePolicy) -> tuple[bool, list[str]]:
        """Strictly enforce that a candidate policy preserves deterministic security doctrine."""
        violations: list[str] = []
        params = candidate.parameters

        # 1. Verification bypass forbidden
        for key in FORBIDDEN_POLICY_KEYS:
            if key in params and params[key] is True:
                violations.append(f"Forbidden policy parameter detected: '{key}' cannot be True")

        # 2. Concurrency and nested worker bounds
        if "max_nested_workers" in params and params["max_nested_workers"] > 4:
            violations.append(f"max_nested_workers={params['max_nested_workers']} exceeds limit 4")
        if "max_total_concurrent_agents" in params and params["max_total_concurrent_agents"] > 8:
            violations.append(
                f"max_concurrency={params['max_total_concurrent_agents']} exceeds limit 8"
            )

        # 3. Effect class ceiling bypass forbidden
        if (
            "max_allowed_effect" in params
            and params["max_allowed_effect"] in ("SE3", "SE4")
            and params.get("target_role") not in ("director",)
        ):
            violations.append("Effect classes SE3/SE4 cannot be granted to non-director roles")

        is_valid = len(violations) == 0
        return is_valid, violations

    def create_candidate_policy(
        self,
        hypothesis: PolicyHypothesis,
        rule_type: str = "min_tier",
        parameters: dict[str, Any] | None = None,
    ) -> CandidatePolicy:
        """Create a candidate policy from a hypothesis and validate against guardrails."""
        cid = f"cand_{uuid4().hex[:8]}"
        params = parameters or {
            "min_tier": "reasoning",
            "target_trigger": hypothesis.suggested_rule,
        }

        candidate = CandidatePolicy(
            candidate_id=cid,
            hypothesis_id=hypothesis.hypothesis_id,
            title=f"Learned constraint: {hypothesis.title}",
            state=PolicyCandidateState.EXPERIMENTAL,
            rule_type=rule_type,
            parameters=params,
            is_security_compliant=True,
            created_at=utc_now(),
        )

        valid, violations = self.validate_security_guardrails(candidate)
        if not valid:
            candidate.is_security_compliant = False
            candidate.state = PolicyCandidateState.REJECTED
            candidate.rollback_reason = f"Security guardrail violations: {'; '.join(violations)}"

        self._candidates[cid] = candidate
        return candidate

    def get_candidate(self, candidate_id: str) -> CandidatePolicy | None:
        """Retrieve candidate policy by ID."""
        return self._candidates.get(candidate_id)

    def list_candidates(
        self,
        state: PolicyCandidateState | None = None,
    ) -> list[CandidatePolicy]:
        """List candidate policies, optionally filtered by state."""
        if state is not None:
            return [c for c in self._candidates.values() if c.state == state]
        return list(self._candidates.values())
