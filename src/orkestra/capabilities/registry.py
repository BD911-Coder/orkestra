"""Generalized capability registry and dynamic qualification engine."""

from __future__ import annotations

import re
from typing import Any

from orkestra.schemas.capability import (
    CapabilityDescriptor,
    CompetencyLevel,
    DomainType,
    TaskQualification,
)
from orkestra.schemas.common import TaskKind

# Standard tier hierarchy from lowest to highest capability
MODEL_TIER_RANKS: dict[str, int] = {
    "fast": 1,
    "standard": 2,
    "reasoning": 3,
    "expert": 4,
}


def _get_standard_capabilities() -> list[CapabilityDescriptor]:
    return [
        # Software Domain
        CapabilityDescriptor(
            name="software.architecture",
            domain=DomainType.SOFTWARE,
            description="System design, component modularization, and architectural planning.",
            required_competency=CompetencyLevel.ADVANCED,
            required_tools=["view_file", "search_code"],
            min_model_tier="reasoning",
            supported_modalities=["text", "code"],
            tags=["architecture", "design", "planning", "system"],
        ),
        CapabilityDescriptor(
            name="software.implementation",
            domain=DomainType.SOFTWARE,
            description="Full-fidelity code implementation, refactoring, and feature construction.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["write_file", "replace_file_content", "view_file"],
            min_model_tier="standard",
            supported_modalities=["text", "code"],
            tags=["code", "implement", "feature", "build"],
        ),
        CapabilityDescriptor(
            name="software.debugging",
            domain=DomainType.SOFTWARE,
            description="Defect reproduction, root-cause isolation, and surgical bug fixing.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["view_file", "run_command", "replace_file_content"],
            min_model_tier="standard",
            supported_modalities=["text", "code"],
            tags=["debug", "fix", "defect", "error"],
        ),
        CapabilityDescriptor(
            name="software.code_review",
            domain=DomainType.SOFTWARE,
            description="Independent peer review, safety validation, and code standards adherence.",
            required_competency=CompetencyLevel.ADVANCED,
            required_tools=["view_file", "search_code"],
            min_model_tier="reasoning",
            supported_modalities=["text", "code"],
            tags=["review", "audit", "security", "style"],
        ),
        # Research Domain
        CapabilityDescriptor(
            name="research.deep_survey",
            domain=DomainType.RESEARCH,
            description="Comprehensive literature review and factual survey.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["web_search", "read_url"],
            min_model_tier="standard",
            supported_modalities=["text"],
            tags=["research", "survey", "investigation", "search"],
        ),
        CapabilityDescriptor(
            name="research.synthesis",
            domain=DomainType.RESEARCH,
            description="Multi-source synthesis, insight extraction, and hypothesis formulation.",
            required_competency=CompetencyLevel.ADVANCED,
            required_tools=["view_file", "write_file"],
            min_model_tier="reasoning",
            supported_modalities=["text"],
            tags=["synthesis", "analysis", "insights", "reasoning"],
        ),
        # Data Engineering Domain
        CapabilityDescriptor(
            name="data.etl_pipeline",
            domain=DomainType.DATA_ENGINEERING,
            description="Data pipeline engineering, schema migration, and transformation logic.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["run_command", "view_file", "write_file"],
            min_model_tier="standard",
            supported_modalities=["text", "code"],
            tags=["data", "etl", "sql", "migration", "pipeline"],
        ),
        # Documents Domain
        CapabilityDescriptor(
            name="documents.technical_spec",
            domain=DomainType.DOCUMENTS,
            description="Technical documentation, PRDs, ADRs, and API contract specifications.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["view_file", "write_file"],
            min_model_tier="standard",
            supported_modalities=["text"],
            tags=["docs", "spec", "adr", "documentation", "rfc"],
        ),
        # Media & Diagrams Domain
        CapabilityDescriptor(
            name="media.diagram_generation",
            domain=DomainType.MEDIA,
            description="Technical diagrams, Mermaid charts, data flow and entity visual models.",
            required_competency=CompetencyLevel.BASIC,
            required_tools=["write_file"],
            min_model_tier="standard",
            supported_modalities=["text"],
            tags=["mermaid", "diagram", "visual", "chart"],
        ),
        # DevOps Domain
        CapabilityDescriptor(
            name="devops.ci_cd_workflow",
            domain=DomainType.DEVOPS,
            description="CI/CD configuration, build scripts, and automation.",
            required_competency=CompetencyLevel.INTERMEDIATE,
            required_tools=["run_command", "view_file", "write_file"],
            min_model_tier="standard",
            supported_modalities=["text", "code"],
            tags=["ci", "cd", "docker", "pipeline", "devops", "automation"],
        ),
    ]


class CapabilityRegistry:
    """In-memory authoritative catalog of system capabilities with dynamic qualification."""

    def __init__(self, include_defaults: bool = True) -> None:
        self._capabilities: dict[str, CapabilityDescriptor] = {}
        if include_defaults:
            for cap in _get_standard_capabilities():
                self.register(cap)

    def register(self, capability: CapabilityDescriptor) -> None:
        """Register or update a capability definition."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> CapabilityDescriptor | None:
        """Retrieve capability descriptor by exact name."""
        return self._capabilities.get(name)

    def list_all(self) -> list[CapabilityDescriptor]:
        """List all registered capabilities sorted by name."""
        return sorted(self._capabilities.values(), key=lambda c: c.name)

    def list_by_domain(self, domain: DomainType) -> list[CapabilityDescriptor]:
        """Filter capabilities belonging to a specific domain."""
        return [c for c in self._capabilities.values() if c.domain == domain]

    def find_by_tags(self, tags: list[str]) -> list[CapabilityDescriptor]:
        """Find capabilities matching any of the specified search tags."""
        tag_set = {t.lower() for t in tags}
        return [
            c
            for c in self._capabilities.values()
            if tag_set.intersection({t.lower() for t in c.tags})
        ]

    def match_task(
        self,
        intent: str,
        task_kind: TaskKind | None = None,
    ) -> list[CapabilityDescriptor]:
        """Deterministically match capabilities against task intent and optional kind.

        Uses tokenized keyword matching and kind mapping to produce a ranked list
        without unconstrained LLM hallucinations.
        """
        scored: list[tuple[float, CapabilityDescriptor]] = []
        tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", intent.lower()))

        # Direct kind hints
        kind_mapping: dict[TaskKind, str] = {
            TaskKind.RESEARCH: "research.deep_survey",
            TaskKind.PLAN: "software.architecture",
            TaskKind.IMPLEMENT: "software.implementation",
            TaskKind.TEST: "software.implementation",
            TaskKind.REVIEW: "software.code_review",
            TaskKind.DEBUG: "software.debugging",
            TaskKind.DOCUMENT: "documents.technical_spec",
        }

        for cap in self._capabilities.values():
            score = 0.0

            # Match on task kind
            if task_kind and cap.name == kind_mapping.get(task_kind):
                score += 5.0

            # Match on tags
            matching_tags = tokens.intersection({t.lower() for t in cap.tags})
            score += len(matching_tags) * 2.0

            # Match in description or name
            if cap.name.lower() in intent.lower():
                score += 3.0
            desc_tokens = set(re.findall(r"\b[a-zA-Z0-9_]+\b", cap.description.lower()))
            score += len(tokens.intersection(desc_tokens)) * 0.5

            if score > 0:
                scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [cap for _, cap in scored]

    def qualify_agent(
        self,
        capability: CapabilityDescriptor,
        agent_profile: dict[str, Any],
    ) -> TaskQualification:
        """Validate whether an agent profile satisfies the capability requirements.

        Checks:
        1. Model tier sufficiency (fast < standard < reasoning < expert)
        2. Required tools presence
        3. Supported modalities coverage
        """
        reasons: list[str] = []
        missing_tools: list[str] = []
        missing_modalities: list[str] = []

        agent_id = str(agent_profile.get("id") or agent_profile.get("name") or "unknown_agent")
        agent_tier = str(agent_profile.get("tier") or "standard").lower()
        agent_tools = set(agent_profile.get("tools") or [])
        agent_modalities = set(agent_profile.get("modalities") or ["text"])

        # 1. Tier check
        req_rank = MODEL_TIER_RANKS.get(capability.min_model_tier.lower(), 2)
        actual_rank = MODEL_TIER_RANKS.get(agent_tier, 2)
        if actual_rank < req_rank:
            reasons.append(
                f"Agent tier '{agent_tier}' (rank {actual_rank}) is below required "
                f"'{capability.min_model_tier}' (rank {req_rank})"
            )

        # 2. Tool check
        for tool in capability.required_tools:
            if tool not in agent_tools:
                missing_tools.append(tool)
        if missing_tools:
            reasons.append(f"Missing required tools: {', '.join(missing_tools)}")

        # 3. Modalities check
        for mod in capability.supported_modalities:
            if mod not in agent_modalities:
                missing_modalities.append(mod)
        if missing_modalities:
            reasons.append(f"Missing required modalities: {', '.join(missing_modalities)}")

        qualified = len(reasons) == 0
        return TaskQualification(
            qualified=qualified,
            capability_name=capability.name,
            agent_id=agent_id,
            reasons=reasons,
            missing_tools=missing_tools,
            missing_modalities=missing_modalities,
        )
