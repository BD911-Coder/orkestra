"""Pydantic schemas for Multi-Window Quota Evaluation, Headroom, and Provenance Confidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QuotaWindowType(StrEnum):
    """Temporal window scopes for provider quotas."""

    FIVE_HOUR = "5h"
    DAILY = "24h"
    WEEKLY = "7d"
    MONTHLY = "30d"


class QuotaConfidence(StrEnum):
    """Provenance confidence levels for quota telemetry (UNKNOWN != ABUNDANT)."""

    EXACT = "exact"  # Measured directly from official provider headers or telemetry
    ESTIMATED = "estimated"  # Computed from tracked requests and token counters
    INFERRED = "inferred"  # Heuristically derived from status codes or rate limit events
    UNKNOWN = "unknown"  # Unverified or unprovided; carries high uncertainty penalty


class QuotaWindowStatus(BaseModel):
    """Status and metrics of a single quota window."""

    model_config = ConfigDict(frozen=True)

    window_type: QuotaWindowType
    used: float = 0.0
    limit: float | None = None
    remaining: float | None = None
    reset_at: datetime | None = None
    confidence: QuotaConfidence = QuotaConfidence.UNKNOWN
    burn_velocity_per_hour: float = 0.0
    headroom_ratio: float = 0.0
    reset_pressure: float = 0.0
    is_exhausted: bool = False


class MultiWindowQuotaProfile(BaseModel):
    """Composite multi-window profile for a provider."""

    model_config = ConfigDict(frozen=True)

    provider: str
    windows: dict[QuotaWindowType, QuotaWindowStatus] = Field(default_factory=dict)
    composite_headroom: float = 0.0
    composite_reset_pressure: float = 0.0
    effective_confidence: QuotaConfidence = QuotaConfidence.UNKNOWN
    throttle_recommended: bool = False
    projected_exhaustion_hours: float | None = None
