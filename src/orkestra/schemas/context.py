"""Schemas for context window monitoring, compaction boundaries, and memory carrying."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class CompactionUrgency(StrEnum):
    """Urgency level of context compaction."""

    NOMINAL = "nominal"  # < 60% context utilized
    ADVISED = "advised"  # 60% - 80% utilized (compact at logical boundaries)
    URGENT = "urgent"  # 80% - 90% utilized (compact immediately)
    CRITICAL = "critical"  # > 90% utilized (imminent session failure / truncation)


class CompactionBreakpoint(StrEnum):
    """Strategic logical lifecycle points where context compaction is optimal."""

    POST_PLAN = "post_plan"  # Plan is approved, compact exploration noise
    POST_FIX = "post_fix"  # Bug fix passes tests, compact debug traces
    PRE_HANDOFF = "pre_handoff"  # Prior to cross-provider or successor agent handoff
    PRE_REVIEW = "pre_review"  # Prior to independent peer review
    PERIODIC = "periodic"  # Threshold-driven periodic compaction


class ContextHealth(BaseModel):
    """Real-time context window utilization and pressure metrics for a session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    provider_id: str
    model_name: str
    context_window_limit: int
    current_tokens: int
    turn_count: int = 0
    token_velocity: float = 0.0  # Tokens per turn
    bloat_factor: float = 1.0  # Ratio of tool/raw outputs vs synthesized text
    urgency: CompactionUrgency = CompactionUrgency.NOMINAL
    last_updated: datetime = Field(default_factory=utc_now)

    @property
    def utilization_pct(self) -> float:
        if self.context_window_limit <= 0:
            return 0.0
        return round((self.current_tokens / self.context_window_limit) * 100.0, 2)


class MemoryItem(BaseModel):
    """Atomic durable memory extracted from an agent session."""

    model_config = ConfigDict(extra="forbid")

    key: str
    content: str
    category: str = "decision"  # decision, architecture, bug_pattern, invariant
    source_session: str = ""
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=utc_now)


class CompactionRecommendation(BaseModel):
    """Recommendation produced by ContextIntelligenceEngine."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    should_compact: bool
    urgency: CompactionUrgency
    breakpoint: CompactionBreakpoint | None = None
    reason: str
    suggested_carryover_memory: list[MemoryItem] = Field(default_factory=list)
    estimated_tokens_saved: int = 0
