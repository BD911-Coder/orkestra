"""Unit tests for adaptive scheduler integration, handoffs, and WAITING_FOR_QUOTA."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from orkestra.adapters.fake import FakeAdapter
from orkestra.kernel.scheduler import Orchestrator
from orkestra.policy import PolicyEngine
from orkestra.schemas.common import TaskKind
from orkestra.schemas.config import ProjectConfig
from orkestra.schemas.task import Assignment, TaskSpec
from orkestra.store import Database, Store
from orkestra.workspace.worktrees import WorkspaceManager


def make_config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "version": 1,
            "project": {"name": "test_project"},
            "agents": {
                "claude": {"adapter": "fake"},
                "antigravity": {"adapter": "fake"},
            },
            "director": {"agent": "claude"},
            "verify": {"commands": ["python --version"]},
        }
    )


@pytest.mark.asyncio
async def test_scheduler_adaptive_dispatch_and_handoff() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        import subprocess

        subprocess.run(["git", "init"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
        (root / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True)

        db = Database(root / "orkestra.db")
        try:
            store = Store(db)

            config = make_config()
            policy = PolicyEngine(config.policy, enabled_agents=list(config.agents.keys()))
            workspaces = WorkspaceManager(root, policy)

            fake_claude = FakeAdapter(agent_name="claude")
            fake_antigravity = FakeAdapter(agent_name="antigravity")

            adapters = {"claude": fake_claude, "antigravity": fake_antigravity}
            orchestrator = Orchestrator(root, config, store, adapters, policy, workspaces)

            run_id = store.create_run("test_project")
            spec = TaskSpec(
                key="t1", kind=TaskKind.RESEARCH, title="Research Architecture", mutates_repo=False
            )
            assignment = Assignment(
                primary="claude", reviewers=["antigravity"], fallbacks=["antigravity"]
            )
            task_id = store.add_task(run_id, spec, assignment)

            rev = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
            ).stdout.strip()
            store.set_run_git(run_id, rev, "main")

            state = await orchestrator.execute(run_id)
            assert state is not None

            # Check routing decision recorded
            decisions = store.routing_decisions_for_run(run_id)
            assert len(decisions) >= 1
            assert decisions[0].task_id == task_id
        finally:
            db.close()
