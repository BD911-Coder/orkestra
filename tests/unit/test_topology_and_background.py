"""Unit tests for Phase P Swarm Topology Intelligence, Nesting Limits, and Background Backlog."""

from __future__ import annotations

from orkestra.director.background import BackgroundBacklogManager
from orkestra.kernel.topology import TopologyIntelligenceEngine
from orkestra.schemas.topology import BackgroundWorkTask, SwarmTopology


def test_subagent_nesting_limits() -> None:
    """Verifies deterministic enforcement of subagent nesting depth and fleet concurrency."""
    engine = TopologyIntelligenceEngine(
        max_nested_workers=4,
        max_total_concurrent=8,
        max_subagent_depth=2,
    )

    # 1. Allowed dispatch
    ok, err = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=2, total_concurrent=4
    )
    assert ok is True
    assert err is None

    # 2. Depth limit exceeded (depth 2 >= max 2)
    ok_depth, err_depth = engine.validate_subagent_dispatch(
        current_depth=2, current_nested_workers=1, total_concurrent=3
    )
    assert ok_depth is False
    assert err_depth is not None
    assert "Subagent nesting depth limit reached" in err_depth

    # 3. Max nested workers exceeded (4 >= max 4)
    ok_nested, err_nested = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=4, total_concurrent=5
    )
    assert ok_nested is False
    assert err_nested is not None
    assert "Max nested workers reached" in err_nested

    # 4. Total concurrent fleet exceeded (8 >= max 8)
    ok_tot, err_tot = engine.validate_subagent_dispatch(
        current_depth=1, current_nested_workers=2, total_concurrent=8
    )
    assert ok_tot is False
    assert err_tot is not None
    assert "Max total concurrent agents reached" in err_tot


def test_parallel_efficiency_calculation() -> None:
    """Detects genuine speedup vs wasteful 'false parallelism' coordination overhead."""
    engine = TopologyIntelligenceEngine()

    # 1. Genuine speedup
    good_metrics = engine.calculate_parallel_efficiency(
        seq_sec=120.0,
        par_sec=35.0,
        worker_count=4,
        seq_tokens=10_000,
        par_tokens=12_500,
    )
    assert good_metrics.speedup == 3.43
    assert good_metrics.parallel_efficiency == 0.86
    assert good_metrics.is_false_parallelism is False
    assert "PROCEED_PARALLEL" in good_metrics.recommendation

    # 2. False parallelism: 4 workers burning 4x tokens for negligible speedup
    wasteful_metrics = engine.calculate_parallel_efficiency(
        seq_sec=100.0,
        par_sec=96.0,
        worker_count=4,
        seq_tokens=10_000,
        par_tokens=38_000,
    )
    assert wasteful_metrics.speedup == 1.04
    assert wasteful_metrics.compute_multiplier == 3.8
    assert wasteful_metrics.is_false_parallelism is True
    assert "COLLAPSE_TO_SEQUENTIAL" in wasteful_metrics.recommendation


def test_recommend_topology() -> None:
    """Recommends appropriate topology based on complexity and resource availability."""
    engine = TopologyIntelligenceEngine()

    # Severe scarcity forces Star topology
    assert (
        engine.recommend_topology(complexity=6, available_providers=3, quota_scarcity=0.85)
        == SwarmTopology.STAR
    )

    # Low complexity uses simple Hierarchical tree
    assert (
        engine.recommend_topology(complexity=2, available_providers=2, quota_scarcity=0.10)
        == SwarmTopology.HIERARCHICAL
    )

    # High complexity with multi-provider availability uses Peer Mesh
    assert (
        engine.recommend_topology(complexity=9, available_providers=3, quota_scarcity=0.20)
        == SwarmTopology.MESH
    )

    # General case uses Adaptive
    assert (
        engine.recommend_topology(complexity=5, available_providers=2, quota_scarcity=0.30)
        == SwarmTopology.ADAPTIVE
    )


def test_background_backlog_selection() -> None:
    """Dispatches maintenance tasks to absorb expiring quota allowance."""
    mgr = BackgroundBacklogManager(reset_pressure_threshold=0.40)

    backlog = [
        BackgroundWorkTask(task_id="bg_1", title="Low task", priority=1),
        BackgroundWorkTask(task_id="bg_2", title="High task", priority=5),
        BackgroundWorkTask(
            task_id="bg_3",
            title="AGY specific task",
            priority=10,
            preferred_provider="agy",
        ),
    ]

    # 1. Quota reset pressure is low -> Do not absorb
    task_low = mgr.select_background_task(
        backlog=backlog,
        provider="claude",
        provider_reset_pressure=0.20,
    )
    assert task_low is None

    # 2. Concurrency saturated -> Do not absorb
    task_saturated = mgr.select_background_task(
        backlog=backlog,
        provider="claude",
        provider_reset_pressure=0.80,
        current_concurrency=4,
        max_concurrency=4,
    )
    assert task_saturated is None

    # 3. High reset pressure on claude -> Selects highest priority compatible task ("bg_2")
    task_selected = mgr.select_background_task(
        backlog=backlog,
        provider="claude",
        provider_reset_pressure=0.75,
        current_concurrency=1,
    )
    assert task_selected is not None
    assert task_selected.task_id == "bg_2"

    # 4. High reset pressure on agy -> Selects preferred high priority task ("bg_3")
    task_agy = mgr.select_background_task(
        backlog=backlog,
        provider="agy",
        provider_reset_pressure=0.60,
        current_concurrency=0,
    )
    assert task_agy is not None
    assert task_agy.task_id == "bg_3"
