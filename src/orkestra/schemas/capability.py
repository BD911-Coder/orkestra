from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import TaskKind, utc_now


class DomainType(StrEnum):
    """Broad domain classification for general-purpose work orchestration."""

    SOFTWARE = "software"
    RESEARCH = "research"
    DATA_ENGINEERING = "data_engineering"
    DOCUMENTS = "documents"
    MEDIA = "media"
    DEVOPS = "devops"
    CUSTOM = "custom"


class CompetencyLevel(StrEnum):
    """Competency grade required or possessed."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CapabilityDescriptor(BaseModel):
    """Normalized metadata describing an operational capability."""

    model_config = ConfigDict(extra="forbid")

    name: str  # e.g., "software.architecture", "research.synthesis"
    domain: DomainType
    description: str
    required_competency: CompetencyLevel = CompetencyLevel.BASIC
    required_tools: list[str] = Field(default_factory=list)
    min_model_tier: str = "standard"  # fast, standard, reasoning, expert
    supported_modalities: list[str] = Field(default_factory=lambda: ["text"])
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class TaskQualification(BaseModel):
    """Qualification verdict checking whether an agent satisfies a capability."""

    model_config = ConfigDict(extra="forbid")

    qualified: bool
    capability_name: str
    agent_id: str
    reasons: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    missing_modalities: list[str] = Field(default_factory=list)


class CapabilityProbe(BaseModel):
    """A bounded, safe exercise used to measure an agent capability."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    probe_id: str
    capability: str
    kind: TaskKind
    prompt: str
    expected_kind: str = "text"  # text | json | code
    check: str = ""
    """Deterministic check description, evaluated by the probe harness."""


class CapabilityObservation(BaseModel):
    """One measured outcome (probe result or real task outcome)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    agent: str
    agent_version: str = ""
    capability: str
    source: str  # probe:<id> | task:<id>
    objective_pass: bool | None = None
    judged_score: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_s: float = 0.0
    ts: datetime = Field(default_factory=utc_now)


class CapabilityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    """Observation sources backing this score - scores without evidence are forbidden."""


class CapabilityMatrix(BaseModel):
    """agent -> capability -> evidenced score."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    scores: dict[str, dict[str, CapabilityScore]] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)

    def score_for(self, agent: str, capability: str) -> CapabilityScore | None:
        return self.scores.get(agent, {}).get(capability)
