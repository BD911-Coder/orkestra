"""Unit tests for ContextIntelligenceEngine, context health, and compaction logic."""

from __future__ import annotations

import pytest

from orkestra.kernel.context import (
    ContextIntelligenceEngine,
    resolve_context_limit,
)
from orkestra.schemas.agent import Usage
from orkestra.schemas.context import (
    CompactionBreakpoint,
    CompactionUrgency,
)


class TestContextIntelligence:
    def test_resolve_context_limits(self) -> None:
        assert resolve_context_limit("claude-3-5-sonnet") == 200_000
        assert resolve_context_limit("gpt-4o") == 128_000
        assert resolve_context_limit("gemini-1.5-pro") == 1_000_000
        assert resolve_context_limit("unknown-model") == 128_000

    def test_register_and_track_nominal_session(self) -> None:
        engine = ContextIntelligenceEngine()
        health = engine.register_session(
            session_id="sess-100",
            provider_id="claude",
            model_name="claude-3-5-sonnet",
        )
        assert health.session_id == "sess-100"
        assert health.context_window_limit == 200_000
        assert health.current_tokens == 0
        assert health.utilization_pct == 0.0
        assert health.urgency == CompactionUrgency.NOMINAL

        # Record nominal usage
        usage = Usage(input_tokens=10_000, output_tokens=2_000)
        updated = engine.record_usage("sess-100", usage)
        assert updated.current_tokens == 12_000
        assert updated.turn_count == 1
        assert updated.utilization_pct == 6.0
        assert updated.urgency == CompactionUrgency.NOMINAL

        # Evaluate compaction: should be False
        rec = engine.evaluate_compaction("sess-100")
        assert rec.should_compact is False
        assert rec.urgency == CompactionUrgency.NOMINAL

    def test_advised_compaction_at_strategic_breakpoint(self) -> None:
        engine = ContextIntelligenceEngine()
        engine.register_session(
            session_id="sess-200",
            provider_id="codex",
            model_name="gpt-4o",  # 128k limit
        )

        # 65% utilization = ~83,200 tokens
        usage = Usage(input_tokens=70_000, output_tokens=15_000)
        updated = engine.record_usage("sess-200", usage)
        assert updated.utilization_pct == pytest.approx(66.41, 0.1)
        assert updated.urgency == CompactionUrgency.ADVISED

        # Without breakpoint: should not force compact yet
        rec_nominal = engine.evaluate_compaction("sess-200")
        assert rec_nominal.should_compact is False

        # With POST_PLAN breakpoint: should advise compaction!
        rec_plan = engine.evaluate_compaction("sess-200", breakpoint=CompactionBreakpoint.POST_PLAN)
        assert rec_plan.should_compact is True
        assert rec_plan.urgency == CompactionUrgency.ADVISED
        assert rec_plan.breakpoint == CompactionBreakpoint.POST_PLAN
        assert "post_plan" in rec_plan.reason

    def test_urgent_and_critical_compaction(self) -> None:
        engine = ContextIntelligenceEngine()
        engine.register_session(
            session_id="sess-300",
            provider_id="claude",
            model_name="claude-3-5-sonnet",  # 200k limit
        )

        # 85% utilization -> URGENT
        usage_85 = Usage(input_tokens=150_000, output_tokens=20_000)
        h_urgent = engine.record_usage("sess-300", usage_85)
        assert h_urgent.urgency == CompactionUrgency.URGENT

        rec_urgent = engine.evaluate_compaction("sess-300")
        assert rec_urgent.should_compact is True
        assert rec_urgent.urgency == CompactionUrgency.URGENT

        # 95% utilization -> CRITICAL
        usage_95 = Usage(input_tokens=170_000, output_tokens=20_000)
        h_crit = engine.record_usage("sess-300", usage_95)
        assert h_crit.urgency == CompactionUrgency.CRITICAL

        rec_crit = engine.evaluate_compaction("sess-300")
        assert rec_crit.should_compact is True
        assert rec_crit.urgency == CompactionUrgency.CRITICAL

    def test_bloat_factor_and_handoff_compaction(self) -> None:
        engine = ContextIntelligenceEngine()
        engine.register_session(
            session_id="sess-400",
            provider_id="antigravity",
            model_name="antigravity-pro",  # 1M limit
        )

        # Record large raw output (e.g., massive file dump)
        engine.record_usage(
            "sess-400", Usage(input_tokens=50_000, output_tokens=40_000), is_tool_or_raw=True
        )
        # Small synthesized response
        engine.record_usage(
            "sess-400", Usage(input_tokens=55_000, output_tokens=2_000), is_tool_or_raw=False
        )

        health = engine.get_health("sess-400")
        assert health is not None
        assert health.bloat_factor > 10.0  # High bloat

        # PRE_HANDOFF breakpoint should recommend compaction due to high bloat
        rec = engine.evaluate_compaction("sess-400", breakpoint=CompactionBreakpoint.PRE_HANDOFF)
        assert rec.should_compact is True
        assert rec.breakpoint == CompactionBreakpoint.PRE_HANDOFF

    def test_memory_vault_and_carryover_summary(self) -> None:
        engine = ContextIntelligenceEngine()
        engine.register_session("sess-500", "claude", "claude-3-5-sonnet")

        # Record durable memories
        engine.record_memory(
            session_id="sess-500",
            key="db_schema_v2",
            content="Added tenant_id column to sessions table.",
            category="decision",
        )
        engine.record_memory(
            session_id="sess-500",
            key="test_failure_guard",
            content="Use CREATE_NEW_PROCESS_GROUP on Windows to prevent subchild zombie processes.",
            category="invariant",
        )

        memories = engine.get_memories("sess-500")
        assert len(memories) == 2

        summary = engine.format_carryover_summary("sess-500")
        assert "### Session Memory Carryover" in summary
        assert "[DECISION] db_schema_v2" in summary
        assert "[INVARIANT] test_failure_guard" in summary
