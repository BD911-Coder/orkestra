"""Unit tests for provider usage collectors and defensive parsers."""

from __future__ import annotations

import pytest

from orkestra.adapters.collectors import (
    CollectorRegistry,
    parse_antigravity_models_output,
    parse_claude_usage_output,
    parse_codex_status_output,
)
from orkestra.schemas.common import utc_now
from orkestra.schemas.resource import QuotaConfidence
from orkestra.store import Database, Store


@pytest.mark.asyncio
async def test_codex_parser_exact_and_fallback() -> None:
    now = utc_now().isoformat()

    # Test exact match from status text
    sample_status = "Codex CLI v0.159.3\nWeekly allowance: 62% remaining\nReset in 4d 12h"
    snapshot = parse_codex_status_output(sample_status, "codex", "default", now)
    assert snapshot.provider == "codex"
    assert len(snapshot.windows) == 1
    assert snapshot.windows[0].window_kind == "weekly"
    assert snapshot.windows[0].remaining_ratio == 0.62
    assert snapshot.windows[0].confidence == QuotaConfidence.EXACT

    # Test fallback parser when text is unformatted
    unformatted = "Codex CLI running OK"
    snap_fallback = parse_codex_status_output(unformatted, "codex", "default", now)
    assert snap_fallback.windows[0].confidence == QuotaConfidence.INFERRED


@pytest.mark.asyncio
async def test_claude_parser_exact_and_fallback() -> None:
    now = utc_now().isoformat()

    sample_usage = "Claude Code 2.1.280\n5-hour limit: 45% remaining\n"
    snapshot = parse_claude_usage_output(sample_usage, "claude", "default", now)
    assert snapshot.provider == "claude"
    assert snapshot.windows[0].remaining_ratio == 0.45
    assert snapshot.windows[0].confidence == QuotaConfidence.EXACT


@pytest.mark.asyncio
async def test_antigravity_parser() -> None:
    now = utc_now().isoformat()

    sample_models = "Available models:\n- antigravity-pro\n- antigravity-flash"
    snapshot = parse_antigravity_models_output(sample_models, "antigravity", "default", now)
    assert snapshot.provider == "antigravity"
    assert snapshot.windows[0].confidence == QuotaConfidence.INFERRED


@pytest.mark.asyncio
async def test_collector_registry_all() -> None:
    db = Database(":memory:")
    store = Store(db)
    try:
        registry = CollectorRegistry()
        snapshots = await registry.collect_all(store, "run_test")
        assert "codex" in snapshots
        assert "claude" in snapshots
        assert "antigravity" in snapshots
        assert "gemini" in snapshots

        unknown_collector = registry.get("custom_agent")
        snap_custom = await unknown_collector.collect(store, "run_test")
        assert snap_custom.provider == "custom_agent"
    finally:
        db.close()
