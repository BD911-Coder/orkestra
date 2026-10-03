"""Pydantic schemas for Session Continuity, Context Pressure, and Switching Cost."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class ContextPressureLevel(StrEnum):
    """Context window utilization thresholds."""

    NORMAL = "normal"  # < 60% of window: standard operation
    ELEVATED = "elevated"  # 60% - 80% of window: prepare for compaction
    HIGH = "high"  # 80% - 90% of window: proactive compaction recommended
    CRITICAL = "critical"  # > 90% of window: immediate compaction or handoff required


class ContextAction(StrEnum):
    """Recommended action derived from context pressure."""

    CONTINUE = "continue"
    COMPACT = "compact"
    HANDOFF = "handoff"


class ContextPressureEvent(BaseModel):
    """Context telemetry event measuring window saturation."""

    model_config = ConfigDict(frozen=True)

    token_count: int
    window_limit: int
    usage_ratio: float
    pressure_level: ContextPressureLevel
    recommended_action: ContextAction
    timestamp: datetime = Field(default_factory=utc_now)


class SessionContinuityState(BaseModel):
    """Tracks provider affinity, cache warmth, and worktree continuity across task transitions."""

    model_config = ConfigDict(frozen=True)

    active_run_id: str
    current_provider: str | None = None
    active_worktree: str | None = None
    tokens_accumulated: int = 0
    switch_count: int = 0
    last_checkpoint_id: str | None = None
