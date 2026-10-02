"""Tests for Phase B resource models, schema migrations, and Store persistence."""

from __future__ import annotations

from orkestra.schemas.common import utc_now
from orkestra.schemas.resource import (
    ExecutionProfile,
    HandoffCheckpoint,
    LogicalDirectorState,
    ProviderHealth,
    ProviderUsageSnapshot,
    QuotaConfidence,
    QuotaSource,
    QuotaWindow,
    ResourceState,
    RoutingDecision,
)
from orkestra.store import Database, Store


def test_resource_schemas_instantiation() -> None:
    now = utc_now().isoformat()
    window = QuotaWindow(
        provider="claude",
        window_kind="5h",
        remaining_ratio=0.62,
        reset_at=now,
        source=QuotaSource.OFFICIAL_CLI,
        confidence=QuotaConfidence.EXACT,
        observed_at=now,
    )
    assert window.provider == "claude"
    assert window.remaining_ratio == 0.62

    snapshot = ProviderUsageSnapshot(
        provider="claude",
        health=ProviderHealth.HEALTHY,
        state=ResourceState.ACTIVE,
        windows=[window],
        observed_at=now,
    )
    assert snapshot.provider == "claude"
    assert len(snapshot.windows) == 1

    profile = ExecutionProfile(
        profile_id="claude-opus-high",
        provider="claude",
        adapter="claude_code",
        model="claude-3-7-sonnet",
        quality_rank=9,
        speed_rank=6,
    )
    assert profile.quality_rank == 9

    routing = RoutingDecision(
        decision_id="dec_001",
        run_id="run_001",
        task_id="task_001",
        selected_profile="claude-opus-high",
        score=0.85,
        reasons=["task_fit_high", "quota_abundant"],
        timestamp=now,
    )
    assert routing.score == 0.85

    handoff = HandoffCheckpoint(
        handoff_id="hdf_001",
        run_id="run_001",
        task_id="task_001",
        attempt_id="att_001",
        worktree_path="/tmp/ws",
        base_commit="abc",
        current_head="def",
        prior_agent="antigravity",
        successor_agent="claude",
        reason="QUOTA_EXHAUSTED",
        timestamp=now,
    )
    assert handoff.reason == "QUOTA_EXHAUSTED"

    director = LogicalDirectorState(
        director_id="dir_001",
        run_id="run_001",
        active_engine_profile="claude-opus-high",
        project_goal="Evolve Orkestra Command Center",
        updated_at=now,
    )
    assert director.project_goal == "Evolve Orkestra Command Center"


def test_store_resource_persistence() -> None:
    db = Database(":memory:")
    try:
        store = Store(db)

        # Check migration version is 5
        row = db.query_one("SELECT version FROM schema_version")
        assert row is not None
        assert int(row["version"]) == 5

        now = utc_now().isoformat()
        snap = ProviderUsageSnapshot(
            provider="codex",
            health=ProviderHealth.HEALTHY,
            state=ResourceState.IDLE,
            windows=[
                QuotaWindow(
                    provider="codex",
                    window_kind="weekly",
                    remaining_ratio=0.31,
                    source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                    confidence=QuotaConfidence.EXACT,
                    observed_at=now,
                )
            ],
            observed_at=now,
        )
        row_id = store.add_provider_snapshot(snap)
        assert row_id > 0

        latest = store.latest_provider_snapshots()
        assert "codex" in latest
        assert latest["codex"].windows[0].remaining_ratio == 0.31

        # Test RoutingDecision
        routing = RoutingDecision(
            decision_id="dec_test",
            run_id="run_100",
            task_id="task_100",
            selected_profile="codex-sol-high",
            score=0.92,
            reasons=["scarcity_avoidance"],
            timestamp=now,
        )
        store.add_routing_decision(routing)
        decisions = store.routing_decisions_for_run("run_100")
        assert len(decisions) == 1
        assert decisions[0].selected_profile == "codex-sol-high"

        latest_dec = store.latest_routing_decision("run_100", "task_100")
        assert latest_dec is not None
        assert latest_dec.score == 0.92

        # Test HandoffCheckpoint
        handoff = HandoffCheckpoint(
            handoff_id="hdf_test",
            run_id="run_100",
            task_id="task_100",
            attempt_id="att_100",
            worktree_path="/ws/path",
            base_commit="sha1",
            current_head="sha2",
            prior_agent="antigravity",
            successor_agent="codex",
            reason="QUOTA_EXHAUSTED",
            timestamp=now,
        )
        store.add_handoff_checkpoint(handoff)
        handoffs = store.handoffs_for_task("run_100", "task_100")
        assert len(handoffs) == 1
        assert handoffs[0].prior_agent == "antigravity"

        # Test LogicalDirectorState
        director_state = LogicalDirectorState(
            director_id="dir_test",
            run_id="run_100",
            active_engine_profile="codex-sol-high",
            project_goal="Test Goal",
            architecture_notes=["note 1"],
            updated_at=now,
        )
        store.save_director_state(director_state)
        retrieved_dir = store.get_director_state("run_100")
        assert retrieved_dir is not None
        assert retrieved_dir.project_goal == "Test Goal"
    finally:
        db.close()
