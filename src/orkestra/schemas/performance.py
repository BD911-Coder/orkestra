"""Schemas for task execution performance telemetry and explainable intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class TaskPerformanceRecord(BaseModel):
    """Detailed telemetry record for a completed or failed task execution."""

    model_config = ConfigDict(extra="forbid")

    performance_id: str
    task_id: str
    run_id: str
    provider: str
    model: str
    domain: str = "software"
    pass_at_1: bool
    eventual_pass: bool
    repair_attempts: int = 0
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime = Field(default_factory=utc_now)


class DomainPerformanceMetrics(BaseModel):
    """Explainable aggregate metrics for a provider/profile in a specific domain."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    domain: str
    sample_size: int = 0
    first_pass_rate: float = 0.5  # Smoothed pass@1
    eventual_pass_rate: float = 0.5
    average_repairs: float = 0.0
    average_duration_s: float = 0.0
    cache_hit_rate: float = 0.0
    confidence: float = 0.0  # n / (n + 5)
    performance_multiplier: float = 1.0  # Routing score adjustment
