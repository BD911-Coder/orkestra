"""Artifact validation and task completion contracts enforced by the deterministic kernel."""

from __future__ import annotations

from pathlib import Path

from orkestra.schemas.artifacts import (
    CANONICAL_TASK_ARTIFACT_MAP,
    BaseExecutionArtifact,
    ImplementationArtifact,
    ReviewArtifact,
    ReviewVerdict,
)
from orkestra.schemas.common import TaskKind


class ArtifactValidationError(ValueError):
    """Raised when an execution artifact fails schema or physical integrity checks."""


class ArtifactValidator:
    """Validates that tasks produce canonical typed artifacts and satisfy completion contracts."""

    def validate_artifact_for_task(
        self,
        task_kind: TaskKind,
        artifact: BaseExecutionArtifact,
    ) -> tuple[bool, list[str]]:
        """Verify that an artifact matches the expected class and contract for the task kind."""
        expected_type = CANONICAL_TASK_ARTIFACT_MAP.get(task_kind)
        violations: list[str] = []

        if expected_type is None:
            return True, []

        if not isinstance(artifact, expected_type):
            violations.append(
                f"Task kind '{task_kind.value}' expects artifact '{expected_type.__name__}', "
                f"got '{type(artifact).__name__}'"
            )
            return False, violations

        # Specific field validations
        if isinstance(artifact, ImplementationArtifact):
            if not artifact.summary.strip():
                violations.append("ImplementationArtifact requires a non-empty summary")
            if not artifact.worktree_path:
                violations.append("ImplementationArtifact requires an explicit worktree_path")

        elif isinstance(artifact, ReviewArtifact):
            if not artifact.reviewer_id.strip():
                violations.append("ReviewArtifact requires an explicit reviewer_id")
            if artifact.verdict == ReviewVerdict.CHANGES_REQUESTED and not artifact.findings:
                violations.append("ReviewArtifact with CHANGES_REQUESTED must include findings")

        return len(violations) == 0, violations

    def verify_files_exist_in_worktree(
        self,
        worktree_root: Path,
        file_paths: list[str],
    ) -> tuple[bool, list[str]]:
        """Verify that modified files declared by an artifact physically exist on disk."""
        missing: list[str] = []
        for rel_path in file_paths:
            full_path = (worktree_root / rel_path).resolve()
            # Ensure no escape outside worktree
            try:
                full_path.relative_to(worktree_root.resolve())
            except ValueError:
                missing.append(f"{rel_path} (escapes worktree boundary)")
                continue

            if not full_path.exists():
                missing.append(rel_path)

        return len(missing) == 0, missing

    def can_task_complete(
        self,
        task_kind: TaskKind,
        artifact: BaseExecutionArtifact | None,
        verification_passed: bool,
        review_verdict: ReviewVerdict | None = None,
        worktree_root: Path | None = None,
    ) -> tuple[bool, list[str]]:
        """Determine whether a task can transition to COMPLETED.

        Enforces:
        1. An expected canonical artifact must exist and validate.
        2. If files were modified, they must exist on disk in the worktree.
        3. Deterministic verification gates must have passed (for implementation/test tasks).
        4. Independent review must be approved (for implementation tasks).
        """
        reasons: list[str] = []

        # 1. Artifact check
        if artifact is None:
            reasons.append(
                f"Task cannot complete without canonical artifact for kind '{task_kind.value}'"
            )
            return False, reasons

        valid, violations = self.validate_artifact_for_task(task_kind, artifact)
        if not valid:
            reasons.extend(violations)

        # 2. File existence check for implementation
        if isinstance(artifact, ImplementationArtifact) and worktree_root:
            files_ok, missing = self.verify_files_exist_in_worktree(
                worktree_root, artifact.changed_files
            )
            if not files_ok:
                reasons.append(f"Declared implementation files do not exist: {', '.join(missing)}")

        # 3. Verification gate check
        if (
            task_kind in (TaskKind.IMPLEMENT, TaskKind.TEST, TaskKind.DEBUG)
            and not verification_passed
        ):
            reasons.append(
                "Task cannot complete while deterministic verification gates are failing"
            )

        # 4. Review check
        if task_kind == TaskKind.IMPLEMENT:
            if review_verdict is None:
                reasons.append("Task requires an independent review verdict before completion")
            elif review_verdict != ReviewVerdict.APPROVED:
                msg = (
                    "Independent review has not approved the task "
                    f"(verdict: {review_verdict.value})"
                )
                reasons.append(msg)

        return len(reasons) == 0, reasons
