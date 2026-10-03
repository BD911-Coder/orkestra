"""Provider resources, quota windows, routing decisions, handoffs, and Director state schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuotaSource(StrEnum):
    OFFICIAL_CLI = "official_cli"
    OFFICIAL_SDK = "official_sdk"
    STRUCTURED_PROVIDER_OUTPUT = "structured_provider_output"
    DOCUMENTED_STATUS_COMMAND = "documented_status_command"
    RATE_LIMIT_ERROR = "rate_limit_error"
    ORKESTRA_USAGE_LEDGER = "orkestra_usage_ledger"
    MANUAL_CONFIG = "manual_config"
    UNKNOWN = "unknown"


class QuotaConfidence(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ProviderHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    OUTAGE = "outage"
    UNKNOWN = "unknown"


class ResourceState(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    RESERVED = "reserved"
    COOLDOWN = "cooldown"
    SCARCE = "scarce"
    EXHAUSTED = "exhausted"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class QuotaWindow(BaseModel):
    """Represents a single provider quota window (e.g. 5h rolling, weekly, monthly)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    account_profile: str = "default"
    quota_pool: str = "default"
    model_family: str = "default"

    window_kind: str  # e.g., "5h", "weekly", "monthly", "token_budget"
    limit_value: float | None = None
    used_value: float | None = None
    remaining_value: float | None = None
    remaining_ratio: float | None = None  # 0.0 to 1.0

    window_started_at: str | None = None
    reset_at: str | None = None
    seconds_to_reset: float | None = None

    source: QuotaSource = QuotaSource.UNKNOWN
    confidence: QuotaConfidence = QuotaConfidence.UNKNOWN
    observed_at: str

    is_exhausted: bool = False
    is_estimated: bool = True


class ProviderUsageSnapshot(BaseModel):
    """Complete resource & quota snapshot for a single provider."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    account_profile: str = "default"
    health: ProviderHealth = ProviderHealth.HEALTHY
    state: ResourceState = ResourceState.IDLE
    windows: list[QuotaWindow] = Field(default_factory=list)
    waste_risk: float = 0.0
    scarcity: float = 0.0
    active_concurrency: int = 0
    max_concurrency: int = 2
    cooldown_until: str | None = None
    observed_at: str


class ExecutionProfile(BaseModel):
    """Agent / Provider / Model capability profile."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    provider: str
    adapter: str
    model: str
    effort: str = "medium"
    quality_rank: int = 5  # 1..10
    speed_rank: int = 5  # 1..10
    quota_pool: str = "default"
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoutingDecision(BaseModel):
    """Audit record explaining why an execution profile was chosen."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    run_id: str
    task_id: str
    selected_profile: str
    alternatives: list[str] = Field(default_factory=list)
    score: float
    reasons: list[str] = Field(default_factory=list)
    waste_risk: float = 0.0
    scarcity: float = 0.0
    quality_floor_applied: bool = False
    timestamp: str


class HandoffCheckpoint(BaseModel):
    """Structured mid-task handoff record between agents."""

    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    run_id: str
    task_id: str
    attempt_id: str
    worktree_path: str
    base_commit: str
    current_head: str
    diff_summary: str = ""
    completed_criteria: list[str] = Field(default_factory=list)
    remaining_criteria: list[str] = Field(default_factory=list)
    prior_agent: str
    prior_profile: str = ""
    successor_agent: str
    successor_profile: str = ""
    reason: str
    timestamp: str


class LogicalDirectorState(BaseModel):
    """Persistent project state owned by the logical Director."""

    model_config = ConfigDict(extra="forbid")

    director_id: str
    run_id: str
    active_engine_profile: str
    project_goal: str = ""
    architecture_notes: list[str] = Field(default_factory=list)
    task_dag_summary: dict[str, str] = Field(default_factory=dict)
    accepted_decisions: list[str] = Field(default_factory=list)
    rejected_decisions: list[str] = Field(default_factory=list)
    active_blockers: list[str] = Field(default_factory=list)
    recent_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str
