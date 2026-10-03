"""Deterministic Failure Classification and Stagnation Loop Detection."""

from __future__ import annotations

import hashlib
import re

from orkestra.schemas.memory import FailureCategory, StagnationReport


class FailureClassifier:
    """Classifies attempt errors into actionable categories based on error signatures."""

    @staticmethod
    def classify(error_output: str) -> FailureCategory:
        text = error_output.lower()
        if "syntaxerror" in text or "indentationerror" in text or "ruff" in text:
            return FailureCategory.SYNTAX_LINT
        if "mypy" in text or "incompatible type" in text or "type error" in text:
            return FailureCategory.TYPE_CHECK
        if "assert" in text or "failure" in text or "pytest" in text:
            return FailureCategory.TEST_FAILURE
        if "timeout" in text or "timed out" in text or "deadline exceeded" in text:
            return FailureCategory.TIMEOUT
        if "rate limit" in text or "quota" in text or "429" in text or "exhausted" in text:
            return FailureCategory.QUOTA_EXHAUSTION
        return FailureCategory.UNKNOWN


class StagnationDetector:
    """Detects repeated identical failure cycles to prevent infinite retry loops."""

    def __init__(self, repeat_threshold: int = 2) -> None:
        self.repeat_threshold = repeat_threshold
        # (run_id, task_key) -> list of error fingerprints
        self._history: dict[tuple[str, str], list[str]] = {}

    @staticmethod
    def fingerprint(error_output: str) -> str:
        """Normalizes and hashes error output, stripping dynamic timestamps or line numbers."""
        # Strip timestamps, line numbers, memory addresses
        normalized = re.sub(r"\b0x[0-9a-fA-F]+\b", "", error_output)
        normalized = re.sub(r":\d+:", "", normalized)
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "", normalized)
        normalized = " ".join(normalized.split()).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def record_attempt(
        self,
        run_id: str,
        task_key: str,
        error_output: str,
    ) -> StagnationReport:
        """Records an attempt error and determines whether execution is stagnating."""
        category = FailureClassifier.classify(error_output)
        fp = self.fingerprint(error_output)
        key = (run_id, task_key)

        history = self._history.setdefault(key, [])
        history.append(fp)

        # Count consecutive identical fingerprints from the end
        repetitions = 0
        for item in reversed(history):
            if item == fp:
                repetitions += 1
            else:
                break

        is_stagnated = repetitions >= self.repeat_threshold
        mandated_escalation: str | None = None
        if is_stagnated:
            category = FailureCategory.STAGNATION_LOOP
            mandated_escalation = (
                f"STAGNATION_LOOP_DETECTED({repetitions} identical failures): "
                "Kernel mandates switching provider or upgrading model effort level"
            )

        return StagnationReport(
            is_stagnated=is_stagnated,
            consecutive_repetitions=repetitions,
            failure_category=category,
            error_fingerprint=fp,
            mandated_escalation=mandated_escalation,
        )
