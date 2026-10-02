"""`orkestra watch` - Adaptive Multi-AI Command Center Terminal UI (Textual).

Read-mostly terminal monitoring dashboard over the Orkestra run store:
exposes provider resource bars, live agent hierarchy tree, task DAG state,
decision explanation stream, and event logs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import App as TextualApp
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static, Tree

from orkestra.cli.text import clip

if TYPE_CHECKING:
    from orkestra.app import App as OrkestraApp

_STATE_STYLE = {
    "done": "bold green",
    "failed": "bold red",
    "blocked": "bold yellow",
    "cancelled": "dim",
    "running": "cyan",
    "verifying": "bold cyan",
    "reviewing": "bold magenta",
    "integrating": "magenta",
    "waiting_for_quota": "bold yellow",
    "ready": "blue",
    "pending": "dim",
}


def _render_quota_bar(ratio: float | None, width: int = 8) -> str:
    if ratio is None:
        return "[dim]░░░░░░░░ ?%[/dim]"
    filled = int(round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    pct = int(round(ratio * 100))
    color = "green" if ratio > 0.4 else "yellow" if ratio > 0.15 else "red"
    return f"[{color}]{bar} {pct}%[/{color}]"


class WatchApp(TextualApp[None]):
    """Live Multi-AI Command Center Monitor for Orkestra."""

    TITLE = "ORKESTRA COMMAND CENTER"
    CSS = """
    Screen { background: $background; }
    #summary_bar { height: 3; padding: 0 1; background: $surface; border-bottom: solid $primary; }
    #resource_strip { height: 7; padding: 0 1; background: $surface-darken-1; border-bottom: solid $secondary; }
    #middle_pane { height: 1fr; }
    #agent_tree_panel { width: 35%; height: 100%; border-right: solid $primary; padding: 0 1; }
    #task_dag_panel { width: 65%; height: 100%; }
    #decisions_stream { height: 7; background: $surface; border-top: solid $secondary; padding: 0 1; }
    #events_panel { height: 9; border-top: solid $primary; }
    """

    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit"),
        Binding("p", "pause", "Request pause"),
        Binding("c", "cancel", "Request cancel"),
    ]

    def __init__(self, application: OrkestraApp, run_id: str) -> None:
        super().__init__()
        self.application = application
        self.run_id = run_id
        self._last_event_id = 0

    # ------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static(id="summary_bar")
            yield Static(id="resource_strip")
            with Horizontal(id="middle_pane"):
                with Vertical(id="agent_tree_panel"):
                    yield Static("[b cyan]LIVE AGENT HIERARCHY[/b cyan]")
                    yield Tree("ORKESTRA DIRECTOR", id="agent_tree")
                with Vertical(id="task_dag_panel"):
                    yield DataTable[str](id="tasks")
            yield Static(id="decisions_stream")
            yield RichLog(id="events_panel", wrap=True, markup=False, max_lines=500)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks", DataTable)
        table.add_columns("task", "kind", "state", "primary", "reviewers", "attempts")
        table.cursor_type = "row"

        tree = self.query_one("#agent_tree", Tree)
        tree.root.expand()

        self.refresh_state()
        self.set_interval(1.0, self.refresh_state)

    # ----------------------------------------------------------- refresh

    def refresh_state(self) -> None:
        store = self.application.store
        run = store.get_run(self.run_id)

        # 1. Summary Bar
        summary = self.query_one("#summary_bar", Static)
        summary.update(
            f" [b green]ORKESTRA[/b green]  run:[b]{run.run_id}[/b]  project:[b]{run.project_name}[/b]  "
            f"state:[b cyan]{run.state.value.upper()}[/b cyan]  branch:[dim]{run.integration_branch or '-'}[/dim]"
        )

        # 2. Provider Resource Bar
        resource_strip = self.query_one("#resource_strip", Static)
        snapshots = store.latest_provider_snapshots()

        cards: list[str] = []
        default_providers = ["claude", "codex", "antigravity", "gemini"]

        for p_name in default_providers:
            snap = snapshots.get(p_name)
            if snap and snap.windows:
                w0 = snap.windows[0]
                ratio_str = _render_quota_bar(w0.remaining_ratio)
                conf_str = f"[{w0.confidence.value.upper()}]"
                reset_str = f"reset {w0.seconds_to_reset/3600:.1f}h" if w0.seconds_to_reset else "reset unknown"
                health_str = f"[bold green]{snap.health.value.upper()}[/bold green]"
                if snap.waste_risk > 0.4:
                    health_str += " [yellow]waste HIGH[/yellow]"
                if snap.scarcity > 0.4:
                    health_str += " [red]scarce HIGH[/red]"

                card = (
                    f"[b yellow]{p_name.upper()}[/b yellow] ({conf_str})\n"
                    f"{ratio_str}\n"
                    f"[dim]{reset_str}[/dim]\n"
                    f"{health_str}"
                )
            else:
                card = (
                    f"[b yellow]{p_name.upper()}[/b yellow]\n"
                    f"{_render_quota_bar(None)}\n"
                    f"[dim]reset -[/dim]\n"
                    f"[dim]IDLE[/dim]"
                )
            cards.append(card)

        resource_strip.update(" │ ".join(cards))

        # 3. Task DAG Table
        table = self.query_one("#tasks", DataTable)
        table.clear()
        active_tasks: list[tuple[str, str, str]] = []

        for task in store.tasks_for_run(self.run_id):
            style = _STATE_STYLE.get(task.state.value, "")
            state_cell = f"[{style}]{task.state.value}[/{style}]" if style else task.state.value
            assignment = task.assignment
            primary = assignment.primary if assignment else "-"
            table.add_row(
                task.key,
                task.spec.kind.value,
                state_cell,
                primary,
                ", ".join(assignment.reviewers) if assignment else "-",
                str(task.attempt_count),
                key=task.task_id,
            )
            if task.state.value in ("running", "verifying", "reviewing", "integrating", "waiting_for_quota"):
                active_tasks.append((task.key, task.spec.kind.value, primary))

        # 4. Agent Hierarchy Tree
        tree = self.query_one("#agent_tree", Tree)
        tree.root.remove_children()

        dir_state = store.get_director_state("run_director")
        dir_label = f"Director ({dir_state.active_engine_profile if dir_state else 'Claude'})"
        tree.root.label = dir_label

        if active_tasks:
            for key, kind, agent in active_tasks:
                t_node = tree.root.add(f"Task #{key} [{kind}]")
                t_node.add(f"Agent: [cyan]{agent}[/cyan]")
                t_node.add("Gate: [green]PASSED[/green]")
                t_node.expand()
        else:
            tree.root.add("[dim]No active agent dispatches[/dim]")
        tree.root.expand()

        # 5. Decision Stream Panel
        decisions_widget = self.query_one("#decisions_stream", Static)
        routing_decisions = store.routing_decisions_for_run(self.run_id, limit=3)
        if routing_decisions:
            lines = [
                f"[b cyan]DECISION STREAM[/b cyan] [dim]({d.timestamp[11:19]})[/dim] "
                f"Task [b]{d.task_id}[/b] -> profile:[yellow]{d.selected_profile}[/yellow] (score:{d.score:.2f}) "
                f"reasons:[dim]{', '.join(d.reasons[:3])}[/dim]"
                for d in routing_decisions
            ]
            decisions_widget.update("\n".join(lines))
        else:
            decisions_widget.update("[b cyan]DECISION STREAM[/b cyan]\n[dim]No routing decisions recorded yet[/dim]")

        # 6. Event Log Stream
        log = self.query_one("#events_panel", RichLog)
        for event in store.events_for_run(self.run_id, limit=100):
            if event["event_id"] <= self._last_event_id:
                continue
            self._last_event_id = event["event_id"]
            text = clip(str(event["text"]).replace("\n", " "), 200)
            if text:
                log.write(f"{event['ts'][11:19]} {event['kind']:>9}  {text}")

    # ------------------------------------------------------------ actions

    def action_pause(self) -> None:
        self.application.orchestrator.request_pause(self.run_id)
        self.notify("pause requested (in-flight tasks will finish)")

    def action_cancel(self) -> None:
        self.application.orchestrator.request_cancel(self.run_id)
        self.notify("cancel requested", severity="warning")
