"""Unit tests for Phase M: typed canonical artifacts and checkpoint governance."""

from __future__ import annotations

import tempfile
from pathlib import Path

from orkestra.kernel.artifacts import ArtifactValidator
from orkestra.kernel.checkpoints import AtomicCheckpointManager
from orkestra.schemas.artifacts import (
    ImplementationArtifact,
    PlanningArtifact,
    ReviewVerdict,
)
from orkestra.schemas.common import TaskKind
from orkestra.schemas.resource import RoutingDecision


class TestTypedArtifactsAndValidator:
    def test_planning_artifact_validates(self) -> None:
        validator = ArtifactValidator()
        artifact = PlanningArtifact(
            artifact_id="art_plan_1",
            task_id="task_1",
            agent_id="claude",
            objectives=["Refactor authentication module"],
            decomposed_tasks=[{"task": "subtask_1", "kind": "implement"}],
            prerequisites=[],
        )
        ok, violations = validator.validate_artifact_for_task(TaskKind.PLAN, artifact)
        assert ok is True
        assert len(violations) == 0

    def test_mismatched_artifact_rejected(self) -> None:
        validator = ArtifactValidator()
        artifact = PlanningArtifact(
            artifact_id="art_plan_1",
            task_id="task_1",
            agent_id="claude",
            objectives=["Implement feature"],
        )
        ok, violations = validator.validate_artifact_for_task(TaskKind.IMPLEMENT, artifact)
        assert ok is False
        assert any("expects artifact 'ImplementationArtifact'" in v for v in violations)

    def test_implementation_artifact_and_worktree_files(self) -> None:
        validator = ArtifactValidator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            worktree = Path(tmp_dir)
            (worktree / "src").mkdir()
            (worktree / "src" / "main.py").write_text("print('hello')", encoding="utf-8")

            # Case 1: All files exist
            artifact = ImplementationArtifact(
                artifact_id="art_impl_1",
                task_id="task_1",
                agent_id="codex",
                summary="Implemented main.py",
                changed_files=["src/main.py"],
                worktree_path=str(worktree),
            )
            ok, violations = validator.can_task_complete(
                task_kind=TaskKind.IMPLEMENT,
                artifact=artifact,
                verification_passed=True,
                review_verdict=ReviewVerdict.APPROVED,
                worktree_root=worktree,
            )
            assert ok is True

            # Case 2: Declared file missing
            bad_artifact = ImplementationArtifact(
                artifact_id="art_impl_2",
                task_id="task_1",
                agent_id="codex",
                summary="Implemented missing file",
                changed_files=["src/missing.py"],
                worktree_path=str(worktree),
            )
            ok, violations = validator.can_task_complete(
                task_kind=TaskKind.IMPLEMENT,
                artifact=bad_artifact,
                verification_passed=True,
                review_verdict=ReviewVerdict.APPROVED,
                worktree_root=worktree,
            )
            assert ok is False
            assert any("Declared implementation files do not exist" in v for v in violations)

    def test_task_cannot_complete_without_passed_verification(self) -> None:
        validator = ArtifactValidator()
        artifact = ImplementationArtifact(
            artifact_id="art_impl_3",
            task_id="task_1",
            agent_id="codex",
            summary="Bugfix",
            changed_files=[],
            worktree_path=".",
        )
        ok, violations = validator.can_task_complete(
            task_kind=TaskKind.IMPLEMENT,
            artifact=artifact,
            verification_passed=False,
            review_verdict=ReviewVerdict.APPROVED,
        )
        assert ok is False
        assert any("verification gates are failing" in v for v in violations)

    def test_task_cannot_complete_without_approved_review(self) -> None:
        validator = ArtifactValidator()
        artifact = ImplementationArtifact(
            artifact_id="art_impl_4",
            task_id="task_1",
            agent_id="codex",
            summary="Feature A",
            changed_files=[],
            worktree_path=".",
        )
        # Changes requested
        ok, violations = validator.can_task_complete(
            task_kind=TaskKind.IMPLEMENT,
            artifact=artifact,
            verification_passed=True,
            review_verdict=ReviewVerdict.CHANGES_REQUESTED,
        )
        assert ok is False
        assert any("Independent review has not approved" in v for v in violations)


class TestAtomicCheckpointManager:
    def test_atomic_write_and_history_archiving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            chk_dir = Path(tmp_dir) / "checkpoints"
            manager = AtomicCheckpointManager(chk_dir)

            # Save v1
            v1 = manager.save_checkpoint("run_100", "planning", {"stage": "plan", "steps": 3})
            assert v1.version == 1
            assert (chk_dir / "checkpoint_run_100.json").is_file()

            latest = manager.load_latest_checkpoint("run_100")
            assert latest is not None
            assert latest.version == 1
            assert latest.stage == "planning"

            # Save v2 (should archive v1 into history/)
            v2 = manager.save_checkpoint("run_100", "implementation", {"stage": "impl", "files": 2})
            assert v2.version == 2

            history = manager.list_history("run_100")
            assert len(history) == 2
            assert history[0].version == 1
            assert history[1].version == 2

            # Rollback to v1
            rb = manager.rollback("run_100", target_version=1)
            assert rb is not None
            assert rb.version == 3  # New atomic checkpoint with v1's data
            assert rb.data["stage"] == "plan"


class TestDecisionLedgerRevisions:
    def test_routing_decision_revisions(self) -> None:
        d1 = RoutingDecision(
            decision_id="dec_001",
            run_id="run_100",
            task_id="task_1",
            selected_profile="claude-code",
            alternatives=["codex-cli"],
            score=8.5,
            reasons=["High task fitness"],
            timestamp="2026-10-03T05:00:00Z",
            revision_number=1,
        )
        assert d1.revision_number == 1
        assert d1.supersedes_decision_id is None

        # Revised decision
        d2 = RoutingDecision(
            decision_id="dec_002",
            run_id="run_100",
            task_id="task_1",
            selected_profile="codex-cli",
            alternatives=["claude-code"],
            score=9.0,
            reasons=["Claude quota depleted; failover to Codex"],
            timestamp="2026-10-03T05:05:00Z",
            supersedes_decision_id="dec_001",
            revision_number=2,
            raw_factors={"quota": 0.2, "fitness": 0.9},
        )
        assert d2.revision_number == 2
        assert d2.supersedes_decision_id == "dec_001"
        assert d2.raw_factors["quota"] == 0.2
