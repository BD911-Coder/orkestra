"""Pydantic schemas for Outcome Memory, Counterfactual Analysis, and Failure Classification."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class TaskOutcomeRecord(BaseModel):
    """Historical execution record used for similar-task retrieval and provider recommendation."""

    model_config = ConfigDict(frozen=True)

    outcome_id: str
    task_key: str
    task_kind: str
    task_domain: str = "general"
    keywords: list[str] = Field(default_factory=list)
    provider: str
    model: str
    success: bool
    duration_sec: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=utc_now)


class CounterfactualStrategy(StrEnum):
    """Alternative routing policies evaluated post-hoc against actual execution."""

    ACTUAL = "actual"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    MAX_QUALITY = "max_quality"
    ADAPTIVE_BALANCED = "adaptive_balanced"


class CounterfactualComparison(BaseModel):
    """Comparative outcome projection under an alternative routing strategy."""

    model_config = ConfigDict(frozen=True)

    strategy: CounterfactualStrategy
    projected_cost_usd: float
    projected_duration_sec: float
    projected_success_rate: float
    quota_saved_ratio: float
    summary: str


class FailureCategory(StrEnum):
    """Categorized root causes of task or attempt failures."""

    SYNTAX_LINT = "syntax_lint"
    TYPE_CHECK = "type_check"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    QUOTA_EXHAUSTION = "quota_exhaustion"
    STAGNATION_LOOP = "stagnation_loop"
    UNKNOWN = "unknown"


class StagnationReport(BaseModel):
    """Telemetry report diagnosing repeated non-converging failure cycles."""

    model_config = ConfigDict(frozen=True)

    is_stagnated: bool
    consecutive_repetitions: int
    failure_category: FailureCategory
    error_fingerprint: str
    mandated_escalation: str | None = None
