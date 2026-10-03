"""Schemas for multi-domain artifact evaluation, verdicts, and cryptographic receipts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class ArtifactType(StrEnum):
    """Classification of output artifacts subject to evaluation."""

    CODE = "code"
    TEST = "test"
    DOCUMENT = "document"
    RESEARCH = "research"
    DATA = "data"
    MEDIA = "media"
    CUSTOM = "custom"


class EvaluationStatus(StrEnum):
    """Outcome status of an artifact evaluation."""

    PASS = "PASS"  # nosec B105 # noqa: S105
    FAIL = "FAIL"
    NEEDS_REVISION = "NEEDS_REVISION"
    SKIPPED = "SKIPPED"


class EvaluationVerdict(BaseModel):
    """The outcome of evaluating a single artifact against a domain standard."""

    model_config = ConfigDict(extra="forbid")

    evaluator_name: str
    artifact_type: ArtifactType
    status: EvaluationStatus
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    artifact_path: str = ""
    issues: list[str] = Field(default_factory=list)
    remedies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    cryptographic_digest: str = ""  # SHA-256 hash of artifact + findings
    timestamp: datetime = Field(default_factory=utc_now)


class EvaluationReceipt(BaseModel):
    """Cryptographically chained receipt recording a bundle of evaluated artifacts."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    task_id: str
    verdicts: list[EvaluationVerdict]
    overall_status: EvaluationStatus
    chain_digest: str  # Hash chain linking all verdicts
    created_at: datetime = Field(default_factory=utc_now)
