"""Counterfactual Routing Evaluation and Offline Strategy Arena."""

from __future__ import annotations

from orkestra.schemas.memory import CounterfactualComparison, CounterfactualStrategy


class CounterfactualEvaluator:
    """Simulates hypothetical outcomes under alternative routing strategies for finished tasks."""

    def evaluate_run(
        self,
        actual_cost_usd: float,
        actual_duration_sec: float,
        actual_success: bool,
    ) -> list[CounterfactualComparison]:
        """Compares actual execution against modeled alternate strategies."""
        results: list[CounterfactualComparison] = []

        # 1. ACTUAL
        results.append(
            CounterfactualComparison(
                strategy=CounterfactualStrategy.ACTUAL,
                projected_cost_usd=actual_cost_usd,
                projected_duration_sec=actual_duration_sec,
                projected_success_rate=1.0 if actual_success else 0.0,
                quota_saved_ratio=0.0,
                summary="Observed baseline execution",
            )
        )

        # 2. CHEAPEST
        cheapest_cost = round(actual_cost_usd * 0.55, 3)
        results.append(
            CounterfactualComparison(
                strategy=CounterfactualStrategy.CHEAPEST,
                projected_cost_usd=cheapest_cost,
                projected_duration_sec=round(actual_duration_sec * 1.35, 1),
                projected_success_rate=0.82,
                quota_saved_ratio=round(
                    (actual_cost_usd - cheapest_cost) / max(0.01, actual_cost_usd), 2
                ),
                summary="Free/low-tier models; higher latency and lower first-pass rate",
            )
        )

        # 3. FASTEST
        fastest_cost = round(actual_cost_usd * 1.45, 3)
        results.append(
            CounterfactualComparison(
                strategy=CounterfactualStrategy.FASTEST,
                projected_cost_usd=fastest_cost,
                projected_duration_sec=round(actual_duration_sec * 0.60, 1),
                projected_success_rate=0.90,
                quota_saved_ratio=-0.45,
                summary="Fastest responsive models regardless of quota burn",
            )
        )

        # 4. MAX_QUALITY
        quality_cost = round(actual_cost_usd * 2.20, 3)
        results.append(
            CounterfactualComparison(
                strategy=CounterfactualStrategy.MAX_QUALITY,
                projected_cost_usd=quality_cost,
                projected_duration_sec=round(actual_duration_sec * 0.90, 1),
                projected_success_rate=0.99,
                quota_saved_ratio=-1.20,
                summary="Flagship reasoning models; highest pass rate, highest burn",
            )
        )

        # 5. ADAPTIVE_BALANCED (V2 Operating System)
        adaptive_cost = round(actual_cost_usd * 0.85, 3)
        results.append(
            CounterfactualComparison(
                strategy=CounterfactualStrategy.ADAPTIVE_BALANCED,
                projected_cost_usd=adaptive_cost,
                projected_duration_sec=round(actual_duration_sec * 0.80, 1),
                projected_success_rate=0.96,
                quota_saved_ratio=0.15,
                summary="Dynamic multi-window quota routing with expiry harvesting",
            )
        )

        return results
