"""Background backlog task dispatcher to absorb expiring quota allowance."""

from __future__ import annotations

from orkestra.schemas.topology import BackgroundWorkTask


class BackgroundBacklogManager:
    """Schedules low-priority maintenance tasks when quota reset pressure is high."""

    def __init__(self, reset_pressure_threshold: float = 0.40) -> None:
        self.threshold = reset_pressure_threshold

    def select_background_task(
        self,
        backlog: list[BackgroundWorkTask],
        provider: str,
        provider_reset_pressure: float,
        current_concurrency: int = 0,
        max_concurrency: int = 4,
    ) -> BackgroundWorkTask | None:
        """Selects highest priority background task if provider quota is nearing expiration."""
        # 1. Capacity check
        if current_concurrency >= max_concurrency:
            return None

        # 2. Reset pressure gate: only absorb if quota is actively at risk of expiring unused
        if provider_reset_pressure < self.threshold:
            return None

        # 3. Filter eligible tasks
        eligible = [
            t for t in backlog if t.preferred_provider is None or t.preferred_provider == provider
        ]

        if not eligible:
            return None

        # Sort by priority descending
        eligible.sort(key=lambda t: t.priority, reverse=True)
        return eligible[0]
