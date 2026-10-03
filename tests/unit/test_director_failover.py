"""Unit tests for Director engine failover and persistent state saving."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orkestra.adapters.base import AdapterInfo, AgentAdapter, InvocationSpec
from orkestra.director.service import DirectorService
from orkestra.policy import PolicyEngine
from orkestra.schemas.agent import AgentEvent, AgentResult, ErrorKind, ResultStatus
from orkestra.schemas.config import ProjectConfig
from orkestra.schemas.director import DirectorAnalysis
from orkestra.schemas.task import TaskBrief
from orkestra.store import Database, Store


class MockParser:
    def __init__(self, ok: bool, payload: dict[str, Any] | None = None) -> None:
        self.ok = ok
        self.payload = payload

    def feed_line(self, line: str, is_stderr: bool) -> list[AgentEvent]:
        return []

    def result(self, returncode: int, duration: float, cwd: str) -> AgentResult:
        if not self.ok:
            return AgentResult(
                status=ResultStatus.ERROR, error_kind=ErrorKind.CRASH, error_detail="Failed"
            )
        return AgentResult(status=ResultStatus.OK, structured=self.payload)


class MockFailingAdapter(AgentAdapter):
    adapter_id = "failing"

    async def detect(self) -> AdapterInfo:
        return AdapterInfo(adapter_id="failing", available=True, version="1.0")

    async def check_auth(self) -> Any:
        from orkestra.schemas.agent import AuthStatus

        return AuthStatus(ready=True)

    def build_invocation(self, brief: TaskBrief) -> InvocationSpec:
        return InvocationSpec(argv=["python", "-c", "import sys; sys.exit(1)"], cwd=brief.cwd)

    def make_parser(self, brief: TaskBrief) -> Any:
        return MockParser(ok=False)


class MockWorkingAdapter(AgentAdapter):
    adapter_id = "working"

    async def detect(self) -> AdapterInfo:
        return AdapterInfo(adapter_id="working", available=True, version="1.0")

    async def check_auth(self) -> Any:
        from orkestra.schemas.agent import AuthStatus

        return AuthStatus(ready=True)

    def build_invocation(self, brief: TaskBrief) -> InvocationSpec:
        return InvocationSpec(
            argv=["python", "-c", "print('ok')"],
            cwd=brief.cwd,
        )

    def make_parser(self, brief: TaskBrief) -> Any:
        return MockParser(ok=True, payload={"summary": "Analyzed successfully", "risks": []})


def make_config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "version": 1,
            "project": {"name": "test_project"},
            "agents": {
                "claude": {"adapter": "fake"},
                "codex": {"adapter": "fake"},
            },
            "director": {"agent": "claude"},
        }
    )


@pytest.mark.asyncio
async def test_director_engine_failover(tmp_path: Path) -> None:
    db = Database(tmp_path / "director_test.db")
    try:
        store = Store(db)
        config = make_config()
        policy = PolicyEngine(config.policy, enabled_agents=list(config.agents.keys()))

        primary_failing = MockFailingAdapter()
        fallback_working = MockWorkingAdapter()

        service = DirectorService(
            director_name="claude",
            adapter=primary_failing,
            policy=policy,
            work_dir=tmp_path,
            max_retries=0,
            store=store,
            fallback_adapters={"codex": fallback_working},
        )

        analysis = await service.analyze("Test Spec Title", "agents list")
        assert isinstance(analysis, DirectorAnalysis)
        assert analysis.summary == "Analyzed successfully"

        # Verify persistent director state recorded active engine as codex
        dir_state = store.get_director_state("run_director")
        assert dir_state is not None
        assert dir_state.active_engine_profile == "codex"
    finally:
        db.close()
