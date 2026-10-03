"""Pydantic schemas for the Canonical V2 Neutral Event Bus and Correlation Engine."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now


class EventType(StrEnum):
    """Canonical event taxonomy for Orkestra V2."""

    RUN_LIFECYCLE = "run_lifecycle"
    TASK_DISPATCH = "task_dispatch"
    QUOTA_TELEMETRY = "quota_telemetry"
    VERIFICATION_GATE = "verification_gate"
    REVIEW_VERDICT = "review_verdict"
    CONTEXT_PRESSURE = "context_pressure"
    CONTINUITY_TRANSITION = "continuity_transition"
    STAGNATION_WARNING = "stagnation_warning"


class OrkestraEvent(BaseModel):
    """Base event model carrying causality correlation identifiers."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:8]}")
    run_id: str
    correlation_id: str  # Unifies causal chain (dispatch -> attempt -> gate -> review)
    event_type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReplayStep(BaseModel):
    """A chronological synthesized milestone in a run's lifecycle."""

    model_config = ConfigDict(frozen=True)

    step_index: int
    timestamp: datetime
    event_type: EventType
    title: str
    details: str
    correlation_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunReplaySummary(BaseModel):
    """Full timeline and causal reconstruction of an orchestrated run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    total_events: int
    start_time: datetime
    end_time: datetime | None = None
    steps: list[ReplayStep] = Field(default_factory=list)
    final_verdict: str = "UNKNOWN"
