"""Unit tests for Phase Q Performance Intelligence V2:
Memory, Counterfactual, and Failure Analysis.
"""

from __future__ import annotations

from orkestra.kernel.counterfactual import CounterfactualEvaluator
from orkestra.kernel.failure import FailureClassifier, StagnationDetector
from orkestra.kernel.memory import OutcomeMemoryStore
from orkestra.schemas.memory import (
    CounterfactualStrategy,
    FailureCategory,
    TaskOutcomeRecord,
)


def test_outcome_memory_and_recommendation() -> None:
    """Outcome memory indexes historical performance and recommends high-probability providers."""
    store = OutcomeMemoryStore()

    # Seed history: Claude succeeded on architecture tasks; Codex failed
    store.record_outcome(
        TaskOutcomeRecord(
            outcome_id="out_1",
            task_key="T1",
            task_kind="implement",
            task_domain="architecture",
            keywords=["refactor", "kernel"],
            provider="claude",
            model="sonnet",
            success=True,
            duration_sec=45.0,
            tokens_used=5000,
        )
    )
    store.record_outcome(
        TaskOutcomeRecord(
            outcome_id="out_2",
            task_key="T2",
            task_kind="implement",
            task_domain="architecture",
            keywords=["refactor", "kernel"],
            provider="codex",
            model="o3-mini",
            success=False,
            duration_sec=30.0,
            tokens_used=4000,
        )
    )

    # Query recommendation
    rec_provider, success_rate = store.recommend_provider_for_task(
        task_kind="implement",
        task_domain="architecture",
        keywords=["refactor"],
    )

    assert rec_provider == "claude"
    assert success_rate == 1.0


def test_counterfactual_strategy_evaluation() -> None:
    """Counterfactual evaluator projects costs and latencies across alternate routing models."""
    evaluator = CounterfactualEvaluator()
    comparisons = evaluator.evaluate_run(
        actual_cost_usd=1.00,
        actual_duration_sec=100.0,
        actual_success=True,
    )

    by_strategy = {c.strategy: c for c in comparisons}
    assert CounterfactualStrategy.ACTUAL in by_strategy
    assert CounterfactualStrategy.CHEAPEST in by_strategy
    assert CounterfactualStrategy.FASTEST in by_strategy
    assert CounterfactualStrategy.MAX_QUALITY in by_strategy
    assert CounterfactualStrategy.ADAPTIVE_BALANCED in by_strategy

    # Cheapest should have lowest cost
    assert by_strategy[CounterfactualStrategy.CHEAPEST].projected_cost_usd < 1.00
    # Fastest should have lowest duration
    assert by_strategy[CounterfactualStrategy.FASTEST].projected_duration_sec < 100.0
    # Max quality should have highest cost
    assert by_strategy[CounterfactualStrategy.MAX_QUALITY].projected_cost_usd > 1.00


def test_failure_classification() -> None:
    """FailureClassifier accurately buckets distinct root failure classes."""
    assert (
        FailureClassifier.classify("SyntaxError: invalid syntax in file foo.py")
        == FailureCategory.SYNTAX_LINT
    )
    assert (
        FailureClassifier.classify("mypy: error: Incompatible types in assignment")
        == FailureCategory.TYPE_CHECK
    )
    assert (
        FailureClassifier.classify("FAILED tests/test_foo.py::test_bar - AssertionError")
        == FailureCategory.TEST_FAILURE
    )
    assert (
        FailureClassifier.classify("HTTP 429 Too Many Requests: Rate limit exceeded")
        == FailureCategory.QUOTA_EXHAUSTION
    )
    assert (
        FailureClassifier.classify("Process execution timed out after 300 seconds")
        == FailureCategory.TIMEOUT
    )


def test_stagnation_loop_detection() -> None:
    """StagnationDetector flags identical repeating errors and mandates strategy escalation."""
    detector = StagnationDetector(repeat_threshold=2)
    err = "AssertionError: expected status code 200, got 500 at line 42"

    # Attempt 1: recorded, not stagnated yet
    rep1 = detector.record_attempt("run_1", "T_AUTH", err)
    assert rep1.is_stagnated is False
    assert rep1.consecutive_repetitions == 1
    assert rep1.mandated_escalation is None

    # Attempt 2: identical error output -> triggers stagnation loop!
    rep2 = detector.record_attempt("run_1", "T_AUTH", err)
    assert rep2.is_stagnated is True
    assert rep2.consecutive_repetitions == 2
    assert rep2.failure_category == FailureCategory.STAGNATION_LOOP
    assert rep2.mandated_escalation is not None
    assert "STAGNATION_LOOP_DETECTED" in rep2.mandated_escalation
