"""Deterministic Session Continuity, Context Pressure Evaluation, and Switching Cost Control."""

from __future__ import annotations

from orkestra.schemas.common import utc_now
from orkestra.schemas.continuity import (
    ContextAction,
    ContextPressureEvent,
    ContextPressureLevel,
    SessionContinuityState,
)


class SessionContinuityEngine:
    """Evaluates provider cache affinity, cold handoff penalties, and context pressure."""

    def __init__(
        self,
        same_provider_bonus: float = 1.0,
        cold_switch_penalty: float = 1.5,
    ) -> None:
        self.same_provider_bonus = same_provider_bonus
        self.cold_switch_penalty = cold_switch_penalty

    def compute_switching_adjustment(
        self,
        previous_provider: str | None,
        candidate_provider: str,
    ) -> tuple[float, str | None]:
        """Calculates score adjustment based on warm session affinity vs cold handoff cost."""
        if not previous_provider:
            return 0.0, None

        if previous_provider == candidate_provider:
            return (
                self.same_provider_bonus,
                f"session_warm_affinity:+{self.same_provider_bonus:.2f}",
            )

        return (
            -self.cold_switch_penalty,
            f"cold_session_switch_penalty:-{self.cold_switch_penalty:.2f}",
        )

    def evaluate_context_pressure(
        self,
        token_count: int,
        window_limit: int,
    ) -> ContextPressureEvent:
        """Determines context saturation level and recommends proactive compaction or handoff."""
        limit = max(1, window_limit)
        ratio = round(token_count / limit, 4)

        if ratio < 0.60:
            level = ContextPressureLevel.NORMAL
            action = ContextAction.CONTINUE
        elif ratio < 0.80:
            level = ContextPressureLevel.ELEVATED
            action = ContextAction.CONTINUE
        elif ratio < 0.90:
            level = ContextPressureLevel.HIGH
            action = ContextAction.COMPACT
        else:
            level = ContextPressureLevel.CRITICAL
            action = ContextAction.HANDOFF

        return ContextPressureEvent(
            token_count=token_count,
            window_limit=limit,
            usage_ratio=ratio,
            pressure_level=level,
            recommended_action=action,
            timestamp=utc_now(),
        )

    def record_transition(
        self,
        current_state: SessionContinuityState,
        next_provider: str,
        additional_tokens: int = 0,
        checkpoint_id: str | None = None,
    ) -> SessionContinuityState:
        """Records a task dispatch transition, updating provider affinity and token counters."""
        is_switch = (
            current_state.current_provider is not None
            and current_state.current_provider != next_provider
        )
        new_tokens = (
            additional_tokens if is_switch else current_state.tokens_accumulated + additional_tokens
        )
        new_switches = current_state.switch_count + 1 if is_switch else current_state.switch_count

        return SessionContinuityState(
            active_run_id=current_state.active_run_id,
            current_provider=next_provider,
            active_worktree=current_state.active_worktree,
            tokens_accumulated=new_tokens,
            switch_count=new_switches,
            last_checkpoint_id=checkpoint_id or current_state.last_checkpoint_id,
        )
