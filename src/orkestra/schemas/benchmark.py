"""Schemas for benchmark test batteries and scorecards."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.capability import DomainType
from orkestra.schemas.common import TaskKind, utc_now


class BenchmarkCase(BaseModel):
    """An individual standardized benchmark scenario."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    domain: DomainType = DomainType.SOFTWARE
    title: str
    task_kind: TaskKind = TaskKind.IMPLEMENT
    prompt: str
    required_tools: list[str] = Field(default_factory=list)
    verification_command: str = "true"
    timeout_seconds: int = 120
    difficulty: str = "standard"  # basic, standard, challenging


class BenchmarkRunResult(BaseModel):
    """Execution outcome for a single benchmark case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    agent_id: str
    passed: bool
    duration_seconds: float
    tokens_used: int = 0
    repairs_needed: int = 0
    details: str = ""


class BenchmarkScorecard(BaseModel):
    """Comprehensive performance scorecard summarizing a benchmark battery."""

    model_config = ConfigDict(extra="forbid")

    suite_name: str
    agent_id: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_duration_seconds: float
    total_tokens_used: int
    case_results: list[BenchmarkRunResult] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)
