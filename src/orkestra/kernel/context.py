"""Advanced Context Intelligence Engine for session health, compaction, and memory carrying."""

from __future__ import annotations

from orkestra.schemas.agent import Usage
from orkestra.schemas.common import utc_now
from orkestra.schemas.context import (
    CompactionBreakpoint,
    CompactionRecommendation,
    CompactionUrgency,
    ContextHealth,
    MemoryItem,
)

# Known model context windows in tokens
STANDARD_CONTEXT_LIMITS: dict[str, int] = {
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-5-haiku": 200_000,
    "gpt-4o": 128_000,
    "o1": 128_000,
    "o3-mini": 128_000,
    "gemini-1.5-pro": 1_000_000,
    "gemini-1.5-flash": 1_000_000,
    "antigravity-pro": 1_000_000,
    "default": 128_000,
}


def resolve_context_limit(model_name: str) -> int:
    """Resolve context window token limit for a model name."""
    lower = model_name.lower()
    for key, limit in STANDARD_CONTEXT_LIMITS.items():
        if key in lower:
            return limit
    return STANDARD_CONTEXT_LIMITS["default"]


class ContextIntelligenceEngine:
    """Authoritative monitor of per-session context pressure and compaction lifecycle."""

    def __init__(self) -> None:
        self._sessions: dict[str, ContextHealth] = {}
        self._raw_output_tokens: dict[str, int] = {}
        self._synthesized_tokens: dict[str, int] = {}
        self._memory_vault: dict[str, list[MemoryItem]] = {}  # session_id -> list[MemoryItem]

    def register_session(
        self,
        session_id: str,
        provider_id: str,
        model_name: str,
        custom_limit: int | None = None,
    ) -> ContextHealth:
        """Register or reset an active session's context tracking."""
        limit = custom_limit or resolve_context_limit(model_name)
        health = ContextHealth(
            session_id=session_id,
            provider_id=provider_id,
            model_name=model_name,
            context_window_limit=limit,
            current_tokens=0,
            turn_count=0,
            token_velocity=0.0,
            bloat_factor=1.0,
            urgency=CompactionUrgency.NOMINAL,
            last_updated=utc_now(),
        )
        self._sessions[session_id] = health
        self._raw_output_tokens[session_id] = 0
        self._synthesized_tokens[session_id] = 0
        return health

    def record_usage(
        self,
        session_id: str,
        usage: Usage,
        is_tool_or_raw: bool = False,
    ) -> ContextHealth:
        """Update session context token tracking after an agent turn or tool execution."""
        health = self._sessions.get(session_id)
        if not health:
            health = self.register_session(
                session_id=session_id,
                provider_id="unknown",
                model_name="default",
            )

        # Tokens accumulated in session
        total_tokens = usage.input_tokens + usage.output_tokens
        health.current_tokens = max(health.current_tokens, total_tokens)
        health.turn_count += 1
        health.token_velocity = round(health.current_tokens / max(1, health.turn_count), 1)

        # Track bloat factor (ratio of tool dumps vs natural reasoning)
        if is_tool_or_raw:
            self._raw_output_tokens[session_id] = (
                self._raw_output_tokens.get(session_id, 0) + usage.output_tokens
            )
        else:
            self._synthesized_tokens[session_id] = (
                self._synthesized_tokens.get(session_id, 0) + usage.output_tokens
            )

        raw = self._raw_output_tokens.get(session_id, 0)
        synth = max(1, self._synthesized_tokens.get(session_id, 0))
        health.bloat_factor = round(raw / synth, 2)

        # Determine urgency
        util = health.utilization_pct
        if util >= 90.0:
            health.urgency = CompactionUrgency.CRITICAL
        elif util >= 80.0:
            health.urgency = CompactionUrgency.URGENT
        elif util >= 60.0:
            health.urgency = CompactionUrgency.ADVISED
        else:
            health.urgency = CompactionUrgency.NOMINAL

        health.last_updated = utc_now()
        return health

    def evaluate_compaction(
        self,
        session_id: str,
        breakpoint: CompactionBreakpoint | None = None,
    ) -> CompactionRecommendation:
        """Evaluate whether a session should trigger context compaction.

        Combines quantitative token utilization with qualitative strategic breakpoints.
        """
        health = self._sessions.get(session_id)
        if not health:
            return CompactionRecommendation(
                session_id=session_id,
                should_compact=False,
                urgency=CompactionUrgency.NOMINAL,
                reason="Session not tracked in ContextIntelligenceEngine",
            )

        util = health.utilization_pct
        vault_items = self._memory_vault.get(session_id, [])

        # Case 1: Critical window utilization (> 90%)
        if health.urgency == CompactionUrgency.CRITICAL:
            return CompactionRecommendation(
                session_id=session_id,
                should_compact=True,
                urgency=CompactionUrgency.CRITICAL,
                breakpoint=breakpoint or CompactionBreakpoint.PERIODIC,
                reason=(
                    f"Context window utilization is critical ({util}%). "
                    "Immediate compaction required."
                ),
                suggested_carryover_memory=vault_items,
                estimated_tokens_saved=int(health.current_tokens * 0.5),
            )

        # Case 2: Urgent window utilization (> 80%)
        if health.urgency == CompactionUrgency.URGENT:
            return CompactionRecommendation(
                session_id=session_id,
                should_compact=True,
                urgency=CompactionUrgency.URGENT,
                breakpoint=breakpoint or CompactionBreakpoint.PERIODIC,
                reason=(
                    f"Context utilization exceeds 80% ({util}%). "
                    "Compacting before further multi-step reasoning."
                ),
                suggested_carryover_memory=vault_items,
                estimated_tokens_saved=int(health.current_tokens * 0.4),
            )

        # Case 3: Strategic breakpoint hit with advised utilization (> 60%)
        if breakpoint is not None and health.urgency == CompactionUrgency.ADVISED:
            return CompactionRecommendation(
                session_id=session_id,
                should_compact=True,
                urgency=CompactionUrgency.ADVISED,
                breakpoint=breakpoint,
                reason=(
                    f"Strategic breakpoint '{breakpoint.value}' reached with context at "
                    f"{util}%. Recommended to prune intermediate logs."
                ),
                suggested_carryover_memory=vault_items,
                estimated_tokens_saved=int(health.current_tokens * 0.35),
            )

        # Case 4: Pre-handoff or Pre-review always benefits from compaction if bloat is high
        if breakpoint in (
            CompactionBreakpoint.PRE_HANDOFF,
            CompactionBreakpoint.PRE_REVIEW,
        ) and (health.bloat_factor > 3.0 or util > 50.0):
            return CompactionRecommendation(
                session_id=session_id,
                should_compact=True,
                urgency=CompactionUrgency.ADVISED,
                breakpoint=breakpoint,
                reason=(
                    f"Clean handoff breakpoint '{breakpoint.value}' triggered with "
                    f"bloat factor {health.bloat_factor}."
                ),
                suggested_carryover_memory=vault_items,
                estimated_tokens_saved=int(health.current_tokens * 0.3),
            )

        return CompactionRecommendation(
            session_id=session_id,
            should_compact=False,
            urgency=health.urgency,
            breakpoint=breakpoint,
            reason=f"Context utilization nominal ({util}%). Compaction not needed.",
        )

    def record_memory(
        self,
        session_id: str,
        key: str,
        content: str,
        category: str = "decision",
    ) -> MemoryItem:
        """Record an atomic memory item for durable carryover during compaction or handoff."""
        item = MemoryItem(
            key=key,
            content=content,
            category=category,
            source_session=session_id,
            created_at=utc_now(),
        )
        if session_id not in self._memory_vault:
            self._memory_vault[session_id] = []
        self._memory_vault[session_id].append(item)
        return item

    def get_memories(self, session_id: str) -> list[MemoryItem]:
        """Retrieve stored memories for a session."""
        return list(self._memory_vault.get(session_id, []))

    def format_carryover_summary(self, session_id: str) -> str:
        """Format durable memory items as a clean markdown block for session handoff."""
        items = self.get_memories(session_id)
        if not items:
            return ""

        lines = ["### Session Memory Carryover", ""]
        for m in items:
            lines.append(f"- **[{m.category.upper()}] {m.key}:** {m.content}")
        return "\n".join(lines)

    def get_health(self, session_id: str) -> ContextHealth | None:
        """Retrieve health snapshot for a session."""
        return self._sessions.get(session_id)

    def list_all_health(self) -> list[ContextHealth]:
        """List health snapshots for all active sessions."""
        return list(self._sessions.values())
