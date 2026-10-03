"""Deterministic Multi-Window Quota Evaluation, Scarcity Capping, and Provenance Confidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from orkestra.schemas.common import utc_now
from orkestra.schemas.resources_v2 import (
    MultiWindowQuotaProfile,
    QuotaConfidence,
    QuotaWindowStatus,
    QuotaWindowType,
)

CONFIDENCE_WEIGHTS: dict[QuotaConfidence, float] = {
    QuotaConfidence.EXACT: 1.0,
    QuotaConfidence.ESTIMATED: 0.85,
    QuotaConfidence.INFERRED: 0.65,
    QuotaConfidence.UNKNOWN: 0.35,  # UNKNOWN != ABUNDANT: significant uncertainty penalty
}

WINDOW_HOURS: dict[QuotaWindowType, float] = {
    QuotaWindowType.FIVE_HOUR: 5.0,
    QuotaWindowType.DAILY: 24.0,
    QuotaWindowType.WEEKLY: 168.0,
    QuotaWindowType.MONTHLY: 720.0,
}


class MultiWindowQuotaEvaluator:
    """Evaluates multi-window quota constraints, enforcing long-window scarcity bounds."""

    def __init__(self, confidence_weights: dict[QuotaConfidence, float] | None = None) -> None:
        self.weights = confidence_weights or CONFIDENCE_WEIGHTS

    def compute_headroom_ratio(
        self,
        used: float,
        limit: float | None,
        is_exhausted: bool = False,
    ) -> float:
        """Computes the normalized remaining quota ratio (0.0 to 1.0)."""
        if is_exhausted:
            return 0.0
        if limit is None or limit <= 0:
            return 0.5  # Neutral default when limit unspecified
        remaining = max(0.0, limit - used)
        return round(min(1.0, max(0.0, remaining / limit)), 4)

    def compute_reset_pressure(
        self,
        headroom_ratio: float,
        reset_at: datetime | None,
        current_time: datetime,
        window_type: QuotaWindowType,
    ) -> float:
        """Computes urgency to consume quota before expiration ('use-it-or-lose-it')."""
        if reset_at is None or headroom_ratio <= 0.01:
            return 0.0

        dt_seconds = (reset_at - current_time).total_seconds()
        if dt_seconds <= 0:
            return 1.0 if headroom_ratio > 0.05 else 0.0

        dt_hours = dt_seconds / 3600.0
        window_span_hours = WINDOW_HOURS.get(window_type, 24.0)

        if dt_hours >= window_span_hours:
            return 0.0

        # Quadratic decay: pressure rises steeply as reset approaches
        proximity = max(0.0, 1.0 - (dt_hours / window_span_hours))
        return round(headroom_ratio * (proximity**2), 4)

    def compute_burn_velocity(
        self,
        used: float,
        window_start: datetime | None,
        current_time: datetime,
    ) -> float:
        """Computes consumption velocity in units/hour."""
        if window_start is None or used <= 0:
            return 0.0
        elapsed_hours = max(0.05, (current_time - window_start).total_seconds() / 3600.0)
        return round(used / elapsed_hours, 2)

    def evaluate_profile(
        self,
        provider: str,
        raw_windows: list[dict[str, Any] | QuotaWindowStatus],
        current_time: datetime | None = None,
    ) -> MultiWindowQuotaProfile:
        """Evaluates all temporal windows and derives composite scarcity & headroom."""
        now = current_time or utc_now()
        evaluated_windows: dict[QuotaWindowType, QuotaWindowStatus] = {}

        for raw in raw_windows:
            if isinstance(raw, QuotaWindowStatus):
                wtype = raw.window_type
                used = raw.used
                limit = raw.limit
                reset_at = raw.reset_at
                conf = raw.confidence
                exhausted = raw.is_exhausted
                velocity = raw.burn_velocity_per_hour
                headroom = (
                    raw.headroom_ratio
                    if raw.headroom_ratio > 0
                    else self.compute_headroom_ratio(used, limit, exhausted)
                )
                pressure = (
                    raw.reset_pressure
                    if raw.reset_pressure > 0
                    else self.compute_reset_pressure(headroom, reset_at, now, wtype)
                )
                remaining = (
                    raw.remaining
                    if raw.remaining is not None
                    else (max(0.0, limit - used) if limit is not None else None)
                )

                status = QuotaWindowStatus(
                    window_type=wtype,
                    used=used,
                    limit=limit,
                    remaining=remaining,
                    reset_at=reset_at,
                    confidence=conf,
                    burn_velocity_per_hour=velocity,
                    headroom_ratio=headroom,
                    reset_pressure=pressure,
                    is_exhausted=exhausted or headroom <= 0.0,
                )
            else:
                wtype = QuotaWindowType(raw["window_type"])
                used = float(raw.get("used", 0.0))
                limit = float(raw["limit"]) if raw.get("limit") is not None else None
                reset_at = raw.get("reset_at")
                if isinstance(reset_at, str):
                    reset_at = datetime.fromisoformat(reset_at)
                conf = QuotaConfidence(raw.get("confidence", QuotaConfidence.UNKNOWN))
                exhausted = bool(raw.get("is_exhausted", False))

                headroom = self.compute_headroom_ratio(used, limit, exhausted)
                pressure = self.compute_reset_pressure(headroom, reset_at, now, wtype)
                velocity = float(raw.get("burn_velocity_per_hour", 0.0))
                remaining = max(0.0, limit - used) if limit is not None else None

                status = QuotaWindowStatus(
                    window_type=wtype,
                    used=used,
                    limit=limit,
                    remaining=remaining,
                    reset_at=reset_at,
                    confidence=conf,
                    burn_velocity_per_hour=velocity,
                    headroom_ratio=headroom,
                    reset_pressure=pressure,
                    is_exhausted=exhausted or headroom <= 0.0,
                )

            evaluated_windows[status.window_type] = status

        if not evaluated_windows:
            return MultiWindowQuotaProfile(
                provider=provider,
                windows={},
                composite_headroom=0.35,  # Unknown default
                composite_reset_pressure=0.0,
                effective_confidence=QuotaConfidence.UNKNOWN,
                throttle_recommended=False,
            )

        # 1. Effective confidence is the minimum confidence across windows
        confidence_order = [
            QuotaConfidence.UNKNOWN,
            QuotaConfidence.INFERRED,
            QuotaConfidence.ESTIMATED,
            QuotaConfidence.EXACT,
        ]
        effective_conf = min(
            (w.confidence for w in evaluated_windows.values()),
            key=lambda c: confidence_order.index(c),
        )
        conf_weight = self.weights.get(effective_conf, 0.35)

        # 2. Strict Scarcity Capping:
        # Long-window scarcity strictly caps short-window abundance!
        # Sort by window span descending (MONTHLY -> WEEKLY -> DAILY -> FIVE_HOUR)
        ordered_types = [
            QuotaWindowType.MONTHLY,
            QuotaWindowType.WEEKLY,
            QuotaWindowType.DAILY,
            QuotaWindowType.FIVE_HOUR,
        ]
        min_headroom = 1.0
        for w_type in ordered_types:
            if w_type in evaluated_windows:
                w_status = evaluated_windows[w_type]
                if w_status.headroom_ratio < min_headroom:
                    min_headroom = w_status.headroom_ratio

        # Composite headroom applies confidence multiplier (penalizing unknown provenance)
        composite_headroom = round(min_headroom * conf_weight, 4)

        # 3. Composite Reset Pressure: maximum reset pressure among available windows
        composite_pressure = round(
            max((w.reset_pressure for w in evaluated_windows.values()), default=0.0),
            4,
        )

        # 4. Burn velocity projection and throttling recommendation
        throttle_recommended = False
        projected_exhaustion_hours: float | None = None

        for w in evaluated_windows.values():
            if w.burn_velocity_per_hour > 0 and w.remaining is not None and w.remaining > 0:
                hours_left = w.remaining / w.burn_velocity_per_hour
                if projected_exhaustion_hours is None or hours_left < projected_exhaustion_hours:
                    projected_exhaustion_hours = round(hours_left, 2)

                if w.reset_at is not None:
                    time_to_reset_hours = (w.reset_at - now).total_seconds() / 3600.0
                    if 0 < hours_left < time_to_reset_hours:
                        throttle_recommended = True

        return MultiWindowQuotaProfile(
            provider=provider,
            windows=evaluated_windows,
            composite_headroom=composite_headroom,
            composite_reset_pressure=composite_pressure,
            effective_confidence=effective_conf,
            throttle_recommended=throttle_recommended,
            projected_exhaustion_hours=projected_exhaustion_hours,
        )
