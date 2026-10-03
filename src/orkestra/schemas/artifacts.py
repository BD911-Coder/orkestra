"""Typed canonical execution artifacts for task lifecycle stages and gate governance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import TaskKind, utc_now


class ReviewVerdict(StrEnum):
    """Independent review verdict outcomes."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"


class ReviewSeverity(StrEnum):
    """Severity classification for review findings."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewFinding(BaseModel):
    """An individual finding discovered during independent code or security review."""

    model_config = ConfigDict(extra="forbid")

    file_path: str
    line: int | None = None
    severity: ReviewSeverity
    title: str
    description: str
    suggested_fix: str | None = None


class BaseExecutionArtifact(BaseModel):
    """Base model for all canonical stage execution artifacts."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    task_id: str
    agent_id: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by planning tasks."""

    objectives: list[str]
    decomposed_tasks: list[dict[str, Any]] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_effort: str = "medium"


class ArchitectureArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by architecture and system design tasks."""

    system_summary: str
    components: list[str] = Field(default_factory=list)
    interface_contracts: list[str] = Field(default_factory=list)
    security_considerations: list[str] = Field(default_factory=list)


class ImplementationArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by implementation and bug fixing tasks."""

    summary: str
    changed_files: list[str] = Field(default_factory=list)
    worktree_path: str
    commit_sha: str | None = None
    diff_stat: str = ""


class ReviewArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by independent code review tasks."""

    reviewer_id: str
    verdict: ReviewVerdict
    highest_severity: ReviewSeverity = ReviewSeverity.NONE
    findings: list[ReviewFinding] = Field(default_factory=list)
    comments: str = ""


class VerificationArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by deterministic verification gates."""

    commands_executed: list[str] = Field(default_factory=list)
    exit_codes: list[int] = Field(default_factory=list)
    all_passed: bool
    environment_fingerprint: str
    details: str = ""


class SecurityReviewArtifact(BaseExecutionArtifact):
    """Canonical artifact produced by security auditing tasks."""

    audited_files: list[str] = Field(default_factory=list)
    violations_detected: int = 0
    passed: bool
    details: str = ""


class HandoffArtifact(BaseExecutionArtifact):
    """Canonical artifact produced during mid-task or session handoffs."""

    mission: str
    current_state: str
    worktree_path: str
    is_worktree_clean: bool
    uncommitted_files: list[str] = Field(default_factory=list)
    last_verified_commit: str | None = None
    exact_next_action: str
    failure_history: list[str] = Field(default_factory=list)


CANONICAL_TASK_ARTIFACT_MAP: dict[TaskKind, type[BaseExecutionArtifact]] = {
    TaskKind.PLAN: PlanningArtifact,
    TaskKind.IMPLEMENT: ImplementationArtifact,
    TaskKind.TEST: ImplementationArtifact,
    TaskKind.DEBUG: ImplementationArtifact,
    TaskKind.REVIEW: ReviewArtifact,
    TaskKind.RESEARCH: PlanningArtifact,
    TaskKind.DOCUMENT: PlanningArtifact,
}
