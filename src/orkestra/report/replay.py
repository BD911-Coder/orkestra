"""Run Replay Synthesizer for chronological execution timeline reconstruction."""

from __future__ import annotations

from orkestra.schemas.events_v2 import (
    EventType,
    OrkestraEvent,
    ReplayStep,
    RunReplaySummary,
)


class RunReplaySynthesizer:
    """Reconstructs causal timelines from raw event streams for post-hoc auditing."""

    def synthesize(self, run_id: str, events: list[OrkestraEvent]) -> RunReplaySummary:
        """Sorts and synthesizes raw events into chronological human-readable steps."""
        if not events:
            from orkestra.schemas.common import utc_now

            now = utc_now()
            return RunReplaySummary(
                run_id=run_id,
                total_events=0,
                start_time=now,
                end_time=now,
                steps=[],
                final_verdict="NO_EVENTS_RECORDED",
            )

        # Sort chronologically by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        steps: list[ReplayStep] = []
        final_verdict = "IN_PROGRESS"

        for idx, evt in enumerate(sorted_events, start=1):
            title, details = self._render_step(evt)
            if evt.event_type == EventType.RUN_LIFECYCLE:
                state = evt.payload.get("state", "").upper()
                if state in ("COMPLETE", "SUCCEEDED"):
                    final_verdict = "PASSED"
                elif state in ("FAILED", "CANCELLED"):
                    final_verdict = "FAILED"

            steps.append(
                ReplayStep(
                    step_index=idx,
                    timestamp=evt.timestamp,
                    event_type=evt.event_type,
                    title=title,
                    details=details,
                    correlation_id=evt.correlation_id,
                    metadata=evt.payload,
                )
            )

        return RunReplaySummary(
            run_id=run_id,
            total_events=len(sorted_events),
            start_time=sorted_events[0].timestamp,
            end_time=sorted_events[-1].timestamp,
            steps=steps,
            final_verdict=final_verdict,
        )

    @staticmethod
    def _render_step(evt: OrkestraEvent) -> tuple[str, str]:
        p = evt.payload
        match evt.event_type:
            case EventType.RUN_LIFECYCLE:
                state = p.get("state", "UNKNOWN")
                return f"Lifecycle State: {state}", f"Run entered lifecycle state '{state}'"
            case EventType.TASK_DISPATCH:
                task = p.get("task_key", "UNKNOWN")
                prov = p.get("provider", "UNKNOWN")
                topo = p.get("topology", "standard")
                return (
                    f"Dispatch: {task} -> {prov}",
                    f"Task {task} dispatched to provider {prov} under topology {topo}",
                )
            case EventType.QUOTA_TELEMETRY:
                prov = p.get("provider", "UNKNOWN")
                headroom = p.get("composite_headroom", 0.0)
                pressure = p.get("reset_pressure", 0.0)
                return (
                    f"Quota Telemetry: {prov}",
                    f"Headroom: {headroom:.2f} | Reset pressure: {pressure:.2f}",
                )
            case EventType.VERIFICATION_GATE:
                gate = p.get("gate_name", "gate")
                status = p.get("status", "UNKNOWN")
                code = p.get("exit_code", 0)
                return (
                    f"Verification Gate: {gate}",
                    f"Gate evaluated: {status} (exit code: {code})",
                )
            case EventType.REVIEW_VERDICT:
                rev = p.get("reviewer", "UNKNOWN")
                verdict = p.get("verdict", "UNKNOWN")
                return (
                    f"Review Verdict: {verdict}",
                    f"Reviewer {rev} rendered verdict '{verdict}'",
                )
            case EventType.CONTEXT_PRESSURE:
                level = p.get("pressure_level", "NORMAL")
                act = p.get("action", "CONTINUE")
                return (
                    f"Context Pressure: {level}",
                    f"Saturation level {level} -> recommended action: {act}",
                )
            case EventType.CONTINUITY_TRANSITION:
                prev = p.get("from_provider", "none")
                nxt = p.get("to_provider", "none")
                adj = p.get("adjustment", "none")
                return (
                    f"Continuity Transition: {prev} -> {nxt}",
                    f"Session transition applied: {adj}",
                )
            case EventType.STAGNATION_WARNING:
                reps = p.get("repetitions", 0)
                return (
                    f"Stagnation Warning ({reps} repetitions)",
                    "Repetitive failure cycle detected; kernel escalation triggered",
                )
            case _:
                return f"Event: {evt.event_type.value}", str(p)  # type: ignore[unreachable]

    def render_markdown(self, summary: RunReplaySummary) -> str:
        """Renders summary into human-readable markdown timeline."""
        lines = [
            f"# Run Replay: `{summary.run_id}`",
            f"**Final Verdict:** {summary.final_verdict} | **Events:** {summary.total_events}",
            f"**Timeline:** {summary.start_time.isoformat()} -> "
            f"{summary.end_time.isoformat() if summary.end_time else 'ongoing'}",
            "",
            "| Step | Timestamp | Type | Title | Details | Correlation ID |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in summary.steps:
            t_str = s.timestamp.strftime("%H:%M:%S")
            lines.append(
                f"| {s.step_index} | {t_str} | `{s.event_type.value}` | {s.title}"
                f" | {s.details} | `{s.correlation_id}` |"
            )
        return "\n".join(lines)
