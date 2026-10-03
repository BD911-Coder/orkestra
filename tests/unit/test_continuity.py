"""Unit tests for Phase O Session Continuity, Context Pressure, and Switching Cost Control."""

from __future__ import annotations

from orkestra.kernel.continuity import SessionContinuityEngine
from orkestra.kernel.router import ResourceRouter
from orkestra.schemas.common import TaskKind
from orkestra.schemas.continuity import (
    ContextAction,
    ContextPressureLevel,
    SessionContinuityState,
)
from orkestra.schemas.task import TaskSpec


def test_session_switching_adjustment() -> None:
    """Warm provider affinity yields bonus; cold provider switch incurs penalty."""
    engine = SessionContinuityEngine(same_provider_bonus=1.0, cold_switch_penalty=1.5)

    # 1. Warm affinity
    bonus, reason = engine.compute_switching_adjustment("claude", "claude")
    assert bonus == 1.0
    assert reason == "session_warm_affinity:+1.00"

    # 2. Cold switch penalty
    penalty, reason = engine.compute_switching_adjustment("claude", "codex")
    assert penalty == -1.5
    assert reason == "cold_session_switch_penalty:-1.50"

    # 3. Initial dispatch (no previous provider)
    neutral, reason = engine.compute_switching_adjustment(None, "claude")
    assert neutral == 0.0
    assert reason is None


def test_context_pressure_levels_and_actions() -> None:
    """Context pressure levels appropriately trigger continue, compact, or handoff."""
    engine = SessionContinuityEngine()
    window = 200_000

    # 1. Normal (< 60%)
    ev1 = engine.evaluate_context_pressure(50_000, window)
    assert ev1.pressure_level == ContextPressureLevel.NORMAL
    assert ev1.recommended_action == ContextAction.CONTINUE

    # 2. Elevated (60% - 80%)
    ev2 = engine.evaluate_context_pressure(140_000, window)
    assert ev2.pressure_level == ContextPressureLevel.ELEVATED
    assert ev2.recommended_action == ContextAction.CONTINUE

    # 3. High (80% - 90%) -> Proactive compaction trigger
    ev3 = engine.evaluate_context_pressure(170_000, window)
    assert ev3.pressure_level == ContextPressureLevel.HIGH
    assert ev3.recommended_action == ContextAction.COMPACT

    # 4. Critical (> 90%) -> Immediate handoff required
    ev4 = engine.evaluate_context_pressure(190_000, window)
    assert ev4.pressure_level == ContextPressureLevel.CRITICAL
    assert ev4.recommended_action == ContextAction.HANDOFF


def test_record_session_transition() -> None:
    """Transitioning providers increments switch counter and tracks token accumulators."""
    engine = SessionContinuityEngine()
    init_state = SessionContinuityState(
        active_run_id="run_101",
        current_provider="claude",
        tokens_accumulated=10_000,
        switch_count=0,
    )

    # Same provider: tokens accumulate, switch count unchanged
    state2 = engine.record_transition(
        init_state, "claude", additional_tokens=5_000, checkpoint_id="chk_1"
    )
    assert state2.current_provider == "claude"
    assert state2.tokens_accumulated == 15_000
    assert state2.switch_count == 0
    assert state2.last_checkpoint_id == "chk_1"

    # Switched provider: switch count increments, token accumulator tracks new task
    state3 = engine.record_transition(
        state2, "codex", additional_tokens=2_000, checkpoint_id="chk_2"
    )
    assert state3.current_provider == "codex"
    assert state3.tokens_accumulated == 2_000
    assert state3.switch_count == 1
    assert state3.last_checkpoint_id == "chk_2"


def test_router_integration_with_session_continuity() -> None:
    """ResourceRouter applies session affinity bonus and cold switch penalty."""
    router = ResourceRouter()
    spec = TaskSpec(
        key="T2",
        title="Refactor core architecture",
        description="Heavy architecture task",
        kind=TaskKind.IMPLEMENT,
    )

    # Session currently running on codex
    session = SessionContinuityState(
        active_run_id="run_202",
        current_provider="codex",
    )

    decision = router.select_best_profile(
        task_id="task_session_test",
        run_id="run_202",
        spec=spec,
        snapshots={},
        session_state=session,
    )

    # Decision reasons must show session continuity impact
    assert decision.selected_profile.startswith("codex")
    assert any("session_warm_affinity" in r for r in decision.reasons)
