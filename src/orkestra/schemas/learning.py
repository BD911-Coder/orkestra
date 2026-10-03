"""Schemas for continuous learning, pattern observations, hypotheses, and candidate policies."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class PolicyCandidateState(StrEnum):
    """Lifecycle states for empirically learned candidate policies."""

    EXPERIMENTAL = "experimental"
    SHADOW = "shadow"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class PatternObservation(BaseModel):
    """Atomic recorded observation of an execution pattern or defect tendency."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    task_id: str
    provider: str
    domain: str
    trigger: str  # e.g., "high_complexity_refactor", "untyped_external_api"
    evidence: str
    outcome: str  # "success", "failure", "repair_loop", "timeout"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)


class PolicyHypothesis(BaseModel):
    """Structured hypothesis inferred from clustered pattern observations."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    title: str
    description: str
    supporting_observations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_rule: str
    target_domain: str = "software"
    target_provider: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CandidatePolicy(BaseModel):
    """A formal policy configuration delta proposed by the continuous learning engine."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    hypothesis_id: str
    title: str
    state: PolicyCandidateState = PolicyCandidateState.EXPERIMENTAL
    rule_type: str = "routing_gate"
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_security_compliant: bool = True
    shadow_eval_score: float = 0.0
    shadow_eval_tasks: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    promoted_at: datetime | None = None
    rollback_reason: str = ""
