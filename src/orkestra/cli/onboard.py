"""CLI command for automated project onboarding and config generation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from orkestra.director.onboarding import OnboardingDirector

console = Console()


def onboard_command(
    path: Annotated[
        Path, typer.Option("--path", "-p", help="Root directory of the project")
    ] = Path(),
    write: Annotated[
        bool, typer.Option("--write", "-w", help="Write .orkestra/config.toml automatically")
    ] = False,
) -> None:
    """Analyze repository and generate optimized Orkestra configuration."""
    director = OnboardingDirector()
    target_path = path.resolve()

    console.print(f"[bold cyan]Analyzing project at:[/bold cyan] {target_path}")
    profile = director.analyze_repository(target_path)

    table = Table(title=f"Detected Project Profile: {profile.project_name}", show_header=True)
    table.add_column("Category", style="bold yellow")
    table.add_column("Detected Values", style="white")

    table.add_row("Languages", ", ".join(profile.languages) or "none detected")
    table.add_row("Frameworks", ", ".join(profile.frameworks) or "none detected")
    table.add_row("Package Managers", ", ".join(profile.package_managers) or "none detected")
    table.add_row("Test Frameworks", ", ".join(profile.test_frameworks) or "none detected")
    table.add_row(
        "Linters / Formatters", ", ".join(profile.linters_and_formatters) or "none detected"
    )
    table.add_row("Verify Commands", " && ".join(profile.recommended_verify_commands))

    console.print(table)

    config_content = director.generate_config_toml(profile)

    if write:
        config_dir = target_path / ".orkestra"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.toml"
        config_file.write_text(config_content, encoding="utf-8")
        console.print(
            f"[bold green]Successfully written configuration to {config_file}[/bold green]"
        )
    else:
        console.print("\n[bold]Generated Configuration Preview:[/bold]")
        console.print(Panel(config_content, title=".orkestra/config.toml", border_style="cyan"))
        console.print("[dim]Run with '--write' to persist this configuration.[/dim]")
