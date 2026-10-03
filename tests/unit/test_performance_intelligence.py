"""Tests for performance telemetry, migration 0006, and performance intelligence."""

from __future__ import annotations

from pathlib import Path

from orkestra.kernel.performance import PerformanceIntelligenceEngine
from orkestra.schemas.evaluators import (
    ArtifactType,
    EvaluationReceipt,
    EvaluationStatus,
    EvaluationVerdict,
)
from orkestra.schemas.performance import TaskPerformanceRecord
from orkestra.store.db import Database
from orkestra.store.repo import Store


def test_migration_0006_and_repo_persistence(tmp_path: Path) -> None:
    store = Store(Database(tmp_path / "test_perf.db"))

    # 1. Record task performance
    perf = TaskPerformanceRecord(
        performance_id="perf-001",
        task_id="task-101",
        run_id="run-1",
        provider="claude",
        model="claude-3-5-sonnet",
        domain="software",
        pass_at_1=True,
        eventual_pass=True,
        repair_attempts=0,
        duration_s=14.2,
        input_tokens=5000,
        output_tokens=1200,
        cached_tokens=2500,
    )
    store.record_task_performance(perf)

    # List performance
    records = store.list_task_performance(provider="claude", domain="software")
    assert len(records) == 1
    assert records[0].performance_id == "perf-001"
    assert records[0].pass_at_1 is True

    # 2. Record evaluation receipt
    verdict = EvaluationVerdict(
        evaluator_name="evaluator.code.syntax",
        artifact_type=ArtifactType.CODE,
        status=EvaluationStatus.PASS,
        score=1.0,
        artifact_path="test.py",
        cryptographic_digest="a" * 64,
    )
    receipt = EvaluationReceipt(
        receipt_id="rcpt-001",
        task_id="task-101",
        verdicts=[verdict],
        overall_status=EvaluationStatus.PASS,
        chain_digest="b" * 64,
    )
    store.record_evaluation_receipt(receipt)

    fetched_receipt = store.get_evaluation_receipt("rcpt-001")
    assert fetched_receipt is not None
    assert fetched_receipt.receipt_id == "rcpt-001"
    assert fetched_receipt.overall_status == EvaluationStatus.PASS
    assert len(fetched_receipt.verdicts) == 1


def test_performance_intelligence_metrics_and_smoothing() -> None:
    engine = PerformanceIntelligenceEngine(store=None)

    # No data: should return neutral metrics
    neutral = engine.get_domain_metrics("codex", "software")
    assert neutral.sample_size == 0
    assert neutral.confidence == 0.0
    assert neutral.performance_multiplier == 1.0
    assert engine.calculate_routing_score_adjustment("codex", "software") == 0.0

    # Add 5 successful first-pass tasks
    for i in range(5):
        engine.record_task_outcome(
            TaskPerformanceRecord(
                performance_id=f"perf-{i}",
                task_id=f"task-{i}",
                run_id="run-1",
                provider="codex",
                model="gpt-4o",
                domain="software",
                pass_at_1=True,
                eventual_pass=True,
                repair_attempts=0,
                duration_s=10.0,
                input_tokens=2000,
                output_tokens=500,
                cached_tokens=1000,
            )
        )

    metrics = engine.get_domain_metrics("codex", "software")
    assert metrics.sample_size == 5
    # Laplace smoothing: (5 + 1) / (5 + 2) = 6/7 = ~0.8571
    assert metrics.first_pass_rate == round(6 / 7, 4)
    # Confidence: 5 / (5 + 5) = 0.5
    assert metrics.confidence == 0.5
    assert metrics.performance_multiplier > 1.0

    adjustment = engine.calculate_routing_score_adjustment("codex", "software")
    assert adjustment > 0.0
    assert adjustment <= 5.0

    explanation = engine.explain_metrics("codex", "software")
    assert "Provider 'codex'" in explanation
    assert "sample_size=5" in explanation


def test_poor_performance_penalty() -> None:
    engine = PerformanceIntelligenceEngine(store=None)

    # Add 4 tasks where all failed first-pass and required multiple repairs
    for i in range(4):
        engine.record_task_outcome(
            TaskPerformanceRecord(
                performance_id=f"fail-{i}",
                task_id=f"task-{i}",
                run_id="run-1",
                provider="antigravity",
                model="gemini-flash",
                domain="research",
                pass_at_1=False,
                eventual_pass=True,
                repair_attempts=3,
                duration_s=25.0,
                input_tokens=3000,
                output_tokens=800,
                cached_tokens=0,
            )
        )

    metrics = engine.get_domain_metrics("antigravity", "research")
    assert metrics.sample_size == 4
    # Laplace smoothing: (0 + 1) / (4 + 2) = 1/6 = ~0.1667
    assert metrics.first_pass_rate == round(1 / 6, 4)
    assert metrics.performance_multiplier < 1.0

    adjustment = engine.calculate_routing_score_adjustment("antigravity", "research")
    assert adjustment < 0.0
    assert adjustment >= -5.0


def test_resource_router_with_performance_engine() -> None:
    from orkestra.kernel.router import ResourceRouter
    from orkestra.schemas.common import TaskKind
    from orkestra.schemas.resource import ExecutionProfile, ProviderUsageSnapshot
    from orkestra.schemas.task import TaskSpec

    engine = PerformanceIntelligenceEngine(store=None)
    # Give codex 10 successful pass@1 tasks
    for i in range(10):
        engine.record_task_outcome(
            TaskPerformanceRecord(
                performance_id=f"p-{i}",
                task_id=f"t-{i}",
                run_id="run-1",
                provider="codex",
                model="gpt-4o",
                domain="software",
                pass_at_1=True,
                eventual_pass=True,
                repair_attempts=0,
                duration_s=5.0,
                input_tokens=1000,
                output_tokens=200,
            )
        )

    p_claude = ExecutionProfile(
        profile_id="claude-standard",
        provider="claude",
        adapter="claude",
        model="claude-3-5-sonnet",
        quality_rank=8,
        capabilities=["python", "implement"],
    )
    p_codex = ExecutionProfile(
        profile_id="codex-standard",
        provider="codex",
        adapter="codex",
        model="gpt-4o",
        quality_rank=8,  # Equal base quality rank
        capabilities=["python", "implement"],
    )

    router = ResourceRouter(profiles=[p_claude, p_codex], performance_engine=engine)
    spec = TaskSpec(
        key="task-test",
        title="Implement database query",
        description="Write SQL query for telemetry",
        kind=TaskKind.IMPLEMENT,
    )

    snapshots: dict[str, ProviderUsageSnapshot] = {}
    decision = router.select_best_profile(
        task_id="task-test",
        run_id="run-1",
        spec=spec,
        snapshots=snapshots,
    )

    # Codex should win due to performance intelligence bonus!
    assert decision.selected_profile == "codex-standard"
    assert any("performance_intelligence" in r for r in decision.reasons)
