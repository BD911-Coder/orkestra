"""Schemas for capability and skill security scanning."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SecurityViolationSeverity(StrEnum):
    """Severity classification for skill and capability security violations."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityViolation(BaseModel):
    """An individual security violation detected during capability scanning."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: SecurityViolationSeverity
    message: str
    line: int | None = None
    evidence: str = Field(default="")


class ScanResult(BaseModel):
    """Aggregate result from scanning a skill or capability document/script."""

    model_config = ConfigDict(extra="forbid")

    is_safe: bool
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (dangerous)
    highest_severity: SecurityViolationSeverity | None = None
    violations: list[SecurityViolation] = Field(default_factory=list)
    scanned_bytes: int = 0
