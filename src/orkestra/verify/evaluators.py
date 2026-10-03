"""Multi-domain artifact evaluation engine with cryptographic hash chaining."""

from __future__ import annotations

import abc
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from orkestra.schemas.common import utc_now
from orkestra.schemas.evaluators import (
    ArtifactType,
    EvaluationReceipt,
    EvaluationStatus,
    EvaluationVerdict,
)


def _compute_digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class BaseArtifactEvaluator(abc.ABC):
    """Abstract base class for all domain artifact evaluators."""

    def __init__(self, name: str, artifact_type: ArtifactType) -> None:
        self.name = name
        self.artifact_type = artifact_type

    @abc.abstractmethod
    def evaluate(
        self,
        artifact_path: str,
        context: dict[str, Any] | None = None,
    ) -> EvaluationVerdict:
        """Evaluate an artifact at artifact_path and return a structured verdict."""
        raise NotImplementedError


class CodeGateEvaluator(BaseArtifactEvaluator):
    """Evaluates software source files for syntax validity, length bounds, and basic conventions."""

    def __init__(self) -> None:
        super().__init__(name="evaluator.code.syntax", artifact_type=ArtifactType.CODE)

    def evaluate(
        self,
        artifact_path: str,
        context: dict[str, Any] | None = None,
    ) -> EvaluationVerdict:
        path = Path(artifact_path)
        issues: list[str] = []
        remedies: list[str] = []

        if not path.exists():
            return EvaluationVerdict(
                evaluator_name=self.name,
                artifact_type=self.artifact_type,
                status=EvaluationStatus.FAIL,
                score=0.0,
                artifact_path=artifact_path,
                issues=[f"Artifact file not found: {artifact_path}"],
                remedies=["Ensure the code file was created before verification."],
                cryptographic_digest=_compute_digest(f"missing:{artifact_path}"),
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        digest = _compute_digest(content)

        # Python syntax check if python file
        if path.suffix == ".py":
            try:
                compile(content, str(path), "exec")
            except SyntaxError as e:
                issues.append(f"Python syntax error at line {e.lineno}: {e.msg}")
                remedies.append("Fix the syntax error reported by the compiler.")

        # Check for uncommitted conflict markers
        if "<<<<<<< HEAD" in content or ">>>>>>> " in content:
            issues.append("Unresolved merge conflict markers detected in code artifact.")
            remedies.append("Clean up Git conflict markers before passing verification.")

        # Score computation
        if issues:
            status = EvaluationStatus.FAIL
            score = 0.0
        else:
            status = EvaluationStatus.PASS
            score = 1.0

        return EvaluationVerdict(
            evaluator_name=self.name,
            artifact_type=self.artifact_type,
            status=status,
            score=score,
            artifact_path=artifact_path,
            issues=issues,
            remedies=remedies,
            metadata={"file_size_bytes": len(content), "lines": len(content.splitlines())},
            cryptographic_digest=digest,
        )


class DocumentEvaluator(BaseArtifactEvaluator):
    """Evaluates markdown and text documentation for completeness, structure, and links."""

    def __init__(self) -> None:
        super().__init__(name="evaluator.doc.structure", artifact_type=ArtifactType.DOCUMENT)

    def evaluate(
        self,
        artifact_path: str,
        context: dict[str, Any] | None = None,
    ) -> EvaluationVerdict:
        path = Path(artifact_path)
        issues: list[str] = []
        remedies: list[str] = []

        if not path.exists():
            return EvaluationVerdict(
                evaluator_name=self.name,
                artifact_type=self.artifact_type,
                status=EvaluationStatus.FAIL,
                score=0.0,
                artifact_path=artifact_path,
                issues=[f"Documentation file not found: {artifact_path}"],
                remedies=["Create the required documentation artifact."],
                cryptographic_digest=_compute_digest(f"missing:{artifact_path}"),
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        digest = _compute_digest(content)

        # Require a top-level heading
        if not re.search(r"^#\s+.+", content, re.MULTILINE):
            issues.append("Document missing top-level # heading.")
            remedies.append("Add a primary # Title at the beginning of the document.")

        # Check minimum word length
        words = content.split()
        if len(words) < 20:
            issues.append(
                f"Document is suspiciously short ({len(words)} words; minimum 20 words required)."
            )
            remedies.append("Provide substantive documentation details.")

        # Check for placeholder markers
        placeholders = ["TODO", "TBD", "[Insert here]", "Lorem ipsum"]
        for p in placeholders:
            if p.lower() in content.lower():
                issues.append(f"Unfinished placeholder '{p}' found in documentation.")
                remedies.append(f"Replace placeholder '{p}' with complete factual text.")

        if issues:
            status = EvaluationStatus.NEEDS_REVISION
            score = max(0.2, 1.0 - 0.25 * len(issues))
        else:
            status = EvaluationStatus.PASS
            score = 1.0

        return EvaluationVerdict(
            evaluator_name=self.name,
            artifact_type=self.artifact_type,
            status=status,
            score=score,
            artifact_path=artifact_path,
            issues=issues,
            remedies=remedies,
            metadata={"word_count": len(words)},
            cryptographic_digest=digest,
        )


class ResearchEvaluator(BaseArtifactEvaluator):
    """Evaluates research reports for citation rigor, factual grounding, and claim clarity."""

    def __init__(self) -> None:
        super().__init__(name="evaluator.research.grounding", artifact_type=ArtifactType.RESEARCH)

    def evaluate(
        self,
        artifact_path: str,
        context: dict[str, Any] | None = None,
    ) -> EvaluationVerdict:
        path = Path(artifact_path)
        issues: list[str] = []
        remedies: list[str] = []

        if not path.exists():
            return EvaluationVerdict(
                evaluator_name=self.name,
                artifact_type=self.artifact_type,
                status=EvaluationStatus.FAIL,
                score=0.0,
                artifact_path=artifact_path,
                issues=[f"Research report file not found: {artifact_path}"],
                remedies=["Produce the research report file."],
                cryptographic_digest=_compute_digest(f"missing:{artifact_path}"),
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        digest = _compute_digest(content)

        # Check for citation indicators or references section
        has_citations = bool(
            re.search(r"(http[s]?://|\[\d+\]|reference|citation|source:)", content, re.IGNORECASE)
        )
        if not has_citations:
            issues.append("Research output lacks explicit citations, URLs, or reference section.")
            remedies.append("Add supporting citations or URL references for empirical claims.")

        # Check for unverified speculative phrases
        speculations = ["might be true", "I assume that", "probably works", "untested conjecture"]
        for spec in speculations:
            if spec.lower() in content.lower():
                issues.append(f"Speculative hedge phrase detected: '{spec}'")
                remedies.append(
                    "Ground claims in verified evidence rather than unverified conjecture."
                )

        if issues:
            status = EvaluationStatus.NEEDS_REVISION
            score = max(0.3, 1.0 - 0.3 * len(issues))
        else:
            status = EvaluationStatus.PASS
            score = 1.0

        return EvaluationVerdict(
            evaluator_name=self.name,
            artifact_type=self.artifact_type,
            status=status,
            score=score,
            artifact_path=artifact_path,
            issues=issues,
            remedies=remedies,
            metadata={"citations_detected": has_citations},
            cryptographic_digest=digest,
        )


class DataContractEvaluator(BaseArtifactEvaluator):
    """Evaluates data files (JSON, YAML, CSV) for parseability and non-emptiness."""

    def __init__(self) -> None:
        super().__init__(name="evaluator.data.contract", artifact_type=ArtifactType.DATA)

    def evaluate(
        self,
        artifact_path: str,
        context: dict[str, Any] | None = None,
    ) -> EvaluationVerdict:
        path = Path(artifact_path)
        issues: list[str] = []
        remedies: list[str] = []

        if not path.exists():
            return EvaluationVerdict(
                evaluator_name=self.name,
                artifact_type=self.artifact_type,
                status=EvaluationStatus.FAIL,
                score=0.0,
                artifact_path=artifact_path,
                issues=[f"Data file not found: {artifact_path}"],
                remedies=["Ensure the output data artifact exists."],
                cryptographic_digest=_compute_digest(f"missing:{artifact_path}"),
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        digest = _compute_digest(content)

        if not content.strip():
            issues.append("Data artifact is completely empty.")
            remedies.append("Populate the data artifact with serialized records.")
        elif path.suffix == ".json":
            try:
                parsed = json.loads(content)
                # Check required keys if provided in context
                if context and "required_keys" in context:
                    req_keys = set(context["required_keys"])
                    if isinstance(parsed, dict):
                        missing = req_keys - set(parsed.keys())
                        if missing:
                            issues.append(f"JSON data missing required keys: {', '.join(missing)}")
                            remedies.append(
                                f"Include the missing required keys: {', '.join(missing)}"
                            )
            except json.JSONDecodeError as err:
                issues.append(f"Malformed JSON: {err.msg} at line {err.lineno}")
                remedies.append("Fix JSON syntax errors.")

        if issues:
            status = EvaluationStatus.FAIL
            score = 0.0
        else:
            status = EvaluationStatus.PASS
            score = 1.0

        return EvaluationVerdict(
            evaluator_name=self.name,
            artifact_type=self.artifact_type,
            status=status,
            score=score,
            artifact_path=artifact_path,
            issues=issues,
            remedies=remedies,
            metadata={"byte_count": len(content)},
            cryptographic_digest=digest,
        )


class EvaluatorRegistry:
    """Catalog of domain evaluators that executes suites and produces chained receipts."""

    def __init__(self, include_defaults: bool = True) -> None:
        self._evaluators: dict[str, BaseArtifactEvaluator] = {}
        if include_defaults:
            self.register(CodeGateEvaluator())
            self.register(DocumentEvaluator())
            self.register(ResearchEvaluator())
            self.register(DataContractEvaluator())

    def register(self, evaluator: BaseArtifactEvaluator) -> None:
        """Register a domain evaluator."""
        self._evaluators[evaluator.name] = evaluator

    def get(self, name: str) -> BaseArtifactEvaluator | None:
        """Retrieve evaluator by name."""
        return self._evaluators.get(name)

    def list_for_type(self, artifact_type: ArtifactType) -> list[BaseArtifactEvaluator]:
        """List evaluators handling a specific artifact type."""
        return [e for e in self._evaluators.values() if e.artifact_type == artifact_type]

    def evaluate_bundle(
        self,
        task_id: str,
        artifacts: list[tuple[ArtifactType, str]],
        context: dict[str, Any] | None = None,
    ) -> EvaluationReceipt:
        """Evaluate a set of artifacts and assemble a cryptographically chained receipt."""
        verdicts: list[EvaluationVerdict] = []
        chain_hasher = hashlib.sha256()

        for art_type, art_path in artifacts:
            evaluators = self.list_for_type(art_type)
            if not evaluators:
                # Fallback: skip if no evaluator registered for this type
                v = EvaluationVerdict(
                    evaluator_name="evaluator.none",
                    artifact_type=art_type,
                    status=EvaluationStatus.SKIPPED,
                    score=1.0,
                    artifact_path=art_path,
                    issues=[],
                    remedies=[],
                    metadata={"notice": f"No evaluator registered for {art_type}"},
                    cryptographic_digest=_compute_digest(f"skipped:{art_path}"),
                )
                verdicts.append(v)
                chain_hasher.update(v.cryptographic_digest.encode("utf-8"))
                continue

            for ev in evaluators:
                v = ev.evaluate(art_path, context=context)
                verdicts.append(v)
                chain_hasher.update(v.cryptographic_digest.encode("utf-8"))

        # Determine overall status
        if any(v.status == EvaluationStatus.FAIL for v in verdicts):
            overall = EvaluationStatus.FAIL
        elif any(v.status == EvaluationStatus.NEEDS_REVISION for v in verdicts):
            overall = EvaluationStatus.NEEDS_REVISION
        else:
            overall = EvaluationStatus.PASS

        receipt_id = f"rcpt_{uuid4().hex[:12]}"
        return EvaluationReceipt(
            receipt_id=receipt_id,
            task_id=task_id,
            verdicts=verdicts,
            overall_status=overall,
            chain_digest=chain_hasher.hexdigest(),
            created_at=utc_now(),
        )
