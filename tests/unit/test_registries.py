"""Unit tests for CapabilityRegistry, ToolRegistry, and EvaluatorRegistry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkestra.capabilities.registry import CapabilityRegistry
from orkestra.schemas.capability import (
    DomainType,
)
from orkestra.schemas.common import TaskKind
from orkestra.schemas.evaluators import (
    ArtifactType,
    EvaluationStatus,
)
from orkestra.schemas.tools import EffectClass
from orkestra.tools.registry import ToolRegistry
from orkestra.verify.evaluators import (
    CodeGateEvaluator,
    DataContractEvaluator,
    DocumentEvaluator,
    EvaluatorRegistry,
    ResearchEvaluator,
)


class TestCapabilityRegistry:
    def test_default_capabilities_loaded(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        caps = reg.list_all()
        assert len(caps) >= 10
        names = [c.name for c in caps]
        assert "software.architecture" in names
        assert "research.deep_survey" in names
        assert "documents.technical_spec" in names

    def test_list_by_domain(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        software_caps = reg.list_by_domain(DomainType.SOFTWARE)
        assert len(software_caps) >= 4
        for c in software_caps:
            assert c.domain == DomainType.SOFTWARE

        research_caps = reg.list_by_domain(DomainType.RESEARCH)
        assert len(research_caps) >= 2
        for c in research_caps:
            assert c.domain == DomainType.RESEARCH

    def test_find_by_tags(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        results = reg.find_by_tags(["architecture", "planning"])
        assert len(results) >= 1
        assert any(c.name == "software.architecture" for c in results)

    def test_match_task_intent(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        # Search for debug / error fixing
        matches = reg.match_task("Need to debug defect in database query", task_kind=TaskKind.DEBUG)
        assert len(matches) > 0
        assert matches[0].name == "software.debugging"

    def test_qualify_agent_success(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        cap = reg.get("software.architecture")
        assert cap is not None

        agent_profile = {
            "id": "agent-claude-opus",
            "tier": "reasoning",
            "tools": ["view_file", "search_code", "write_file"],
            "modalities": ["text", "code"],
        }
        qual = reg.qualify_agent(cap, agent_profile)
        assert qual.qualified is True
        assert len(qual.reasons) == 0

    def test_qualify_agent_tier_mismatch(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        cap = reg.get("software.architecture")
        assert cap is not None  # requires reasoning tier

        agent_profile = {
            "id": "agent-haiku",
            "tier": "fast",
            "tools": ["view_file", "search_code"],
            "modalities": ["text", "code"],
        }
        qual = reg.qualify_agent(cap, agent_profile)
        assert qual.qualified is False
        assert any("tier" in r.lower() for r in qual.reasons)

    def test_qualify_agent_missing_tools(self) -> None:
        reg = CapabilityRegistry(include_defaults=True)
        cap = reg.get("software.implementation")
        assert cap is not None  # requires write_file, replace_file_content, view_file

        agent_profile = {
            "id": "agent-reader",
            "tier": "standard",
            "tools": ["view_file"],
            "modalities": ["text", "code"],
        }
        qual = reg.qualify_agent(cap, agent_profile)
        assert qual.qualified is False
        assert "write_file" in qual.missing_tools


class TestToolRegistry:
    def test_default_tools_loaded(self) -> None:
        reg = ToolRegistry(include_defaults=True)
        tools = reg.list_tools()
        assert len(tools) >= 10
        view = reg.get("view_file")
        assert view is not None
        assert view.effect_class == EffectClass.SE0_READ_ONLY

    def test_list_tools_by_effect_class(self) -> None:
        reg = ToolRegistry(include_defaults=True)
        se0 = reg.list_tools(EffectClass.SE0_READ_ONLY)
        assert all(t.effect_class == EffectClass.SE0_READ_ONLY for t in se0)
        assert any(t.name == "view_file" for t in se0)

        se3 = reg.list_tools(EffectClass.SE3_REMOTE_EVIDENCE)
        assert all(t.effect_class == EffectClass.SE3_REMOTE_EVIDENCE for t in se3)
        assert any(t.name == "git_push" for t in se3)

    def test_authorization_checks(self) -> None:
        reg = ToolRegistry(include_defaults=True)
        # Implementer calling view_file (SE0) with max SE2: should be authorized
        allowed, _ = reg.authorize("view_file", "implementer", EffectClass.SE2_MUTATION)
        assert allowed is True

        # Implementer calling git_push (SE3, allowed only for director)
        allowed, reason = reg.authorize("git_push", "implementer", EffectClass.SE3_REMOTE_EVIDENCE)
        assert allowed is False
        assert "not in allowed roles" in reason

        # Director calling cloud_deploy (SE4) when ceiling is SE2
        allowed, reason = reg.authorize("cloud_deploy", "director", EffectClass.SE2_MUTATION)
        assert allowed is False
        assert "exceeds maximum permitted effect ceiling" in reason

        # Non-existent tool
        allowed, reason = reg.authorize("non_existent_tool", "director")
        assert allowed is False
        assert "not registered" in reason

    def test_telemetry_recording(self) -> None:
        reg = ToolRegistry(include_defaults=True)
        reg.record_invocation("view_file", success=True, latency_ms=120.0)
        reg.record_invocation("view_file", success=True, latency_ms=80.0)
        reg.record_invocation("view_file", success=False, latency_ms=200.0)

        tel = reg.get_telemetry("view_file")
        assert tel is not None
        assert tel.invocations == 3
        assert tel.successes == 2
        assert tel.failures == 1
        assert tel.average_latency_ms == pytest.approx(133.33, 0.01)
        assert tel.success_rate == pytest.approx(0.6667, 0.001)

    def test_provider_tool_schemas_export(self) -> None:
        reg = ToolRegistry(include_defaults=True)
        openai_tools = reg.export_openai_tools()
        assert len(openai_tools) >= 10
        assert openai_tools[0]["type"] == "function"
        assert "name" in openai_tools[0]["function"]

        anthropic_tools = reg.export_anthropic_tools()
        assert len(anthropic_tools) >= 10
        assert "input_schema" in anthropic_tools[0]


class TestEvaluators:
    def test_code_evaluator_valid_and_invalid(self, tmp_path: Path) -> None:
        evaluator = CodeGateEvaluator()

        # Valid python file
        valid_py = tmp_path / "valid.py"
        valid_py.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")
        verdict = evaluator.evaluate(str(valid_py))
        assert verdict.status == EvaluationStatus.PASS
        assert verdict.score == 1.0
        assert len(verdict.cryptographic_digest) == 64

        # Syntax error
        invalid_py = tmp_path / "invalid.py"
        invalid_py.write_text("def broken(:\n    pass\n", encoding="utf-8")
        verdict_err = evaluator.evaluate(str(invalid_py))
        assert verdict_err.status == EvaluationStatus.FAIL
        assert len(verdict_err.issues) >= 1

        # Missing file
        missing_verdict = evaluator.evaluate(str(tmp_path / "does_not_exist.py"))
        assert missing_verdict.status == EvaluationStatus.FAIL

    def test_document_evaluator(self, tmp_path: Path) -> None:
        evaluator = DocumentEvaluator()

        # Good document
        good_doc = tmp_path / "good.md"
        good_doc.write_text(
            "# Architecture Specification\n\n"
            "This is a complete architectural specification document that provides thorough "
            "details on system interfaces, components, and security parameters across all "
            "operational environments.\n",
            encoding="utf-8",
        )
        verdict = evaluator.evaluate(str(good_doc))
        assert verdict.status == EvaluationStatus.PASS

        # Flawed document with placeholder
        bad_doc = tmp_path / "bad.md"
        bad_doc.write_text("# Overview\n\nTODO: write documentation later.\n", encoding="utf-8")
        bad_verdict = evaluator.evaluate(str(bad_doc))
        assert bad_verdict.status == EvaluationStatus.NEEDS_REVISION
        assert any("TODO" in iss for iss in bad_verdict.issues)

    def test_research_evaluator(self, tmp_path: Path) -> None:
        evaluator = ResearchEvaluator()

        # Valid research report with citations
        good_res = tmp_path / "research.md"
        good_res.write_text(
            "# Market Analysis\n\n"
            "Empirical benchmark data reveals significant performance increases as reported "
            "by [1] and corroborated by source: https://example.com/findings.\n",
            encoding="utf-8",
        )
        verdict = evaluator.evaluate(str(good_res))
        assert verdict.status == EvaluationStatus.PASS

        # Uncited speculative report
        bad_res = tmp_path / "uncited.md"
        bad_res.write_text(
            "# Speculation\n\nI assume that this probably works without any proof.\n",
            encoding="utf-8",
        )
        bad_verdict = evaluator.evaluate(str(bad_res))
        assert bad_verdict.status == EvaluationStatus.NEEDS_REVISION
        assert any("citations" in iss.lower() for iss in bad_verdict.issues)

    def test_data_evaluator(self, tmp_path: Path) -> None:
        evaluator = DataContractEvaluator()

        # Valid JSON with required keys
        data_file = tmp_path / "payload.json"
        data_file.write_text(json.dumps({"id": "123", "status": "active"}), encoding="utf-8")

        verdict = evaluator.evaluate(str(data_file), context={"required_keys": ["id", "status"]})
        assert verdict.status == EvaluationStatus.PASS

        # Missing required key
        verdict_missing = evaluator.evaluate(
            str(data_file), context={"required_keys": ["id", "token"]}
        )
        assert verdict_missing.status == EvaluationStatus.FAIL
        assert any("missing required keys" in iss.lower() for iss in verdict_missing.issues)

    def test_evaluator_registry_bundle_chaining(self, tmp_path: Path) -> None:
        reg = EvaluatorRegistry(include_defaults=True)

        py_file = tmp_path / "code.py"
        py_file.write_text("x = 42\n", encoding="utf-8")

        doc_file = tmp_path / "spec.md"
        doc_file.write_text(
            "# Specification\n\n"
            "This is a comprehensive architectural document detailing all requirements, "
            "design decisions, and verification standards for the new module to ensure "
            "high system quality and maintainability.\n",
            encoding="utf-8",
        )

        artifacts = [
            (ArtifactType.CODE, str(py_file)),
            (ArtifactType.DOCUMENT, str(doc_file)),
        ]

        receipt = reg.evaluate_bundle(task_id="task-42", artifacts=artifacts)
        assert receipt.task_id == "task-42"
        assert receipt.overall_status == EvaluationStatus.PASS
        assert len(receipt.verdicts) == 2
        assert len(receipt.chain_digest) == 64
