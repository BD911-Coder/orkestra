"""Unit tests for continuous learning, candidate policies, shadow evaluation, and rollback."""

from __future__ import annotations

from orkestra.policy.learning import LearningEngine
from orkestra.policy.promotion import PromotionHarness
from orkestra.schemas.learning import (
    CandidatePolicy,
    PatternObservation,
    PolicyCandidateState,
)
from orkestra.schemas.performance import TaskPerformanceRecord


class TestLearningAndPromotion:
    def test_observe_and_cluster_hypotheses(self) -> None:
        engine = LearningEngine()

        # Record 3 failures with the same trigger on provider "antigravity"
        for i in range(3):
            engine.observe(
                PatternObservation(
                    observation_id=f"obs-{i}",
                    task_id=f"task-{i}",
                    provider="antigravity",
                    domain="software",
                    trigger="complex_ast_refactor",
                    evidence="Recursion depth error during syntax parsing",
                    outcome="failure",
                    confidence=0.9,
                )
            )

        hypotheses = engine.synthesize_hypotheses(min_cluster_size=3)
        assert len(hypotheses) == 1
        h = hypotheses[0]
        assert h.target_provider == "antigravity"
        assert h.target_domain == "software"
        assert "complex_ast_refactor" in h.title
        assert len(h.supporting_observations) == 3

    def test_security_guardrails_rejection(self) -> None:
        engine = LearningEngine()
        for i in range(3):
            engine.observe(
                PatternObservation(
                    observation_id=f"obs-b-{i}",
                    task_id=f"task-b-{i}",
                    provider="codex",
                    domain="software",
                    trigger="flaky_tests",
                    evidence="Tests failed randomly",
                    outcome="failure",
                )
            )
        hypo = engine.synthesize_hypotheses(min_cluster_size=3)[0]

        # Malicious / illegal candidate attempting to disable verification and exceed workers
        bad_candidate = engine.create_candidate_policy(
            hypothesis=hypo,
            parameters={
                "disable_verification": True,
                "max_nested_workers": 12,
            },
        )
        assert bad_candidate.is_security_compliant is False
        assert bad_candidate.state == PolicyCandidateState.REJECTED
        assert "Forbidden policy parameter" in bad_candidate.rollback_reason
        assert "exceeds limit" in bad_candidate.rollback_reason

    def test_shadow_evaluation_and_promotion(self) -> None:
        engine = LearningEngine()
        for i in range(3):
            engine.observe(
                PatternObservation(
                    observation_id=f"obs-c-{i}",
                    task_id=f"task-c-{i}",
                    provider="claude",
                    domain="software",
                    trigger="large_diff_failure",
                    evidence="Failed review due to large single patch",
                    outcome="failure",
                )
            )
        hypo = engine.synthesize_hypotheses(min_cluster_size=3)[0]

        # Valid candidate policy: require reasoning tier for large diffs
        candidate = engine.create_candidate_policy(
            hypothesis=hypo,
            parameters={"min_tier": "reasoning", "target_provider": "claude"},
        )
        assert candidate.is_security_compliant is True
        assert candidate.state == PolicyCandidateState.EXPERIMENTAL

        # History with 4 tasks that failed due to repairs
        history = [
            TaskPerformanceRecord(
                performance_id=f"hist-{i}",
                task_id=f"t-hist-{i}",
                run_id="run-0",
                provider="claude",
                model="haiku",
                domain="software",
                pass_at_1=False,
                eventual_pass=False,
                repair_attempts=2,
            )
            for i in range(4)
        ]

        harness = PromotionHarness()
        score = harness.run_shadow_evaluation(candidate, history)
        assert score >= 0.7
        assert candidate.state == PolicyCandidateState.SHADOW
        assert candidate.shadow_eval_tasks == 4

        # Promote candidate
        promoted, _msg = harness.promote(candidate, min_score=0.6, min_tasks=3)
        assert promoted is True
        assert candidate.state == PolicyCandidateState.PROMOTED
        assert candidate.promoted_at is not None

        # Rollback
        harness.rollback(candidate, reason="Regression detected in downstream task")
        assert candidate.state == PolicyCandidateState.ROLLED_BACK
        assert "Regression detected" in candidate.rollback_reason

    def test_promotion_rejection_branches(self) -> None:
        harness = PromotionHarness()

        # Non-compliant candidate cannot be promoted
        cand_bad = CandidatePolicy(
            candidate_id="c-bad",
            hypothesis_id="h-bad",
            title="Bad Policy",
            is_security_compliant=False,
            rollback_reason="Bypassed security",
        )
        ok, reason = harness.promote(cand_bad)
        assert ok is False
        assert "non-compliant" in reason

        # Insufficient tasks
        cand_few = CandidatePolicy(
            candidate_id="c-few",
            hypothesis_id="h-few",
            title="Few Tasks",
            shadow_eval_tasks=1,
            shadow_eval_score=0.9,
        )
        ok, reason = harness.promote(cand_few, min_tasks=3)
        assert ok is False
        assert "Insufficient shadow tasks" in reason

        # Low score
        cand_low = CandidatePolicy(
            candidate_id="c-low",
            hypothesis_id="h-low",
            title="Low Score",
            shadow_eval_tasks=5,
            shadow_eval_score=0.3,
        )
        ok, reason = harness.promote(cand_low, min_score=0.6)
        assert ok is False
        assert "below threshold" in reason.lower() or "< threshold" in reason

    def test_candidate_listing_and_empty_history(self) -> None:
        engine = LearningEngine()
        cand = CandidatePolicy(
            candidate_id="c-1",
            hypothesis_id="h-1",
            title="Policy 1",
            state=PolicyCandidateState.EXPERIMENTAL,
        )
        engine._candidates[cand.candidate_id] = cand

        assert engine.get_candidate("c-1") is not None
        assert engine.get_candidate("c-missing") is None

        all_cands = engine.list_candidates()
        assert len(all_cands) == 1

        exp_cands = engine.list_candidates(state=PolicyCandidateState.EXPERIMENTAL)
        assert len(exp_cands) == 1

        prom_cands = engine.list_candidates(state=PolicyCandidateState.PROMOTED)
        assert len(prom_cands) == 0

        # Empty history shadow evaluation
        harness = PromotionHarness()
        score = harness.run_shadow_evaluation(cand, [])
        assert score == 0.0
        assert cand.state == PolicyCandidateState.SHADOW
