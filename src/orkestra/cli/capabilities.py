"""CLI commands for capability registry, security scanning, and skill import."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from orkestra.capabilities.importer import SkillImporter
from orkestra.capabilities.registry import CapabilityRegistry
from orkestra.capabilities.scanner import SkillSecurityScanner

capabilities_app = typer.Typer(help="Inspect, scan, and import capabilities and skills.")
console = Console()


@capabilities_app.command("list")
def list_capabilities() -> None:
    """List all registered capabilities in the registry."""
    reg = CapabilityRegistry()
    caps = reg.list_all()

    table = Table(title="Orkestra Capability Registry", show_header=True)
    table.add_column("Capability Name", style="bold cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Competency", style="green")
    table.add_column("Min Tier", style="yellow")
    table.add_column("Tags", style="white")

    for c in caps:
        table.add_row(
            c.name,
            c.domain.value.upper(),
            c.required_competency.value.upper(),
            c.min_model_tier,
            ", ".join(c.tags[:4]),
        )

    console.print(table)


@capabilities_app.command("scan")
def scan_path(
    path: Annotated[Path, typer.Argument(help="File or directory path to scan for security risks")],
) -> None:
    """Deterministically scan a capability file or directory for security violations."""
    scanner = SkillSecurityScanner()

    if path.is_file():
        result = scanner.scan_file(path)
        status = (
            "[bold green]SAFE[/bold green]" if result.is_safe else "[bold red]DANGEROUS[/bold red]"
        )
        console.print(
            f"File: [cyan]{path}[/cyan] | Status: {status} | Risk Score: {result.risk_score:.2f}"
        )

        if result.violations:
            table = Table(title="Detected Violations", show_header=True)
            table.add_column("Rule ID", style="bold red")
            table.add_column("Severity", style="yellow")
            table.add_column("Line", style="dim")
            table.add_column("Message", style="white")

            for v in result.violations:
                table.add_row(
                    v.rule_id,
                    v.severity.value.upper(),
                    str(v.line or "-"),
                    v.message,
                )
            console.print(table)
    elif path.is_dir():
        files = list(path.glob("**/*.md")) + list(path.glob("**/*.py"))
        console.print(
            f"Scanning [cyan]{len(files)}[/cyan] files in directory [bold]{path}[/bold]..."
        )

        safe_count = 0
        unsafe_count = 0

        for f in files:
            res = scanner.scan_file(f)
            if res.is_safe:
                safe_count += 1
            else:
                unsafe_count += 1
                console.print(
                    f"  [red]FAIL[/red]: {f.name} "
                    f"(Risk: {res.risk_score:.2f}, Violations: {len(res.violations)})"
                )

        console.print(
            f"\n[bold]Scan Complete:[/bold] [green]{safe_count} safe[/green], "
            f"[red]{unsafe_count} violations detected[/red]."
        )
    else:
        console.print(f"[bold red]Path does not exist: {path}[/bold red]")
        raise typer.Exit(code=1)


@capabilities_app.command("import")
def import_skills(
    path: Annotated[
        Path, typer.Argument(help="Path to SKILL.md file or directory of skills to import")
    ],
) -> None:
    """Scan and import external skills into Orkestra."""
    importer = SkillImporter()

    if path.is_file():
        descriptor, scan = importer.import_skill_file(path)
        if not scan.is_safe:
            console.print(
                "[bold red]Import rejected:[/bold red] File has security violations "
                f"(Risk: {scan.risk_score:.2f})"
            )
            for v in scan.violations:
                console.print(f"  - [{v.severity.value.upper()}] {v.message}")
            raise typer.Exit(code=1)

        if descriptor:
            console.print(
                f"[bold green]Successfully imported:[/bold green] [cyan]{descriptor.name}[/cyan] "
                f"({descriptor.domain.value}, {descriptor.required_competency.value})"
            )
    elif path.is_dir():
        imported = importer.import_directory(path)
        console.print(
            f"[bold green]Successfully imported {len(imported)} skills from {path}[/bold green]"
        )
        for desc in imported:
            console.print(f"  - [cyan]{desc.name}[/cyan] ({desc.domain.value})")
    else:
        console.print(f"[bold red]Path does not exist: {path}[/bold red]")
        raise typer.Exit(code=1)
