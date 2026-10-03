"""Project configuration schema (`.orkestra/config.toml`).

Versioned: ``version = 1``. Unknown top-level keys are rejected to catch
typos early; precise error messages are a product requirement.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from orkestra.errors import ConfigError

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]

CONFIG_VERSION = 1


class AgentConfig(BaseModel):
    """One enabled agent (an adapter binding plus profile options)."""

    model_config = ConfigDict(extra="forbid")

    adapter: Slug
    enabled: bool = True
    model: str | None = None
    effort: Literal["auto", "low", "medium", "high", "max"] | None = None
    """Provider-neutral reasoning effort; validated against the adapter's
    real capabilities (schemas/effort.py) - unsupported levels are rejected,
    never silently ignored. None == "auto" == adapter default."""
    autonomy: Literal["safe", "unsafe-full"] = "safe"
    run_commands: bool = False
    """Let this agent run shell commands inside its isolated worktree.

    Off by default: Orkestra runs your `[verify]` commands itself, so
    agents don't need to. Turning it on lets an agent self-check before
    handing work back (fewer repair cycles, more trust in the agent),
    at the cost of letting it execute code in the worktree.
    """
    timeout_s: int = Field(default=1800, ge=30, le=24 * 3600)
    token_budget: int | None = Field(default=None, ge=1000)
    """Max input+output tokens this agent may spend per run (None = unlimited)."""
    sandbox_image: str | None = None
    """Container image for this agent when policy.sandbox = "docker" (external/fake only)."""
    # external-command adapters only:
    command: list[str] | None = None

    @model_validator(mode="after")
    def _external_needs_command(self) -> Self:
        from orkestra.schemas.effort import validate_effort

        effort_error = validate_effort(self.adapter, self.effort)
        if effort_error:
            raise ValueError(effort_error)

        if self.adapter == "external" and not self.command:
            msg = "agents using adapter='external' must set command = [...]"
            raise ValueError(msg)
        if self.adapter != "external" and self.command:
            msg = "command = [...] is only valid with adapter='external'"
            raise ValueError(msg)
        return self


class DirectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: Slug = "claude"
    max_decision_retries: int = Field(default=2, ge=0, le=5)


class NativeMultiAgentPolicyConfig(BaseModel):
    """Policy governing provider-native subagents, teams, and nesting."""

    model_config = ConfigDict(extra="forbid")

    allow_subagents: bool = True
    """Allow provider-native subagents (e.g. Claude subagents, Antigravity subagents)."""
    allow_agent_teams: bool = True
    """Allow provider-native agent teams."""
    max_nested_workers: int = Field(default=4, ge=1, le=16)
    """Maximum nested workers per parent agent."""
    max_total_concurrent_agents: int = Field(default=8, ge=1, le=64)
    """Maximum total concurrent agents across the entire orchestration run."""
    max_subagent_depth: int = Field(default=2, ge=1, le=5)
    """Maximum delegation nesting depth (e.g. depth 2 allows agent -> subagent -> subagent)."""
    allow_provider_auto_decide: bool = True
    """Allow provider to decide automatically within Orkestra limits."""
    count_nested_in_quota: bool = True
    """Count nested agents in quota and resource planning calculations (ALWAYS)."""


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_concurrency: int = Field(default=2, ge=1, le=32)
    max_attempts_per_task: int = Field(default=3, ge=1, le=10)
    max_review_cycles: int = Field(default=2, ge=0, le=5)
    require_review: bool = True
    session_reuse: bool = True
    """Resume an agent's CLI session on fix cycles in the same workspace."""
    allow_push: bool = False
    task_timeout_s: int = Field(default=1800, ge=30, le=24 * 3600)
    protected_paths: list[str] = Field(
        default_factory=lambda: [".git", ".orkestra", ".github/workflows"]
    )
    sandbox: Literal["none", "docker"] = "none"
    native_agents: NativeMultiAgentPolicyConfig = Field(
        default_factory=NativeMultiAgentPolicyConfig
    )


class VerifyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commands: list[str] = Field(default_factory=list)
    timeout_s: int = Field(default=900, ge=10, le=4 * 3600)
    binding_check: bool = True
    """Prove that the gate actually reads the task worktree.

    Orkestra corrupts one tracked source file in a throwaway worktree and
    requires the gate's exit code to change. A gate that does not react is
    reading some other tree (the classic cause is an editable install whose
    .pth file pins an absolute path to your main checkout) and its green is
    worthless.

    On by default because the answer is cached on the gate and the
    environment rather than recomputed per run. A verdict was identical
    across three different trees of one repository and moved only when the
    environment moved, so it is proved once per configuration and reused
    until your commands or your environment change. Turn it off if you would
    rather never pay that first proof.
    """


class ProbeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["live", "cached", "off"] = "cached"
    budget: int = Field(default=6, ge=0, le=50)
    timeout_s: int = Field(default=240, ge=10, le=3600)


class RoutingConfig(BaseModel):
    """Adaptive resource routing policy options."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["adaptive", "static"] = "adaptive"
    quota_aware: bool = True
    quota_optimization: bool = True
    waste_risk: bool = True
    allow_handoff: bool = True
    allow_model_escalation: bool = True
    usage_refresh_seconds: int = Field(default=60, ge=5, le=3600)
    max_handoffs_per_task: int = Field(default=2, ge=0, le=10)
    stagnation_threshold: int = Field(default=3, ge=1, le=10)
    quality_floor: bool = True


class ProjectSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Slug
    spec_file: str = "SPEC.md"


class ProjectConfig(BaseModel):
    """Root configuration document."""

    model_config = ConfigDict(extra="forbid")

    version: int
    project: ProjectSection
    agents: dict[Slug, AgentConfig]
    director: DirectorConfig = Field(default_factory=DirectorConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    verify: VerifyConfig = Field(default_factory=VerifyConfig)
    probes: ProbeConfig = Field(default_factory=ProbeConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.version != CONFIG_VERSION:
            msg = f"config version {self.version} is not supported (expected {CONFIG_VERSION})"
            raise ValueError(msg)
        enabled = [name for name, a in self.agents.items() if a.enabled]
        if len(enabled) < 2:
            msg = (
                f"at least two enabled agents are required, found {len(enabled)} "
                f"({', '.join(enabled) or 'none'}) - Orkestra orchestrates *multiple* agents"
            )
            raise ValueError(msg)
        if self.director.agent not in self.agents:
            msg = (
                f"director.agent {self.director.agent!r} is not a configured agent "
                f"(configured: {', '.join(self.agents)})"
            )
            raise ValueError(msg)
        if not self.agents[self.director.agent].enabled:
            msg = f"director.agent {self.director.agent!r} is disabled"
            raise ValueError(msg)
        return self

    @property
    def enabled_agents(self) -> dict[str, AgentConfig]:
        return {name: a for name, a in self.agents.items() if a.enabled}


def load_config(path: Path) -> ProjectConfig:
    """Load and validate a config file with precise errors."""
    if not path.is_file():
        msg = f"config file not found: {path}"
        raise ConfigError(msg)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"{path}: invalid TOML: {exc}"
        raise ConfigError(msg) from exc
    try:
        return ProjectConfig.model_validate(raw)
    except ValidationError as exc:
        details = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            if err.get("type") == "literal_error" and err.get("ctx", {}).get("expected"):
                reason = f"must be one of {err['ctx']['expected']}"
            else:
                reason = err["msg"].removeprefix("Value error, ")
            details.append(f"  {loc}: {reason}" if loc else f"  {reason}")
        msg = f"{path}: invalid configuration:\n" + "\n".join(details)
        raise ConfigError(msg) from exc
    except Exception as exc:
        msg = f"{path}: invalid configuration:\n{exc}"
        raise ConfigError(msg) from exc
