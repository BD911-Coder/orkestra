"""Deterministic Outcome Memory and Similar-Task Provider Retrieval."""

from __future__ import annotations

from orkestra.schemas.memory import TaskOutcomeRecord


class OutcomeMemoryStore:
    """Stores historical task execution records and retrieves similar experiences."""

    def __init__(self) -> None:
        self._records: list[TaskOutcomeRecord] = []

    def record_outcome(self, outcome: TaskOutcomeRecord) -> None:
        """Stores a task execution outcome."""
        self._records.append(outcome)

    def find_similar_outcomes(
        self,
        task_kind: str,
        task_domain: str = "general",
        keywords: list[str] | None = None,
        limit: int = 5,
    ) -> list[TaskOutcomeRecord]:
        """Finds most relevant historical records based on kind, domain, and keyword similarity."""
        query_keywords = {k.lower() for k in (keywords or [])}
        scored: list[tuple[float, TaskOutcomeRecord]] = []

        for r in self._records:
            score = 0.0
            if r.task_kind == task_kind:
                score += 3.0
            if r.task_domain == task_domain:
                score += 2.0

            record_keywords = {k.lower() for k in r.keywords}
            if query_keywords and record_keywords:
                overlap = len(query_keywords & record_keywords)
                union = len(query_keywords | record_keywords)
                score += (overlap / union) * 2.0

            scored.append((score, r))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [r for score, r in scored[:limit] if score > 0.0]

    def recommend_provider_for_task(
        self,
        task_kind: str,
        task_domain: str = "general",
        keywords: list[str] | None = None,
    ) -> tuple[str | None, float]:
        """Calculates historical success rates of providers on similar tasks and recommends best."""
        similar = self.find_similar_outcomes(task_kind, task_domain, keywords, limit=10)
        if not similar:
            return None, 0.0

        provider_stats: dict[str, list[bool]] = {}
        for r in similar:
            provider_stats.setdefault(r.provider, []).append(r.success)

        best_provider: str | None = None
        best_rate = -1.0

        for prov, results in provider_stats.items():
            rate = sum(1 for res in results if res) / len(results)
            if rate > best_rate:
                best_rate = rate
                best_provider = prov

        return best_provider, round(best_rate, 2)
