"""Explainable Performance Intelligence Engine for statistical tracking and routing feedback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orkestra.schemas.performance import (
    DomainPerformanceMetrics,
    TaskPerformanceRecord,
)

if TYPE_CHECKING:
    from orkestra.store.repo import Store


class PerformanceIntelligenceEngine:
    """Authoritative statistical calculator providing transparent empirical capability weights."""

    def __init__(self, store: Store | None = None) -> None:
        self.store = store
        self._in_memory_records: list[TaskPerformanceRecord] = []

    def record_task_outcome(self, record: TaskPerformanceRecord) -> None:
        """Record task outcome telemetry in persistence and in-memory cache."""
        self._in_memory_records.append(record)
        if self.store is not None:
            self.store.record_task_performance(record)

    def get_domain_metrics(self, provider: str, domain: str) -> DomainPerformanceMetrics:
        """Compute statistical metrics with Laplace smoothing and confidence weighting."""
        records: list[TaskPerformanceRecord] = []
        if self.store is not None:
            records = self.store.list_task_performance(provider=provider, domain=domain, limit=200)
        else:
            records = [
                r
                for r in self._in_memory_records
                if r.provider.lower() == provider.lower() and r.domain.lower() == domain.lower()
            ]

        n = len(records)
        if n == 0:
            return DomainPerformanceMetrics(
                provider=provider,
                domain=domain,
                sample_size=0,
                first_pass_rate=0.5,
                eventual_pass_rate=0.5,
                average_repairs=0.0,
                average_duration_s=0.0,
                cache_hit_rate=0.0,
                confidence=0.0,
                performance_multiplier=1.0,
            )

        pass_1_count = sum(1 for r in records if r.pass_at_1)
        eventual_count = sum(1 for r in records if r.eventual_pass)
        total_repairs = sum(r.repair_attempts for r in records)
        total_duration = sum(r.duration_s for r in records)
        total_tokens = sum(r.input_tokens + r.output_tokens for r in records)
        cached_tokens = sum(r.cached_tokens for r in records)

        # Laplace smoothing: (k + 1) / (n + 2)
        pass_1_rate = round((pass_1_count + 1) / (n + 2), 4)
        eventual_rate = round((eventual_count + 1) / (n + 2), 4)
        avg_repairs = round(total_repairs / n, 2)
        avg_duration = round(total_duration / n, 2)
        cache_hit_rate = round(cached_tokens / max(1, total_tokens), 4)

        # Confidence: n / (n + 5) - bounded, grows with sample size
        confidence = round(n / (n + 5), 4)

        # Performance multiplier: adjusted by pass@1 deviation weighted by confidence
        # Maximum adjustment is +/- 20%
        multiplier = round(1.0 + (pass_1_rate - 0.5) * 0.4 * confidence, 4)

        return DomainPerformanceMetrics(
            provider=provider,
            domain=domain,
            sample_size=n,
            first_pass_rate=pass_1_rate,
            eventual_pass_rate=eventual_rate,
            average_repairs=avg_repairs,
            average_duration_s=avg_duration,
            cache_hit_rate=cache_hit_rate,
            confidence=confidence,
            performance_multiplier=multiplier,
        )

    def calculate_routing_score_adjustment(self, provider: str, domain: str) -> float:
        """Calculate additive score delta for ResourceRouter (-5.0 to +5.0 points).

        Positive for empirically proven high pass@1; negative for high defect rates.
        """
        metrics = self.get_domain_metrics(provider, domain)
        delta = (metrics.performance_multiplier - 1.0) * 20.0
        return round(max(-5.0, min(5.0, delta)), 2)

    def explain_metrics(self, provider: str, domain: str) -> str:
        """Generate human-readable explainability breakdown for a provider domain profile."""
        m = self.get_domain_metrics(provider, domain)
        return (
            f"Provider '{m.provider}' in domain '{m.domain}': "
            f"sample_size={m.sample_size}, pass@1={m.first_pass_rate:.1%}, "
            f"avg_repairs={m.average_repairs}, confidence={m.confidence:.1%}, "
            f"multiplier={m.performance_multiplier:.3f}"
        )
