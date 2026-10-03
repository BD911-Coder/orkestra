"""Unit tests for Phase N Multi-Window Quota Evaluation and Scarcity Capping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from orkestra.kernel.resources_v2 import MultiWindowQuotaEvaluator
from orkestra.kernel.router import ResourceRouter
from orkestra.schemas.common import TaskKind
from orkestra.schemas.resources_v2 import (
    MultiWindowQuotaProfile,
    QuotaConfidence,
    QuotaWindowStatus,
    QuotaWindowType,
)
from orkestra.schemas.task import TaskSpec


def test_unknown_not_abundant_penalty() -> None:
    """Verifies that UNKNOWN quota confidence receives an uncertainty penalty, NOT 100% headroom."""
    evaluator = MultiWindowQuotaEvaluator()
    now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

    # Window with 100% remaining but UNKNOWN confidence
    status = QuotaWindowStatus(
        window_type=QuotaWindowType.DAILY,
        used=0.0,
        limit=100.0,
        remaining=100.0,
        reset_at=now + timedelta(hours=12),
        confidence=QuotaConfidence.UNKNOWN,
        burn_velocity_per_hour=0.0,
        headroom_ratio=1.0,
        reset_pressure=0.0,
    )

    profile = evaluator.evaluate_profile("provider_x", [status], current_time=now)
    assert profile.effective_confidence == QuotaConfidence.UNKNOWN
    # OmniRoute defect would treat this as 1.0 (abundant). Orkestra penalizes to 0.35
    assert profile.composite_headroom == 0.35


def test_long_window_scarcity_caps_short_window_abundance() -> None:
    """Long-window scarcity strictly caps short-window abundance."""
    evaluator = MultiWindowQuotaEvaluator()
    now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

    # 5h window is 90% free (abundance)
    short_window = QuotaWindowStatus(
        window_type=QuotaWindowType.FIVE_HOUR,
        used=10.0,
        limit=100.0,
        remaining=90.0,
        reset_at=now + timedelta(hours=2),
        confidence=QuotaConfidence.EXACT,
        headroom_ratio=0.9,
    )

    # Monthly window is 95% depleted (only 5% remaining headroom)
    long_window = QuotaWindowStatus(
        window_type=QuotaWindowType.MONTHLY,
        used=950.0,
        limit=1000.0,
        remaining=50.0,
        reset_at=now + timedelta(days=15),
        confidence=QuotaConfidence.EXACT,
        headroom_ratio=0.05,
    )

    profile = evaluator.evaluate_profile("claude", [short_window, long_window], current_time=now)
    # The composite headroom must be capped by the monthly scarcity (0.05), NOT 0.90!
    assert profile.composite_headroom == 0.05
    assert profile.effective_confidence == QuotaConfidence.EXACT


def test_reset_pressure_calculation() -> None:
    """Urgency rises when quota window resets soon with remaining allowance."""
    evaluator = MultiWindowQuotaEvaluator()
    now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

    # 1. 80% remaining, resets in 30 minutes (0.5 hours) of a 5h window
    expiring_soon = QuotaWindowStatus(
        window_type=QuotaWindowType.FIVE_HOUR,
        used=20.0,
        limit=100.0,
        remaining=80.0,
        reset_at=now + timedelta(minutes=30),
        confidence=QuotaConfidence.EXACT,
    )
    profile1 = evaluator.evaluate_profile("agy", [expiring_soon], current_time=now)
    assert profile1.composite_reset_pressure > 0.5

    # 2. 80% remaining, but resets in 4.5 hours (early in window)
    not_expiring_soon = QuotaWindowStatus(
        window_type=QuotaWindowType.FIVE_HOUR,
        used=20.0,
        limit=100.0,
        remaining=80.0,
        reset_at=now + timedelta(hours=4, minutes=30),
        confidence=QuotaConfidence.EXACT,
    )
    profile2 = evaluator.evaluate_profile("agy", [not_expiring_soon], current_time=now)
    assert profile2.composite_reset_pressure < 0.1


def test_burn_velocity_and_throttling_recommendation() -> None:
    """Burn velocity exceeding remaining quota before reset triggers throttle recommendation."""
    evaluator = MultiWindowQuotaEvaluator()
    now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

    # Used 80 units, 20 left. Burn velocity 40 units/hour.
    # Projected exhaustion in 20 / 40 = 0.5 hours.
    # Reset is in 2 hours -> will run out 1.5 hours BEFORE reset!
    window = QuotaWindowStatus(
        window_type=QuotaWindowType.FIVE_HOUR,
        used=80.0,
        limit=100.0,
        remaining=20.0,
        reset_at=now + timedelta(hours=2),
        confidence=QuotaConfidence.EXACT,
        burn_velocity_per_hour=40.0,
    )

    profile = evaluator.evaluate_profile("codex", [window], current_time=now)
    assert profile.throttle_recommended is True
    assert profile.projected_exhaustion_hours == 0.5


def test_router_integration_with_v2_profile() -> None:
    """ResourceRouter integrates V2 multi-window profiles into ranking and decision reasons."""
    router = ResourceRouter()
    spec = TaskSpec(
        key="T1",
        title="Implement feature",
        description="Write code",
        kind=TaskKind.IMPLEMENT,
    )

    # Create profile with high reset pressure
    mw_profile = MultiWindowQuotaProfile(
        provider="claude",
        windows={},
        composite_headroom=0.8,
        composite_reset_pressure=0.75,
        effective_confidence=QuotaConfidence.EXACT,
        throttle_recommended=False,
    )

    decision = router.select_best_profile(
        task_id="task_test_mw",
        run_id="run_1",
        spec=spec,
        snapshots={},
        multi_window_profiles={"claude": mw_profile},
    )

    assert decision.selected_profile.startswith("claude")
    assert any("v2_reset_pressure_bonus" in r for r in decision.reasons)
