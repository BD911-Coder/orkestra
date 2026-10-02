"""Unit tests for `orkestra usage` and `orkestra routing explain` CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pytest
from typer.testing import CliRunner, Result

from orkestra.cli.main import app as cli_app
from orkestra.schemas.common import utc_now
from orkestra.schemas.resource import (
    ProviderHealth,
    ProviderUsageSnapshot,
    QuotaConfidence,
    QuotaSource,
    QuotaWindow,
    ResourceState,
    RoutingDecision,
)
from orkestra.store import Database, Store

runner = CliRunner()


def test_cli_usage_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    runner.invoke(cli_app, ["init", str(root), "--non-interactive"])
    monkeypatch.chdir(root)

    db = Database(root / ".orkestra" / "orkestra.db")
    try:
        store = Store(db)
        now = utc_now().isoformat()
        snap = ProviderUsageSnapshot(
            provider="claude",
            health=ProviderHealth.HEALTHY,
            state=ResourceState.ACTIVE,
            windows=[
                QuotaWindow(
                    provider="claude",
                    window_kind="5h",
                    remaining_ratio=0.75,
                    source=QuotaSource.OFFICIAL_CLI,
                    confidence=QuotaConfidence.EXACT,
                    observed_at=now,
                )
            ],
            observed_at=now,
        )
        store.add_provider_snapshot(snap)
    finally:
        db.close()

    result = runner.invoke(cli_app, ["usage"])
    assert result.exit_code == 0
    assert "CLAUDE" in result.stdout
    assert "75%" in result.stdout


def test_cli_routing_explain_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    runner.invoke(cli_app, ["init", str(root), "--non-interactive"])
    monkeypatch.chdir(root)

    db = Database(root / ".orkestra" / "orkestra.db")
    try:
        store = Store(db)
        run_id = store.create_run("proj")
        now = utc_now().isoformat()

        decision = RoutingDecision(
            decision_id="dec_t1",
            run_id=run_id,
            task_id="t1",
            selected_profile="claude-opus-high",
            score=0.88,
            reasons=["task_fit_high", "waste_risk_bonus"],
            timestamp=now,
        )
        store.add_routing_decision(decision)
    finally:
        db.close()

    result = runner.invoke(cli_app, ["routing", "explain"])
    assert result.exit_code == 0
    assert "claude-opus-high" in result.stdout
    assert "task_fit_high" in result.stdout
