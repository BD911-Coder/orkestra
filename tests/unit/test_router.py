"""Unit tests for the Deterministic Adaptive Resource Router."""

from __future__ import annotations

from orkestra.kernel.router import ResourceRouter
from orkestra.schemas.common import TaskKind, utc_now
from orkestra.schemas.resource import (
    ProviderHealth,
    ProviderUsageSnapshot,
    QuotaConfidence,
    QuotaSource,
    QuotaWindow,
)
from orkestra.schemas.task import TaskSpec


def test_scenario_1_reset_pressure_boosts_preference() -> None:
    now = utc_now().isoformat()
    router = ResourceRouter()

    # Claude reset approaching in 30 minutes with 75% remaining
    claude_snap = ProviderUsageSnapshot(
        provider="claude",
        health=ProviderHealth.HEALTHY,
        windows=[
            QuotaWindow(
                provider="claude",
                window_kind="5h",
                remaining_ratio=0.75,
                seconds_to_reset=1800.0,
                source=QuotaSource.OFFICIAL_CLI,
                confidence=QuotaConfidence.EXACT,
                observed_at=now,
            )
        ],
        observed_at=now,
    )

    # Codex reset far away in 5 days with 20% remaining
    codex_snap = ProviderUsageSnapshot(
        provider="codex",
        health=ProviderHealth.HEALTHY,
        windows=[
            QuotaWindow(
                provider="codex",
                window_kind="weekly",
                remaining_ratio=0.20,
                seconds_to_reset=432000.0,
                source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                confidence=QuotaConfidence.EXACT,
                observed_at=now,
            )
        ],
        observed_at=now,
    )

    snapshots = {"claude": claude_snap, "codex": codex_snap}
    spec = TaskSpec(key="t1", kind=TaskKind.IMPLEMENT, title="Implement Feature X")

    decision = router.select_best_profile("t1", "r1", spec, snapshots)
    assert decision.selected_profile.startswith("claude")
    assert decision.waste_risk > 0.0
    assert any("waste_risk_bonus" in r for r in decision.reasons)


def test_scenario_2_long_window_scarcity_overrides_short_window() -> None:
    now = utc_now().isoformat()
    router = ResourceRouter()

    # Claude 5-hour limit: 80% remaining, BUT weekly limit: 3% remaining!
    claude_snap = ProviderUsageSnapshot(
        provider="claude",
        health=ProviderHealth.HEALTHY,
        windows=[
            QuotaWindow(
                provider="claude",
                window_kind="5h",
                remaining_ratio=0.80,
                seconds_to_reset=3600.0,
                observed_at=now,
            ),
            QuotaWindow(
                provider="claude",
                window_kind="weekly",
                remaining_ratio=0.03,  # Bottleneck!
                seconds_to_reset=345600.0,
                observed_at=now,
            ),
        ],
        observed_at=now,
    )

    # Antigravity Pro abundant
    antigravity_snap = ProviderUsageSnapshot(
        provider="antigravity",
        health=ProviderHealth.HEALTHY,
        windows=[
            QuotaWindow(
                provider="antigravity",
                window_kind="daily",
                remaining_ratio=0.85,
                seconds_to_reset=43200.0,
                observed_at=now,
            )
        ],
        observed_at=now,
    )

    # Codex exhausted
    codex_snap = ProviderUsageSnapshot(
        provider="codex",
        health=ProviderHealth.EXHAUSTED,
        observed_at=now,
    )

    snapshots = {"claude": claude_snap, "antigravity": antigravity_snap, "codex": codex_snap}
    spec = TaskSpec(key="t2", kind=TaskKind.IMPLEMENT, title="Implement Routine Task")

    decision = router.select_best_profile("t2", "r1", spec, snapshots)
    # Claude should be penalized due to weekly scarcity bottleneck
    assert not decision.selected_profile.startswith("claude")
    assert decision.selected_profile.startswith("antigravity")


def test_quality_floor_enforcement() -> None:
    router = ResourceRouter()

    snapshots: dict[str, ProviderUsageSnapshot] = {}

    # High-risk task requires quality floor = 7
    spec = TaskSpec(key="t3", kind=TaskKind.INTEGRATE, title="Complex Core Integration")

    decision = router.select_best_profile("t3", "r1", spec, snapshots)

    # Low quality profile (e.g. antigravity-flash-medium with quality=6) must be excluded
    profile = router.get_profile(decision.selected_profile)
    assert profile is not None
    assert profile.quality_rank >= 7
