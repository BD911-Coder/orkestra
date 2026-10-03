"""Pydantic schemas for Swarm Topology, Parallel Efficiency, and Background Backlog."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SwarmTopology(StrEnum):
    """Dynamic coordination topology for multi-agent execution."""

    HIERARCHICAL = "hierarchical"  # Leader -> workers tree (bounded depth)
    MESH = "mesh"  # Peer agents cross-verifying each other
    STAR = "star"  # Central orchestrator with radiating independent branches
    ADAPTIVE = "adaptive"  # Dynamically chosen based on complexity and resource scarcity


class ParallelEfficiencyMetrics(BaseModel):
    """Measures speedup and resource waste to prevent false parallelism."""

    model_config = ConfigDict(frozen=True)

    sequential_time_sec: float
    parallel_time_sec: float
    speedup: float
    worker_count: int
    compute_multiplier: float
    parallel_efficiency: float
    is_false_parallelism: bool
    recommendation: str


class SubagentTreeAttribution(BaseModel):
    """Hierarchical resource attribution and nesting constraint state."""

    model_config = ConfigDict(frozen=True)

    parent_task_id: str
    root_provider: str
    child_task_ids: list[str] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    current_depth: int = 0
    max_depth_allowed: int = 2
    max_nested_workers: int = 4


class BackgroundWorkTask(BaseModel):
    """A low-priority maintenance or enrichment task for absorbing expiring quota."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    title: str
    priority: int = 1  # 1 (lowest) to 5 (highest)
    domain: str = "maintenance"
    estimated_duration_sec: float = 60.0
    preferred_provider: str | None = None
