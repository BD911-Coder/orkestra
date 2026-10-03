"""Unit tests for NativeMultiAgentPolicyConfig and PolicyEngine native subagent rules."""

from __future__ import annotations

from orkestra.policy.engine import PolicyEngine
from orkestra.schemas.config import NativeMultiAgentPolicyConfig, PolicyConfig


def test_native_multi_agent_policy_defaults() -> None:
    config = NativeMultiAgentPolicyConfig()
    assert config.allow_subagents is True
    assert config.allow_agent_teams is True
    assert config.max_nested_workers == 4
    assert config.max_total_concurrent_agents == 8
    assert config.max_subagent_depth == 2
    assert config.allow_provider_auto_decide is True
    assert config.count_nested_in_quota is True


def test_policy_engine_permits_valid_nested_dispatches() -> None:
    policy_config = PolicyConfig()
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex", "antigravity"])

    decision = engine.check_native_subagents(
        depth=1,
        nested_count=3,
        total_concurrent=6,
        is_team=False,
    )
    assert decision.allowed is True
    assert not decision.violations


def test_policy_engine_rejects_excess_depth() -> None:
    policy_config = PolicyConfig(native_agents=NativeMultiAgentPolicyConfig(max_subagent_depth=2))
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex"])

    decision = engine.check_native_subagents(depth=3)
    assert decision.allowed is False
    assert any("depth 3 exceeds maximum depth 2" in v for v in decision.violations)


def test_policy_engine_rejects_excess_nested_workers() -> None:
    policy_config = PolicyConfig(native_agents=NativeMultiAgentPolicyConfig(max_nested_workers=4))
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex"])

    decision = engine.check_native_subagents(nested_count=5)
    assert decision.allowed is False
    assert any("nested workers 5 exceeds limit (4)" in v for v in decision.violations)


def test_policy_engine_rejects_excess_total_concurrency() -> None:
    policy_config = PolicyConfig(
        native_agents=NativeMultiAgentPolicyConfig(max_total_concurrent_agents=8)
    )
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex"])

    decision = engine.check_native_subagents(total_concurrent=9)
    assert decision.allowed is False
    assert any("total concurrent agents 9 exceeds limit (8)" in v for v in decision.violations)


def test_policy_engine_disallows_subagents_when_disabled() -> None:
    policy_config = PolicyConfig(native_agents=NativeMultiAgentPolicyConfig(allow_subagents=False))
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex"])

    decision = engine.check_native_subagents(is_team=False)
    assert decision.allowed is False
    assert any("subagents are disallowed" in v for v in decision.violations)


def test_policy_engine_disallows_teams_when_disabled() -> None:
    policy_config = PolicyConfig(
        native_agents=NativeMultiAgentPolicyConfig(allow_agent_teams=False)
    )
    engine = PolicyEngine(policy_config, enabled_agents=["claude", "codex"])

    decision = engine.check_native_subagents(is_team=True)
    assert decision.allowed is False
    assert any("agent teams are disallowed" in v for v in decision.violations)
