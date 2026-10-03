"""Comprehensive benchmark harness for standardized cross-domain evaluation."""

from __future__ import annotations

import time
from collections.abc import Callable

from orkestra.schemas.benchmark import (
    BenchmarkCase,
    BenchmarkRunResult,
    BenchmarkScorecard,
)
from orkestra.schemas.capability import DomainType
from orkestra.schemas.common import TaskKind, utc_now

STANDARD_BENCHMARK_SUITE: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="BM-CODE-001",
        domain=DomainType.SOFTWARE,
        title="Pure Function Implementation",
        task_kind=TaskKind.IMPLEMENT,
        prompt="Implement a deterministic LRU cache with capacity limit and TTL expiration.",
        required_tools=["view_file", "write_file"],
        verification_command="python -m unittest tests.test_cache",
        difficulty="basic",
    ),
    BenchmarkCase(
        case_id="BM-CODE-002",
        domain=DomainType.SOFTWARE,
        title="Concurrency Race Fix",
        task_kind=TaskKind.DEBUG,
        prompt="Identify and resolve race condition in multi-threaded connection pool.",
        required_tools=["view_file", "replace_file_content", "run_command"],
        verification_command="python -m pytest -k test_concurrency",
        difficulty="standard",
    ),
    BenchmarkCase(
        case_id="BM-REV-001",
        domain=DomainType.SOFTWARE,
        title="Security & Guardrail Code Review",
        task_kind=TaskKind.REVIEW,
        prompt="Review pull request diff for SQL injection, path traversal, and secret leakage.",
        required_tools=["view_file"],
        verification_command="true",
        difficulty="standard",
    ),
    BenchmarkCase(
        case_id="BM-RES-001",
        domain=DomainType.RESEARCH,
        title="Technical Trade-off Survey",
        task_kind=TaskKind.RESEARCH,
        prompt="Survey and synthesize trade-offs between Raft vs Paxos in distributed stores.",
        required_tools=["search_web", "view_file"],
        verification_command="true",
        difficulty="standard",
    ),
]


class BenchmarkHarness:
    """Runs benchmark test batteries and computes standardized performance scorecards."""

    def __init__(self, cases: list[BenchmarkCase] | None = None) -> None:
        self.cases = cases if cases is not None else list(STANDARD_BENCHMARK_SUITE)

    def list_cases(self) -> list[BenchmarkCase]:
        """Return the current battery of benchmark cases."""
        return list(self.cases)

    def run_case_simulated(
        self,
        case: BenchmarkCase,
        agent_id: str,
        success_probability: float = 0.85,
    ) -> BenchmarkRunResult:
        """Simulate execution of a benchmark case for testing and offline baselines."""
        start = time.perf_counter()
        passed = success_probability >= 0.5
        elapsed = round(max(0.1, time.perf_counter() - start + 0.05), 3)

        return BenchmarkRunResult(
            case_id=case.case_id,
            agent_id=agent_id,
            passed=passed,
            duration_seconds=elapsed,
            tokens_used=1200 if passed else 2400,
            repairs_needed=0 if passed else 1,
            details=f"Simulated execution for {case.case_id} on {agent_id}",
        )

    def run_suite(
        self,
        agent_id: str,
        suite_name: str = "Standard-Orkestra-Battery",
        runner_fn: Callable[[BenchmarkCase, str], BenchmarkRunResult] | None = None,
    ) -> BenchmarkScorecard:
        """Execute all benchmark cases in the battery and compute aggregate scorecard."""
        results: list[BenchmarkRunResult] = []
        runner = runner_fn or self.run_case_simulated

        for case in self.cases:
            res = runner(case, agent_id)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pass_rate = round(passed / total, 3) if total > 0 else 0.0
        avg_dur = round(sum(r.duration_seconds for r in results) / total, 3) if total > 0 else 0.0
        total_tokens = sum(r.tokens_used for r in results)

        return BenchmarkScorecard(
            suite_name=suite_name,
            agent_id=agent_id,
            total_cases=total,
            passed_cases=passed,
            pass_rate=pass_rate,
            avg_duration_seconds=avg_dur,
            total_tokens_used=total_tokens,
            case_results=results,
            evaluated_at=utc_now(),
        )

    def format_scorecard_markdown(self, scorecard: BenchmarkScorecard) -> str:
        """Generate human-readable Markdown summary of a benchmark scorecard."""
        lines = [
            f"# Benchmark Scorecard: {scorecard.suite_name}",
            f"**Agent:** `{scorecard.agent_id}`",
            (
                f"**Pass Rate:** {scorecard.pass_rate * 100:.1f}% "
                f"({scorecard.passed_cases}/{scorecard.total_cases})"
            ),
            f"**Average Duration:** {scorecard.avg_duration_seconds:.2f}s",
            f"**Total Tokens:** {scorecard.total_tokens_used}",
            f"**Evaluated At:** {scorecard.evaluated_at.isoformat()}",
            "",
            "| Case ID | Status | Duration (s) | Tokens | Repairs | Details |",
            "|---------|--------|--------------|--------|---------|---------|",
        ]
        for r in scorecard.case_results:
            status = "PASS" if r.passed else "FAIL"
            row = (
                f"| `{r.case_id}` | {status} | {r.duration_seconds:.2f} | "
                f"{r.tokens_used} | {r.repairs_needed} | {r.details} |"
            )
            lines.append(row)

        return "\n".join(lines)
