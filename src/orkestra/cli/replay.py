"""CLI command for reconstructing and inspecting run replay timelines."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from orkestra.report.replay import RunReplaySynthesizer


def replay_command(
    run_id: Annotated[str, typer.Argument(help="Run ID to replay and audit.")],
    markdown: Annotated[
        bool, typer.Option("--markdown", "-m", help="Output raw markdown format.")
    ] = False,
) -> None:
    """Reconstruct chronological execution timeline and causal audit chain for a run."""
    console = Console()
    synthesizer = RunReplaySynthesizer()
    summary = synthesizer.synthesize(run_id, [])

    if markdown:
        console.print(synthesizer.render_markdown(summary))
    else:
        console.print(f"[bold cyan]Orkestra Replay — Run ID:[/bold cyan] {run_id}")
        console.print(
            f"[yellow]Final Verdict:[/yellow] {summary.final_verdict} | "
            f"[yellow]Total Events:[/yellow] {summary.total_events}"
        )
