"""Phase S — V2 33-Scenario Integration Test Matrix.

Tests covering the complete Orkestra V2 subsystem integration:
- Multi-window quota evaluation
- Session continuity with switching costs
- Swarm topology nesting limits
- Outcome memory & counterfactual evaluation
- Failure classification & stagnation detection
- Event bus & replay synthesis
- Approval gate SE3/SE4 enforcement
- Router integration with V2 scoring components
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from orkestra.kernel.approval import ApprovalRequest, ApprovalStatus, HumanApprovalGate
from orkestra.kernel.continuity import SessionContinuityEngine
from orkestra.kernel.counterfactual import CounterfactualEvaluator
from orkestra.kernel.failure import FailureClassifier, StagnationDetector
from orkestra.kernel.memory import OutcomeMemoryStore
from orkestra.kernel.resources_v2 import MultiWindowQuotaEvaluator
from orkestra.kernel.topology import TopologyIntelligenceEngine
from orkestra.report.replay import RunReplaySynthesizer
from orkestra.schemas.common import utc_now
from orkestra.schemas.events_v2 import EventType, OrkestraEvent
from orkestra.schemas.memory import CounterfactualStrategy, FailureCategory, TaskOutcomeRecord
from orkestra.schemas.resources_v2 import (
    QuotaConfidence,
    QuotaWindowStatus,
    QuotaWindowType,
)
from orkestra.schemas.tools import EffectClass

# ===========================================================================
# SCENARIO GROUP 1: Multi-Window Quota (Scenarios 1-5)
# ===========================================================================


def test_scenario_01_unknown_quota_blocks_abundant_routing() -> None:
    """S1: UNKNOWN confidence cannot be treated as ABUNDANT headroom."""
    evaluator = MultiWindowQuotaEvaluator()
    profile = evaluator.evaluate_profile(
        provider="unknown_prov",
        raw_windows=[
            QuotaWindowStatus(
                window_type=QuotaWindowType.DAILY,
                confidence=QuotaConfidence.UNKNOWN,
                used_ratio=0.0,
            )
        ],
    )
    assert profile.composite_headroom < 1.0
    assert profile.composite_headroom < 0.5  # heavily penalized by UNKNOWN confidence


def test_scenario_02_monthly_scarcity_caps_daily_abundance() -> None:
    """S2: A scarce monthly window must cap a fresh daily window."""
    evaluator = MultiWindowQuotaEvaluator()
    profile = evaluator.evaluate_profile(
        provider="constrained_prov",
        raw_windows=[
            QuotaWindowStatus(
                window_type=QuotaWindowType.DAILY,
                confidence=QuotaConfidence.EXACT,
                used_ratio=0.0,  # daily is fresh
            ),
            QuotaWindowStatus(
                window_type=QuotaWindowType.MONTHLY,
                confidence=QuotaConfidence.EXACT,
                used_ratio=0.95,  # monthly is nearly exhausted
            ),
        ],
    )
    assert profile.composite_headroom < 0.6  # monthly scarcity caps the daily fresh window


def test_scenario_03_reset_pressure_boosts_score_when_backlog_exists() -> None:
    """S3: Near-reset quota earns a routing bonus when backlog workload exists."""
    evaluator = MultiWindowQuotaEvaluator()
    now = utc_now()
    profile = evaluator.evaluate_profile(
        provider="near_reset_prov",
        raw_windows=[
            {
                "window_type": QuotaWindowType.FIVE_HOUR,
                "confidence": QuotaConfidence.EXACT,
                "used": 10.0,
                "limit": 100.0,
                "reset_at": now + timedelta(seconds=120),
            }
        ],
        current_time=now,
    )
    assert profile.composite_reset_pressure > 0.5


def test_scenario_04_estimated_confidence_applies_multiplier() -> None:
    """S4: ESTIMATED confidence correctly applies < 1.0 multiplier vs EXACT."""
    evaluator = MultiWindowQuotaEvaluator()
    exact_profile = evaluator.evaluate_profile(
        provider="p",
        raw_windows=[
            QuotaWindowStatus(
                window_type=QuotaWindowType.DAILY,
                confidence=QuotaConfidence.EXACT,
                used_ratio=0.3,
            )
        ],
    )
    est_profile = evaluator.evaluate_profile(
        provider="p",
        raw_windows=[
            QuotaWindowStatus(
                window_type=QuotaWindowType.DAILY,
                confidence=QuotaConfidence.ESTIMATED,
                used_ratio=0.3,
            )
        ],
    )
    assert est_profile.composite_headroom < exact_profile.composite_headroom


def test_scenario_05_burn_velocity_reported_as_nonnegative() -> None:
    """S5: Burn velocity must be non-negative regardless of window state."""
    ws = QuotaWindowStatus(
        window_type=QuotaWindowType.DAILY,
        confidence=QuotaConfidence.EXACT,
        used_ratio=0.7,
        seconds_to_reset=3600,
    )
    assert ws.burn_velocity_per_hour >= 0.0


# ===========================================================================
# SCENARIO GROUP 2: Session Continuity (Scenarios 6-10)
# ===========================================================================


def test_scenario_06_warm_session_affinity_bonus() -> None:
    """S6: A warm (same-provider) session receives a positive routing adjustment."""
    engine = SessionContinuityEngine()
    adj, _ = engine.compute_switching_adjustment(
        previous_provider="claude", candidate_provider="claude"
    )
    assert adj > 0.0  # warm affinity bonus


def test_scenario_07_cold_switch_penalty() -> None:
    """S7: A cold switch to a different provider incurs a negative adjustment."""
    engine = SessionContinuityEngine()
    adj, _ = engine.compute_switching_adjustment(
        previous_provider="claude", candidate_provider="antigravity"
    )
    assert adj < 0.0  # cold switch penalty


def test_scenario_08_first_dispatch_has_no_penalty() -> None:
    """S8: When no provider is active yet, any provider has zero or positive adjustment."""
    engine = SessionContinuityEngine()
    adj, _ = engine.compute_switching_adjustment(previous_provider=None, candidate_provider="codex")
    assert adj >= 0.0


def test_scenario_09_context_pressure_critical_at_90_percent() -> None:
    """S9: At 90%+ context saturation, pressure level is CRITICAL."""
    engine = SessionContinuityEngine()
    # 190,000 tokens out of 200,000 = 95% — critical
    event = engine.evaluate_context_pressure(token_count=190_000, window_limit=200_000)
    from orkestra.schemas.continuity import ContextPressureLevel

    assert event.pressure_level == ContextPressureLevel.CRITICAL


def test_scenario_10_context_pressure_normal_at_50_percent() -> None:
    """S10: At 50% context saturation, pressure level is NORMAL."""
    engine = SessionContinuityEngine()
    event = engine.evaluate_context_pressure(token_count=100_000, window_limit=200_000)
    from orkestra.schemas.continuity import ContextPressureLevel

    assert event.pressure_level == ContextPressureLevel.NORMAL


# ===========================================================================
# SCENARIO GROUP 3: Swarm Topology (Scenarios 11-15)
# ===========================================================================


def test_scenario_11_dispatch_within_nesting_limit_allowed() -> None:
    """S11: Nesting depth of 1 is within the allowed depth-2 limit."""
    engine = TopologyIntelligenceEngine()
    allowed, _ = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=1, total_concurrent=2
    )
    assert allowed is True


def test_scenario_12_dispatch_exceeds_nesting_depth_blocked() -> None:
    """S12: Nesting depth of 3 violates the depth-2 limit."""
    engine = TopologyIntelligenceEngine()
    allowed, reason = engine.validate_subagent_dispatch(
        current_depth=3, current_nested_workers=1, total_concurrent=2
    )
    assert allowed is False
    assert reason is not None
    assert "depth" in reason.lower()


def test_scenario_13_concurrent_workers_at_max_allowed() -> None:
    """S13: 7 concurrent workers allows dispatching another within the 8-worker cap."""
    engine = TopologyIntelligenceEngine()
    allowed, _ = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=1, total_concurrent=7
    )
    assert allowed is True


def test_scenario_14_concurrent_workers_over_max_blocked() -> None:
    """S14: 9 concurrent workers exceeds the 8-worker cap."""
    engine = TopologyIntelligenceEngine()
    allowed, _ = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=1, total_concurrent=9
    )
    assert allowed is False


def test_scenario_15_parallel_efficiency_single_worker_is_one() -> None:
    """S15: A single worker always has speedup of 1.0."""
    engine = TopologyIntelligenceEngine()
    metrics = engine.calculate_parallel_efficiency(
        seq_sec=60.0, par_sec=60.0, worker_count=1, seq_tokens=1000, par_tokens=1000
    )
    assert metrics.speedup == pytest.approx(1.0, abs=0.01)


# ===========================================================================
# SCENARIO GROUP 4: Outcome Memory & Counterfactual (Scenarios 16-20)
# ===========================================================================


def _make_outcome(
    task_kind: str, domain: str, provider: str, success: bool, keywords: list[str] | None = None
) -> TaskOutcomeRecord:
    """Build a minimal TaskOutcomeRecord with required fields."""
    from uuid import uuid4

    return TaskOutcomeRecord(
        outcome_id=f"outcome_{uuid4().hex[:8]}",
        task_key=f"task_{uuid4().hex[:6]}",
        task_kind=task_kind,
        task_domain=domain,
        keywords=keywords or [],
        provider=provider,
        model=f"{provider}-default",
        success=success,
        duration_sec=100.0,
        tokens_used=3000,
    )


def test_scenario_16_memory_records_and_retrieves_outcomes() -> None:
    """S16: Recorded outcomes are retrievable by task similarity."""
    store = OutcomeMemoryStore()
    record = _make_outcome("implementation", "backend", "claude", True, ["api", "rest"])
    store.record_outcome(record)
    similar = store.find_similar_outcomes("implementation", "backend", ["api", "rest"])
    assert len(similar) >= 1
    assert similar[0].task_kind == "implementation"


def test_scenario_17_counterfactual_produces_five_strategies() -> None:
    """S17: Counterfactual evaluation always returns exactly 5 strategy comparisons."""
    evaluator = CounterfactualEvaluator()
    comparisons = evaluator.evaluate_run(
        actual_cost_usd=0.25,
        actual_duration_sec=300.0,
        actual_success=True,
    )
    assert len(comparisons) == 5
    strategies = {c.strategy for c in comparisons}
    assert CounterfactualStrategy.ACTUAL in strategies
    assert CounterfactualStrategy.CHEAPEST in strategies


def test_scenario_18_actual_strategy_matches_inputs() -> None:
    """S18: The ACTUAL counterfactual comparison faithfully reflects the real run."""
    evaluator = CounterfactualEvaluator()
    comparisons = evaluator.evaluate_run(
        actual_cost_usd=0.10,
        actual_duration_sec=240.0,
        actual_success=True,
    )
    actual = next(c for c in comparisons if c.strategy == CounterfactualStrategy.ACTUAL)
    assert actual.projected_duration_sec == pytest.approx(240.0, abs=0.1)
    assert actual.projected_success_rate > 0.0


def test_scenario_19_failure_classifier_identifies_lint_error() -> None:
    """S19: Lint output is correctly classified as SYNTAX_LINT."""
    classifier = FailureClassifier()
    category = classifier.classify(
        "E501 line too long (110 > 100)\nruff check failed\n2 errors found"
    )
    assert category == FailureCategory.SYNTAX_LINT


def test_scenario_20_stagnation_detector_triggers_on_repeats() -> None:
    """S20: Identical consecutive failure outputs trigger stagnation."""
    detector = StagnationDetector(repeat_threshold=2)
    output = "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
    # First occurrence — not stagnating
    result1 = detector.record_attempt(run_id="run_s20", task_key="lint_task", error_output=output)
    assert result1.is_stagnated is False
    # Second identical — triggers stagnation
    result2 = detector.record_attempt(run_id="run_s20", task_key="lint_task", error_output=output)
    assert result2.is_stagnated is True


# ===========================================================================
# SCENARIO GROUP 5: Event Bus & Replay (Scenarios 21-25)
# ===========================================================================


def _make_event(
    run_id: str, event_type: EventType, offset_s: int = 0, payload: dict | None = None
) -> OrkestraEvent:
    return OrkestraEvent(
        run_id=run_id,
        correlation_id=f"corr_{event_type.value}",
        event_type=event_type,
        timestamp=utc_now() + timedelta(seconds=offset_s),
        payload=payload or {},
    )


def test_scenario_21_replay_empty_run_summary() -> None:
    """S21: Empty event list produces a valid summary with NO_EVENTS_RECORDED."""
    synth = RunReplaySynthesizer()
    summary = synth.synthesize("run_s21", [])
    assert summary.total_events == 0
    assert summary.final_verdict == "NO_EVENTS_RECORDED"


def test_scenario_22_replay_sorts_events_chronologically() -> None:
    """S22: Events fed in reverse order are sorted correctly."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event("run_s22", EventType.REVIEW_VERDICT, offset_s=10),
        _make_event("run_s22", EventType.TASK_DISPATCH, offset_s=0),
    ]
    summary = synth.synthesize("run_s22", evts)
    assert summary.steps[0].event_type == EventType.TASK_DISPATCH
    assert summary.steps[1].event_type == EventType.REVIEW_VERDICT


def test_scenario_23_replay_detects_succeeded_lifecycle() -> None:
    """S23: SUCCEEDED lifecycle state maps to PASSED final verdict."""
    synth = RunReplaySynthesizer()
    evts = [_make_event("run_s23", EventType.RUN_LIFECYCLE, payload={"state": "SUCCEEDED"})]
    summary = synth.synthesize("run_s23", evts)
    assert summary.final_verdict == "PASSED"


def test_scenario_24_replay_markdown_contains_all_event_types() -> None:
    """S24: Markdown output for a full event-type run includes type names."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event("run_s24", EventType.TASK_DISPATCH, offset_s=0),
        _make_event("run_s24", EventType.QUOTA_TELEMETRY, offset_s=1),
        _make_event("run_s24", EventType.VERIFICATION_GATE, offset_s=2),
        _make_event("run_s24", EventType.REVIEW_VERDICT, offset_s=3),
    ]
    summary = synth.synthesize("run_s24", evts)
    md = synth.render_markdown(summary)
    assert "task_dispatch" in md
    assert "quota_telemetry" in md
    assert "verification_gate" in md
    assert "review_verdict" in md


def test_scenario_25_event_ids_are_unique_across_instances() -> None:
    """S25: Auto-generated event_ids across OrkestraEvent instances must not collide."""
    events = [
        OrkestraEvent(
            run_id="run_s25",
            correlation_id="c1",
            event_type=EventType.TASK_DISPATCH,
        )
        for _ in range(50)
    ]
    ids = [e.event_id for e in events]
    assert len(set(ids)) == 50  # all unique


# ===========================================================================
# SCENARIO GROUP 6: Approval Gate (Scenarios 26-30)
# ===========================================================================


def test_scenario_26_se0_never_needs_approval() -> None:
    """S26: SE0 operations are always auto-approved immediately."""
    gate = HumanApprovalGate()
    req = ApprovalRequest(
        run_id="run_s26",
        task_key="read_files",
        effect_class=EffectClass.SE0_READ_ONLY,
        description="inspect workspace",
    )
    record = gate.evaluate(req)
    assert record.status == ApprovalStatus.AUTO_APPROVED
    assert len(gate.list_pending()) == 0


def test_scenario_27_se3_pre_auth_avoids_interruption() -> None:
    """S27: Granting SE3 pre-auth allows subsequent operations without re-prompting."""
    gate = HumanApprovalGate()
    req = ApprovalRequest(
        run_id="run_s27",
        task_key="git_push",
        effect_class=EffectClass.SE3_REMOTE_EVIDENCE,
        description="push branch",
    )
    pending = gate.evaluate(req)
    gate.grant(pending.approval_id, approver="ci-bot", reason="pre-authorized for session")

    record2 = gate.evaluate(req)
    assert record2.status == ApprovalStatus.APPROVED
    assert len(gate.list_pending()) == 0


def test_scenario_28_se4_requires_approval_every_time() -> None:
    """S28: SE4 operations always require a fresh approval — pre-auth is never honored."""
    gate = HumanApprovalGate()
    req = ApprovalRequest(
        run_id="run_s28",
        task_key="billing_op",
        effect_class=EffectClass.SE4_EXTERNAL_CRITICAL,
        description="charge card",
    )
    p1 = gate.evaluate(req)
    gate.grant(p1.approval_id)

    p2 = gate.evaluate(req)
    assert p2.status == ApprovalStatus.PENDING


def test_scenario_29_multiple_pending_ops_tracked_independently() -> None:
    """S29: Multiple pending SE3/SE4 operations are tracked independently."""
    gate = HumanApprovalGate()
    for i in range(5):
        req = ApprovalRequest(
            run_id=f"run_{i}",
            task_key=f"op_{i}",
            effect_class=EffectClass.SE3_REMOTE_EVIDENCE,
            description=f"SE3 op {i}",
        )
        gate.evaluate(req)
    assert len(gate.list_pending()) == 5


def test_scenario_30_denial_does_not_leak_approval() -> None:
    """S30: Denying an SE3 request leaves no cached approval."""
    gate = HumanApprovalGate()
    req = ApprovalRequest(
        run_id="run_s30",
        task_key="push",
        effect_class=EffectClass.SE3_REMOTE_EVIDENCE,
        description="push",
    )
    pending = gate.evaluate(req)
    gate.deny(pending.approval_id, reason="security policy violation")

    r2 = gate.evaluate(req)
    assert r2.status == ApprovalStatus.PENDING


# ===========================================================================
# SCENARIO GROUP 7: Cross-Subsystem Integration (Scenarios 31-33)
# ===========================================================================


def test_scenario_31_stagnation_triggers_after_threshold() -> None:
    """S31: Stagnation detector escalates after the configured repeat threshold."""
    detector = StagnationDetector(repeat_threshold=3)
    output = "ModuleNotFoundError: No module named 'foobar'"
    results = [
        detector.record_attempt(run_id="run_s31", task_key="install_task", error_output=output)
        for _ in range(4)
    ]
    # At threshold=3, the 3rd repeat (index 2) triggers stagnation
    assert results[2].is_stagnated is True
    assert results[3].is_stagnated is True


def test_scenario_32_memory_recommendation_prefers_successful_provider() -> None:
    """S32: Outcome memory recommends the provider with higher historical success."""
    store = OutcomeMemoryStore()
    for _ in range(3):
        store.record_outcome(
            _make_outcome("implementation", "backend", "claude", True, ["python", "api"])
        )
    for _ in range(3):
        store.record_outcome(
            _make_outcome("implementation", "backend", "codex", False, ["python", "api"])
        )
    best_provider, _ = store.recommend_provider_for_task(
        "implementation", "backend", ["python", "api"]
    )
    assert best_provider == "claude"


def test_scenario_33_full_pipeline_event_to_replay_markdown() -> None:
    """S33: A complete lifecycle from event emission to markdown replay renders correctly."""
    events = [
        OrkestraEvent(
            run_id="run_s33",
            correlation_id="c_start",
            event_type=EventType.RUN_LIFECYCLE,
            timestamp=utc_now(),
            payload={"state": "STARTED"},
        ),
        OrkestraEvent(
            run_id="run_s33",
            correlation_id="c_dispatch",
            event_type=EventType.TASK_DISPATCH,
            timestamp=utc_now() + timedelta(seconds=5),
            payload={"task_key": "implement_auth", "provider": "claude", "topology": "star"},
        ),
        OrkestraEvent(
            run_id="run_s33",
            correlation_id="c_gate",
            event_type=EventType.VERIFICATION_GATE,
            timestamp=utc_now() + timedelta(seconds=60),
            payload={"gate_name": "ruff_mypy", "status": "PASSED", "exit_code": 0},
        ),
        OrkestraEvent(
            run_id="run_s33",
            correlation_id="c_review",
            event_type=EventType.REVIEW_VERDICT,
            timestamp=utc_now() + timedelta(seconds=90),
            payload={"reviewer": "antigravity", "verdict": "APPROVED"},
        ),
        OrkestraEvent(
            run_id="run_s33",
            correlation_id="c_end",
            event_type=EventType.RUN_LIFECYCLE,
            timestamp=utc_now() + timedelta(seconds=120),
            payload={"state": "COMPLETE"},
        ),
    ]

    synth = RunReplaySynthesizer()
    summary = synth.synthesize("run_s33", events)

    assert summary.total_events == 5
    assert summary.final_verdict == "PASSED"
    assert summary.steps[0].event_type == EventType.RUN_LIFECYCLE
    assert summary.steps[-1].event_type == EventType.RUN_LIFECYCLE

    md = synth.render_markdown(summary)
    assert "run_s33" in md
    assert "PASSED" in md
