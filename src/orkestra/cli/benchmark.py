"""CLI commands for benchmark execution and scorecard inspection."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from orkestra.benchmark.harness import BenchmarkHarness

benchmark_app = typer.Typer(help="Run and inspect standardized capability benchmarks.")
console = Console()


@benchmark_app.command("list")
def list_benchmark_cases() -> None:
    """List all standardized benchmark cases in the test battery."""
    harness = BenchmarkHarness()
    cases = harness.list_cases()

    table = Table(title="Standard Orkestra Benchmark Battery", show_header=True)
    table.add_column("Case ID", style="bold cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Difficulty", style="green")
    table.add_column("Kind", style="yellow")
    table.add_column("Title", style="white")

    for c in cases:
        table.add_row(
            c.case_id,
            c.domain.value.upper(),
            c.difficulty.upper(),
            c.task_kind.value.upper(),
            c.title,
        )

    console.print(table)


@benchmark_app.command("run")
def run_benchmarks(
    agent: Annotated[
        str, typer.Option("--agent", "-a", help="Agent identifier to benchmark")
    ] = "simulated_agent",
    suite: Annotated[
        str, typer.Option("--suite", "-s", help="Benchmark suite name")
    ] = "Standard-Battery",
) -> None:
    """Execute benchmark battery against an agent and print scorecard."""
    harness = BenchmarkHarness()
    cases = harness.list_cases()
    console.print(f"[bold]Executing {len(cases)} benchmark cases for agent '{agent}'...[/bold]")

    scorecard = harness.run_suite(agent_id=agent, suite_name=suite)

    table = Table(title=f"Benchmark Results: {suite} ({agent})", show_header=True)
    table.add_column("Case ID", style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Duration (s)", style="green")
    table.add_column("Tokens", style="yellow")
    table.add_column("Repairs", style="magenta")

    for r in scorecard.case_results:
        status_styled = "[bold green]PASS[/bold green]" if r.passed else "[bold red]FAIL[/bold red]"
        table.add_row(
            r.case_id,
            status_styled,
            f"{r.duration_seconds:.2f}",
            str(r.tokens_used),
            str(r.repairs_needed),
        )

    console.print(table)
    console.print(
        f"\n[bold]Summary:[/bold] Pass rate: "
        f"[bold green]{scorecard.pass_rate * 100:.1f}%[/bold green] "
        f"({scorecard.passed_cases}/{scorecard.total_cases}), "
        f"Avg Duration: {scorecard.avg_duration_seconds:.2f}s, "
        f"Total Tokens: {scorecard.total_tokens_used}"
    )
