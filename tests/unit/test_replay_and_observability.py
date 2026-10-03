"""Tests for Phase R: Event Bus, Run Replay Synthesizer, and Observability."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from orkestra.report.replay import RunReplaySynthesizer
from orkestra.schemas.common import utc_now
from orkestra.schemas.events_v2 import (
    EventType,
    OrkestraEvent,
    ReplayStep,
    RunReplaySummary,
)

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_orkestra_event_default_ids() -> None:
    """OrkestraEvent auto-generates event_id and timestamps correctly."""
    evt = OrkestraEvent(
        run_id="run_abc",
        correlation_id="corr_xyz",
        event_type=EventType.TASK_DISPATCH,
        payload={"task_key": "implement_feature", "provider": "antigravity"},
    )
    assert evt.event_id.startswith("evt_")
    assert len(evt.event_id) == 12  # "evt_" + 8 hex chars
    assert evt.run_id == "run_abc"
    assert evt.correlation_id == "corr_xyz"


def test_event_type_values() -> None:
    """EventType StrEnum has the canonical taxonomy values."""
    assert EventType.RUN_LIFECYCLE == "run_lifecycle"
    assert EventType.TASK_DISPATCH == "task_dispatch"
    assert EventType.QUOTA_TELEMETRY == "quota_telemetry"
    assert EventType.VERIFICATION_GATE == "verification_gate"
    assert EventType.REVIEW_VERDICT == "review_verdict"
    assert EventType.CONTEXT_PRESSURE == "context_pressure"
    assert EventType.CONTINUITY_TRANSITION == "continuity_transition"
    assert EventType.STAGNATION_WARNING == "stagnation_warning"


def test_replay_step_frozen() -> None:
    """ReplayStep is immutable (frozen Pydantic model)."""
    step = ReplayStep(
        step_index=1,
        timestamp=utc_now(),
        event_type=EventType.VERIFICATION_GATE,
        title="Gate: ruff",
        details="exit code 0",
        correlation_id="corr_001",
    )
    with pytest.raises(ValidationError):
        step.step_index = 99  # type: ignore[misc]


def test_run_replay_summary_defaults() -> None:
    """RunReplaySummary defaults to UNKNOWN verdict and empty steps."""
    now = utc_now()
    s = RunReplaySummary(run_id="run_test", total_events=0, start_time=now)
    assert s.final_verdict == "UNKNOWN"
    assert s.steps == []
    assert s.end_time is None


# ---------------------------------------------------------------------------
# RunReplaySynthesizer — empty event list
# ---------------------------------------------------------------------------


def test_synthesize_empty_events() -> None:
    """Synthesizer returns a well-formed summary even with zero events."""
    synth = RunReplaySynthesizer()
    summary = synth.synthesize(run_id="run_empty", events=[])
    assert summary.run_id == "run_empty"
    assert summary.total_events == 0
    assert summary.steps == []
    assert summary.final_verdict == "NO_EVENTS_RECORDED"
    assert summary.start_time == summary.end_time


# ---------------------------------------------------------------------------
# RunReplaySynthesizer — multi-event synthesis
# ---------------------------------------------------------------------------


def _make_event(
    run_id: str,
    event_type: EventType,
    correlation_id: str,
    payload: dict | None = None,
    offset_seconds: int = 0,
) -> OrkestraEvent:
    return OrkestraEvent(
        run_id=run_id,
        correlation_id=correlation_id,
        event_type=event_type,
        timestamp=utc_now() + timedelta(seconds=offset_seconds),
        payload=payload or {},
    )


def test_synthesize_chronological_ordering() -> None:
    """Events are sorted by timestamp regardless of insertion order."""
    synth = RunReplaySynthesizer()
    # Create events in reverse order
    evts = [
        _make_event("run_1", EventType.REVIEW_VERDICT, "c1", offset_seconds=10),
        _make_event("run_1", EventType.TASK_DISPATCH, "c2", offset_seconds=0),
        _make_event("run_1", EventType.VERIFICATION_GATE, "c3", offset_seconds=5),
    ]
    summary = synth.synthesize("run_1", evts)
    assert summary.total_events == 3
    assert len(summary.steps) == 3
    # Steps must be in ascending timestamp order
    timestamps = [s.timestamp for s in summary.steps]
    assert timestamps == sorted(timestamps)
    # First step must be TASK_DISPATCH (offset=0)
    assert summary.steps[0].event_type == EventType.TASK_DISPATCH


def test_synthesize_final_verdict_passed() -> None:
    """Synthesizer sets final_verdict to PASSED on lifecycle COMPLETE state."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event("run_2", EventType.TASK_DISPATCH, "c1", offset_seconds=0),
        _make_event(
            "run_2",
            EventType.RUN_LIFECYCLE,
            "c2",
            payload={"state": "COMPLETE"},
            offset_seconds=5,
        ),
    ]
    summary = synth.synthesize("run_2", evts)
    assert summary.final_verdict == "PASSED"


def test_synthesize_final_verdict_failed() -> None:
    """Synthesizer sets final_verdict to FAILED on lifecycle FAILED state."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event(
            "run_3",
            EventType.RUN_LIFECYCLE,
            "c1",
            payload={"state": "FAILED"},
            offset_seconds=0,
        ),
    ]
    summary = synth.synthesize("run_3", evts)
    assert summary.final_verdict == "FAILED"


def test_synthesize_in_progress_verdict() -> None:
    """Synthesizer leaves final_verdict as IN_PROGRESS with no lifecycle terminal event."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event("run_4", EventType.TASK_DISPATCH, "c1", offset_seconds=0),
        _make_event("run_4", EventType.QUOTA_TELEMETRY, "c2", offset_seconds=1),
    ]
    summary = synth.synthesize("run_4", evts)
    assert summary.final_verdict == "IN_PROGRESS"


def test_synthesize_mixed_event_types_step_titles() -> None:
    """All EventType branches produce non-empty title and details."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event(
            "run_5",
            EventType.RUN_LIFECYCLE,
            "c1",
            payload={"state": "STARTED"},
            offset_seconds=0,
        ),
        _make_event(
            "run_5",
            EventType.TASK_DISPATCH,
            "c2",
            payload={"task_key": "tk1", "provider": "prov1", "topology": "hierarchical"},
            offset_seconds=1,
        ),
        _make_event(
            "run_5",
            EventType.QUOTA_TELEMETRY,
            "c3",
            payload={"provider": "prov1", "composite_headroom": 0.75, "reset_pressure": 0.2},
            offset_seconds=2,
        ),
        _make_event(
            "run_5",
            EventType.VERIFICATION_GATE,
            "c4",
            payload={"gate_name": "ruff", "status": "PASSED", "exit_code": 0},
            offset_seconds=3,
        ),
        _make_event(
            "run_5",
            EventType.REVIEW_VERDICT,
            "c5",
            payload={"reviewer": "claude", "verdict": "APPROVED"},
            offset_seconds=4,
        ),
        _make_event(
            "run_5",
            EventType.CONTEXT_PRESSURE,
            "c6",
            payload={"pressure_level": "HIGH", "action": "SUMMARIZE"},
            offset_seconds=5,
        ),
        _make_event(
            "run_5",
            EventType.CONTINUITY_TRANSITION,
            "c7",
            payload={"from_provider": "claude", "to_provider": "antigravity", "adjustment": "-1.5"},
            offset_seconds=6,
        ),
        _make_event(
            "run_5",
            EventType.STAGNATION_WARNING,
            "c8",
            payload={"repetitions": 3},
            offset_seconds=7,
        ),
    ]
    summary = synth.synthesize("run_5", evts)
    assert summary.total_events == 8
    for step in summary.steps:
        assert step.title, f"Empty title at step {step.step_index}"
        assert step.details, f"Empty details at step {step.step_index}"


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_headers() -> None:
    """render_markdown output contains expected run_id header and table headers."""
    synth = RunReplaySynthesizer()
    evts = [
        _make_event(
            "run_md",
            EventType.RUN_LIFECYCLE,
            "c1",
            payload={"state": "COMPLETE"},
            offset_seconds=0,
        ),
    ]
    summary = synth.synthesize("run_md", evts)
    md = synth.render_markdown(summary)
    assert "# Run Replay: `run_md`" in md
    assert "**Final Verdict:**" in md
    assert "| Step |" in md
    assert "| Timestamp |" in md
    assert "PASSED" in md


def test_render_markdown_empty_run() -> None:
    """render_markdown handles summary with no steps (empty run)."""
    synth = RunReplaySynthesizer()
    summary = synth.synthesize("run_empty2", [])
    md = synth.render_markdown(summary)
    assert "# Run Replay: `run_empty2`" in md
    assert "NO_EVENTS_RECORDED" in md
