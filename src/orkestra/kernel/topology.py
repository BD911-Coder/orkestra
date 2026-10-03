"""Deterministic Swarm Topology, Nesting Governance, and Parallel Efficiency Calculation."""

from __future__ import annotations

from orkestra.schemas.topology import ParallelEfficiencyMetrics, SwarmTopology

MAX_NESTED_WORKERS = 4
MAX_TOTAL_CONCURRENT_AGENTS = 8
MAX_SUBAGENT_DEPTH = 2


class TopologyIntelligenceEngine:
    """Evaluates multi-agent topologies, subagent nesting bounds, and parallel efficiency."""

    def __init__(
        self,
        max_nested_workers: int = MAX_NESTED_WORKERS,
        max_total_concurrent: int = MAX_TOTAL_CONCURRENT_AGENTS,
        max_subagent_depth: int = MAX_SUBAGENT_DEPTH,
    ) -> None:
        self.max_nested_workers = max_nested_workers
        self.max_total_concurrent = max_total_concurrent
        self.max_subagent_depth = max_subagent_depth

    def validate_subagent_dispatch(
        self,
        current_depth: int,
        current_nested_workers: int,
        total_concurrent: int,
    ) -> tuple[bool, str | None]:
        """Enforces deterministic bounds on recursive subagent creation and fleet size."""
        if current_depth >= self.max_subagent_depth:
            msg = (
                f"Subagent nesting depth limit reached "
                f"({current_depth} >= {self.max_subagent_depth})"
            )
            return False, msg
        if current_nested_workers >= self.max_nested_workers:
            msg = (
                f"Max nested workers reached "
                f"({current_nested_workers} >= {self.max_nested_workers})"
            )
            return False, msg
        if total_concurrent >= self.max_total_concurrent:
            msg = (
                f"Max total concurrent agents reached "
                f"({total_concurrent} >= {self.max_total_concurrent})"
            )
            return False, msg
        return True, None

    def calculate_parallel_efficiency(
        self,
        seq_sec: float,
        par_sec: float,
        worker_count: int,
        seq_tokens: int,
        par_tokens: int,
    ) -> ParallelEfficiencyMetrics:
        """Evaluates whether parallel execution yielded genuine speedup or wasteful overhead."""
        speedup = round(seq_sec / max(0.01, par_sec), 2)
        multiplier = round(par_tokens / max(1, seq_tokens), 2)
        efficiency = round(speedup / max(1, worker_count), 2)

        # Detect false parallelism: negligible speedup despite compute explosion
        is_false = (speedup <= 1.05 and multiplier >= 1.5) or (
            efficiency < 0.35 and worker_count > 1
        )

        if is_false:
            recommendation = (
                "COLLAPSE_TO_SEQUENTIAL: Parallel coordination overhead and token consumption "
                f"outweigh speedup ({speedup:.2f}x speedup vs {multiplier:.2f}x compute multiplier)"
            )
        else:
            recommendation = (
                "PROCEED_PARALLEL: Speedup justifies resource allocation "
                f"({speedup:.2f}x speedup at {efficiency:.2f} worker efficiency)"
            )

        return ParallelEfficiencyMetrics(
            sequential_time_sec=seq_sec,
            parallel_time_sec=par_sec,
            speedup=speedup,
            worker_count=worker_count,
            compute_multiplier=multiplier,
            parallel_efficiency=efficiency,
            is_false_parallelism=is_false,
            recommendation=recommendation,
        )

    def recommend_topology(
        self,
        complexity: int,
        available_providers: int,
        quota_scarcity: float,
    ) -> SwarmTopology:
        """Selects optimal multi-agent structure given task complexity and resource scarcity."""
        if quota_scarcity >= 0.70:
            # Under severe quota scarcity, enforce single-hub Star coordination
            return SwarmTopology.STAR

        if complexity <= 3:
            # Low complexity: simple hierarchical dispatch
            return SwarmTopology.HIERARCHICAL

        if complexity >= 8 and available_providers >= 2:
            # High complexity with multi-provider availability: peer mesh for independent review
            return SwarmTopology.MESH

        return SwarmTopology.ADAPTIVE
