"""Deterministic Adaptive Resource Router.

Ranks execution profiles based on task demands, quality floors, provider health,
scarcity, waste-risk (expiry pressure), multi-window quota ratios, and historical
performance.

Intelligence proposes; deterministic router disposes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from orkestra.schemas.common import TaskKind, utc_now
from orkestra.schemas.resource import (
    ExecutionProfile,
    ProviderHealth,
    ProviderUsageSnapshot,
    ResourceState,
    RoutingDecision,
)

if TYPE_CHECKING:
    from orkestra.kernel.performance import PerformanceIntelligenceEngine
    from orkestra.schemas.resources_v2 import MultiWindowQuotaProfile
    from orkestra.schemas.task import TaskSpec
    from orkestra.store import Store


def _now_iso() -> str:
    return utc_now().isoformat()


@dataclass
class RouterPolicy:
    """Configurable weights and thresholds for deterministic resource routing."""

    quality_weight: float = 2.0
    task_fit_weight: float = 1.5
    waste_risk_weight: float = 2.5
    underutilization_weight: float = 1.0
    scarcity_penalty_weight: float = 3.0
    cooldown_penalty: float = 5.0
    health_penalty: float = 4.0
    load_penalty_weight: float = 1.0
    failure_penalty_weight: float = 2.0
    min_quality_floor_default: int = 5
    high_risk_quality_floor: int = 7


class ResourceRouter:
    """Deterministic allocator that ranks candidate execution profiles for task dispatch."""

    def __init__(
        self,
        policy: RouterPolicy | None = None,
        profiles: list[ExecutionProfile] | None = None,
        performance_engine: PerformanceIntelligenceEngine | None = None,
    ) -> None:
        self.policy = policy or RouterPolicy()
        self.performance_engine = performance_engine
        self._profiles: dict[str, ExecutionProfile] = {}
        if profiles:
            for p in profiles:
                self._profiles[p.profile_id] = p
        else:
            self._register_default_profiles()

    def _register_default_profiles(self) -> None:
        defaults = [
            ExecutionProfile(
                profile_id="claude-opus-high",
                provider="claude",
                adapter="claude_code",
                model="claude-3-7-sonnet",
                effort="high",
                quality_rank=9,
                speed_rank=6,
                capabilities=["python", "architecture", "review", "refactor"],
            ),
            ExecutionProfile(
                profile_id="claude-sonnet-medium",
                provider="claude",
                adapter="claude_code",
                model="claude-3-7-sonnet",
                effort="medium",
                quality_rank=7,
                speed_rank=8,
                capabilities=["python", "implement", "test"],
            ),
            ExecutionProfile(
                profile_id="codex-sol-high",
                provider="codex",
                adapter="codex_cli",
                model="o3-mini",
                effort="high",
                quality_rank=9,
                speed_rank=7,
                capabilities=["python", "review", "debug", "implement"],
            ),
            ExecutionProfile(
                profile_id="antigravity-pro-high",
                provider="antigravity",
                adapter="antigravity_cli",
                model="antigravity-pro",
                effort="high",
                quality_rank=8,
                speed_rank=7,
                capabilities=["python", "implement", "document", "test"],
            ),
            ExecutionProfile(
                profile_id="antigravity-flash-medium",
                provider="antigravity",
                adapter="antigravity_cli",
                model="antigravity-flash",
                effort="medium",
                quality_rank=6,
                speed_rank=9,
                capabilities=["document", "test", "simple_implement"],
            ),
        ]
        for p in defaults:
            self._profiles[p.profile_id] = p

    def register_profile(self, profile: ExecutionProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> ExecutionProfile | None:
        return self._profiles.get(profile_id)

    def compute_waste_risk(self, snapshot: ProviderUsageSnapshot | None) -> float:
        """Computes waste risk (0.0..1.0): high remaining quota + reset approaching soon."""
        if not snapshot or not snapshot.windows:
            return 0.0

        max_risk = 0.0
        for w in snapshot.windows:
            ratio = w.remaining_ratio if w.remaining_ratio is not None else 0.5
            secs = w.seconds_to_reset if w.seconds_to_reset is not None else 86400.0

            # Short reset horizon (< 3 hours = 10800s) + High remaining quota (> 50%)
            time_factor = max(0.0, 1.0 - (secs / 10800.0))
            ratio_factor = max(0.0, (ratio - 0.3) / 0.7)
            risk = time_factor * ratio_factor
            if risk > max_risk:
                max_risk = risk
        return round(min(1.0, max_risk), 3)

    def compute_scarcity(self, snapshot: ProviderUsageSnapshot | None) -> float:
        """Computes scarcity penalty (0.0..1.0): multi-window bottleneck logic.

        Long-window scarcity (e.g. weekly remaining 4%) overrides short-window abundance!
        """
        if not snapshot or not snapshot.windows:
            return 0.0

        min_remaining = 1.0
        for w in snapshot.windows:
            if w.is_exhausted:
                return 1.0
            if w.remaining_ratio is not None and w.remaining_ratio < min_remaining:
                min_remaining = w.remaining_ratio

        # Scarcity is inverse of minimum remaining quota ratio across all windows
        if min_remaining <= 0.15:
            scarcity = 1.0 - (min_remaining / 0.15)
            return round(min(1.0, scarcity), 3)
        return 0.0

    def required_quality_floor(self, spec: TaskSpec) -> int:
        """Determines minimum quality rank needed for a task."""
        if spec.kind in (TaskKind.INTEGRATE, TaskKind.DEBUG):
            return self.policy.high_risk_quality_floor
        if "architecture" in spec.title.lower() or "security" in spec.title.lower():
            return self.policy.high_risk_quality_floor
        return self.policy.min_quality_floor_default

    def select_best_profile(
        self,
        task_id: str,
        run_id: str,
        spec: TaskSpec,
        snapshots: dict[str, ProviderUsageSnapshot],
        failed_agents: list[str] | None = None,
        store: Store | None = None,
        allowed_agents: list[str] | None = None,
        multi_window_profiles: dict[str, MultiWindowQuotaProfile] | None = None,
    ) -> RoutingDecision:
        """Scores candidate profiles and returns an auditable RoutingDecision."""
        failed_agents = failed_agents or []
        req_quality = self.required_quality_floor(spec)
        now = _now_iso()

        # Dynamically register profiles for allowed agents if missing
        if allowed_agents:
            for agent_name in allowed_agents:
                if not any(p.provider == agent_name for p in self._profiles.values()):
                    self._profiles[f"{agent_name}-default"] = ExecutionProfile(
                        profile_id=f"{agent_name}-default",
                        provider=agent_name,
                        adapter=agent_name,
                        model="default",
                        quality_rank=7,
                        capabilities=["python", "implement", "test", "review", "document"],
                    )

        candidates: list[ExecutionProfile] = [
            p
            for p in self._profiles.values()
            if p.enabled and (allowed_agents is None or p.provider in allowed_agents)
        ]

        scored_profiles: list[tuple[float, ExecutionProfile, list[str], float, float, bool]] = []

        for p in candidates:
            reasons: list[str] = []

            # 1. Quality Floor Gate
            if p.quality_rank < req_quality:
                reasons.append(f"DISQUALIFIED_QUALITY_FLOOR({p.quality_rank}<{req_quality})")
                continue

            # 2. Failed Agent Penalty / Exclusion
            if p.provider in failed_agents:
                reasons.append(f"PREVIOUSLY_FAILED_AGENT({p.provider})")

            # 3. Quota & Resource State
            snap = snapshots.get(p.provider)
            waste_risk = self.compute_waste_risk(snap)
            scarcity = self.compute_scarcity(snap)

            if snap and snap.health == ProviderHealth.EXHAUSTED:
                reasons.append("DISQUALIFIED_PROVIDER_EXHAUSTED")
                continue

            # Base Score Components
            quality_score = (p.quality_rank / 10.0) * self.policy.quality_weight
            reasons.append(f"quality:{quality_score:.2f}")

            # Task Fit
            fit_score = 0.0
            if any(cap in spec.title.lower() or cap in spec.kind.value for cap in p.capabilities):
                fit_score = 1.0 * self.policy.task_fit_weight
                reasons.append("task_fit_high")

            # Waste Risk Bonus (Expiry pressure)
            waste_bonus = waste_risk * self.policy.waste_risk_weight
            if waste_bonus > 0.1:
                reasons.append(f"waste_risk_bonus:+{waste_bonus:.2f}")

            # Scarcity Penalty (Multi-window limit protection)
            scarcity_penalty = scarcity * self.policy.scarcity_penalty_weight
            if scarcity_penalty > 0.1:
                reasons.append(f"scarcity_penalty:-{scarcity_penalty:.2f}")

            # V2 Multi-Window Quota Evaluation (Reset pressure & composite headroom)
            throttle_penalty = 0.0
            if multi_window_profiles and p.provider in multi_window_profiles:
                mw_prof = multi_window_profiles[p.provider]
                if mw_prof.composite_reset_pressure > 0.1:
                    rp_bonus = mw_prof.composite_reset_pressure * self.policy.waste_risk_weight
                    waste_bonus = max(waste_bonus, rp_bonus)
                    reasons.append(f"v2_reset_pressure_bonus:+{rp_bonus:.2f}")
                if mw_prof.composite_headroom < 0.2:
                    mw_scarcity = 1.0 - (mw_prof.composite_headroom / 0.2)
                    scarcity = max(scarcity, mw_scarcity)
                    scarcity_penalty = max(
                        scarcity_penalty,
                        mw_scarcity * self.policy.scarcity_penalty_weight,
                    )
                    reasons.append(f"v2_scarcity_penalty:-{scarcity_penalty:.2f}")
                if mw_prof.throttle_recommended:
                    throttle_penalty = 2.0
                    reasons.append("v2_throttle_burn_velocity_exceeded:-2.00")

            # Load & Health Penalties
            load_penalty = 0.0
            if snap and snap.active_concurrency >= snap.max_concurrency:
                load_penalty = self.policy.load_penalty_weight
                reasons.append(f"load_penalty:-{load_penalty:.2f}")

            cooldown_penalty = 0.0
            if snap and snap.state == ResourceState.COOLDOWN:
                cooldown_penalty = self.policy.cooldown_penalty
                reasons.append(f"cooldown_penalty:-{cooldown_penalty:.2f}")

            failed_penalty = (
                self.policy.failure_penalty_weight if p.provider in failed_agents else 0.0
            )

            perf_adj = 0.0
            if self.performance_engine is not None:
                domain = getattr(spec, "domain", "software") or "software"
                perf_adj = self.performance_engine.calculate_routing_score_adjustment(
                    p.provider, domain
                )
                if perf_adj != 0.0:
                    reasons.append(f"performance_intelligence:{perf_adj:+.2f}")

            total_score = (
                quality_score
                + fit_score
                + waste_bonus
                - scarcity_penalty
                - throttle_penalty
                - load_penalty
                - cooldown_penalty
                - failed_penalty
                + perf_adj
            )

            scored_profiles.append((total_score, p, reasons, waste_risk, scarcity, True))

        if not scored_profiles:
            # Fallback profile when all options fail quality floor or exhaustion
            fallback_agent = allowed_agents[0] if allowed_agents else "claude"
            fallback_profile = next(
                (p for p in self._profiles.values() if p.provider == fallback_agent),
                ExecutionProfile(
                    profile_id=f"{fallback_agent}-default",
                    provider=fallback_agent,
                    adapter=fallback_agent,
                    model="default",
                    quality_rank=7,
                ),
            )
            return RoutingDecision(
                decision_id=f"dec_{task_id}_{uuid4().hex[:6]}",
                run_id=run_id,
                task_id=task_id,
                selected_profile=fallback_profile.profile_id,
                alternatives=[
                    p.profile_id for p in candidates if p.profile_id != fallback_profile.profile_id
                ],
                score=0.0,
                reasons=["FALLBACK_SELECTION_ALL_CANDIDATES_EXHAUSTED_OR_FLOORED"],
                waste_risk=0.0,
                scarcity=1.0,
                quality_floor_applied=True,
                timestamp=now,
            )

        # Sort descending by score
        scored_profiles.sort(key=lambda x: x[0], reverse=True)
        best_score, best_p, best_reasons, best_waste, best_scarcity, quality_applied = (
            scored_profiles[0]
        )
        alternatives = [p.profile_id for _, p, _, _, _, _ in scored_profiles[1:]]

        decision = RoutingDecision(
            decision_id=f"dec_{task_id}_{uuid4().hex[:8]}",
            run_id=run_id,
            task_id=task_id,
            selected_profile=best_p.profile_id,
            alternatives=alternatives,
            score=round(best_score, 3),
            reasons=best_reasons,
            waste_risk=best_waste,
            scarcity=best_scarcity,
            quality_floor_applied=quality_applied,
            timestamp=now,
        )

        if store:
            store.add_routing_decision(decision)

        return decision
