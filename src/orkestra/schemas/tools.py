"""Schemas for tool definitions, side effect classes, and execution telemetry."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EffectClass(StrEnum):
    """Categorization of tool side-effect severity inspired by defense-in-depth doctrine.

    SE0: Read-only evaluation, inspection, schema validation (no side effects).
    SE1: Reversible local writes inside workroot or scratch directories.
    SE2: Local process mutation, build execution, test runner execution.
    SE3: Append-only remote evidence publication, git commits and pushes.
    SE4: Economic, counterparty, payment, or secret-handling critical operations.
    """

    SE0_READ_ONLY = "SE0"
    SE1_LOCAL_WRITE = "SE1"
    SE2_MUTATION = "SE2"
    SE3_REMOTE_EVIDENCE = "SE3"
    SE4_EXTERNAL_CRITICAL = "SE4"


# Numeric rank for effect comparison (higher rank = higher risk/privilege)
EFFECT_CLASS_RANKS: dict[EffectClass, int] = {
    EffectClass.SE0_READ_ONLY: 0,
    EffectClass.SE1_LOCAL_WRITE: 1,
    EffectClass.SE2_MUTATION: 2,
    EffectClass.SE3_REMOTE_EVIDENCE: 3,
    EffectClass.SE4_EXTERNAL_CRITICAL: 4,
}


class ToolDescriptor(BaseModel):
    """Normalized metadata describing an invocable agent tool or harness utility."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    effect_class: EffectClass
    timeout_seconds: float = 30.0
    max_retries: int = 2
    rate_limit_per_minute: int | None = None
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    requires_permission: bool = False
    allowed_roles: list[str] = Field(
        default_factory=lambda: ["director", "implementer", "reviewer", "researcher"]
    )
    tags: list[str] = Field(default_factory=list)


class ToolTelemetry(BaseModel):
    """Execution telemetry and reliability metrics for a tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    invocations: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    last_invoked: datetime | None = None

    @property
    def average_latency_ms(self) -> float:
        return round(self.total_latency_ms / self.invocations, 2) if self.invocations > 0 else 0.0

    @property
    def success_rate(self) -> float:
        return round(self.successes / self.invocations, 4) if self.invocations > 0 else 1.0
