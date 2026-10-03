# ORKESTRA V2: ADAPTIVE MULTI-AI PERFORMANCE & WORK ORCHESTRATION OS
## ARCHITECTURAL & OPERATING SPECIFICATION

This specification formalizes the requirements and architectural contracts for Orkestra V2, evolving from the verified A–K command-center foundation into a full-fidelity General-Purpose Performance Operating System.

---

# 1. CORE OPERATING DOCTRINE

> **Intelligence proposes. Deterministic kernel disposes.**

1. **Kernel Supremacy:** The deterministic Python kernel (`src/orkestra/kernel/`) retains exclusive authority over state transitions, scheduling, quota allocation, policy gating, verification, review approvals, git worktree integrations, and human escalations.
2. **Persistence Over Engine:** The logical brain and task context persist independently of the hosting provider CLI or LLM engine.
3. **Evidence Over Claims:** Task completion requires strongly typed, schema-validated artifacts and deterministic test/linter exits. Self-reported "all tests pass" assertions are untrusted.
4. **Independent Review:** An agent can never approve its own work. Cross-provider or cross-profile independent review is strictly enforced. Native subagents in the same parent hierarchy cannot serve as independent reviewers for each other.
5. **Conservative Quota Provenance:** `UNKNOWN != ABUNDANT`. Unmeasured or unknown quotas are never treated as infinite headroom.

---

# 2. V2 ARCHITECTURAL SUBSYSTEMS

```text
orkestra/
├── src/orkestra/
│   ├── schemas/
│   │   ├── artifacts.py       # Typed execution artifacts (Plan, Arch, Code, Review, Gate, Handoff)
│   │   ├── checkpoints.py     # Versioned atomic checkpoints & state snapshots
│   │   ├── decisions.py       # Append-only decision ledger & revision trees
│   │   ├── topology.py        # Swarm execution topologies & parallel metrics
│   │   ├── resources_v2.py    # Multi-window quota models, headroom & burn velocity
│   │   └── events_v2.py       # Provider-neutral structured trace events
│   ├── kernel/
│   │   ├── artifacts.py       # Artifact validation and completion contracts
│   │   ├── checkpoints.py     # Atomic checkpoint replacement and historical ledger
│   │   ├── resources_v2.py    # Multi-window quota engine & reset pressure calculator
│   │   ├── continuity.py      # Session, context, and worktree switching cost engine
│   │   ├── topology.py        # Swarm topology coordinator & parallel efficiency tracker
│   │   ├── arena.py           # Offline strategy arena & counterfactual evaluation
│   │   └── failure.py         # Failure classification, stagnation detection & escalation
│   ├── report/
│   │   └── replay.py          # Chronological run replay synthesizer & postmortem builder
│   ├── director/
│   │   └── background.py      # Useful background worker scheduler (backlog audits, test gaps)
│   └── cli/
│       ├── watch.py           # TUI Command Center (Live projection of persistent state)
│       └── replay.py          # CLI command: `orkestra replay <run_id>`
```

---

# 3. PHASE REQUIREMENTS & SPECIFICATIONS

## Phase M — Typed Execution Artifacts & Checkpoint Governance
- **Canonical Typed Artifacts:** Every task lifecycle kind must output a validated Pydantic model:
  - `PlanningArtifact`: Objectives, prerequisites, task DAG decomposition.
  - `ArchitectureArtifact`: Component modularization, interface contracts, data models.
  - `ImplementationArtifact`: Changed files list, diff summary, commit SHA, worktree path.
  - `ReviewArtifact`: Independent reviewer verdict (`APPROVED`, `CHANGES_REQUESTED`), severity, findings.
  - `VerificationArtifact`: Gate command outputs, exit codes, environment digests, test counts.
  - `HandoffArtifact`: Checkpointed mission state, dirty worktree status, exact next step.
- **Completion Contract:** A task cannot transition to `COMPLETED` unless:
  1. The canonical artifact validates against its schema.
  2. Required files exist on disk in the worktree.
  3. Verification gates pass cleanly (exit 0).
  4. An independent review has approved the change.
- **Atomic Checkpointing:** Superseded checkpoints are preserved in an append-only historical log. Writes use atomic rename semantics to prevent corruption during unexpected shutdowns.

## Phase N — Resource Intelligence Engine V2
- **Multi-Window Quota Evaluation:** Support concurrent tracking across 5-hour, daily, weekly, and monthly windows. Long-window scarcity strictly caps short-window abundance.
- **Provenance & Confidence:** Every signal records confidence: `EXACT`, `ESTIMATED`, `INFERRED`, `UNKNOWN`.
- **Headroom & Reset Pressure:** Dynamically calculate remaining capacity and impending reset windows. Prefer consuming near-reset quota only when in-scope backlog tasks exist and quality floors are satisfied.
- **Burn Rate Tracking:** Moving average token burn rate and projection to exhaustion.

## Phase O — Session, Context & Execution Continuity
- **Continuity Dimensions:** Model switching cost between sessions:
  - Cache affinity (prompt cache hit potential).
  - Context affinity (repository and lineage understanding).
  - Worktree state (already checked out vs cold checkout).
- **Context Pressure:** Classify pressure: `NORMAL`, `ELEVATED`, `HIGH`, `CRITICAL`. At `CRITICAL`, trigger strategic compaction or handoff before token overflow.

## Phase P — Swarm & Execution Topology Intelligence
- **Topologies:** Support `NONE`, `HIERARCHICAL`, `MESH`, `STAR`, `ADAPTIVE`.
- **Parallel Efficiency:** Compute speedup ($S = T_{seq} / T_{par}$) versus resource multiplier ($R = \text{Tokens}_{par} / \text{Tokens}_{seq}$). Detect negative-yield swarms ($S \approx 1.0$ while $R \gg 1.0$).
- **Useful Background Work:** Non-destructive backlog tasks (test gap analysis, lint cleanup, type annotations) run on surplus capacity during reset pressure.

## Phase Q — Performance Intelligence V2
- **Outcome Memory:** Store task execution signatures, provider performance, and failure modes in SQLite.
- **Counterfactual Routing Evaluation:** Offline comparison of actual routing against baseline strategies (Always Claude, Always Codex, Quota-First).
- **Strategy Arena:** Shadow evaluation of candidate routing policies on benchmark tasks before promotion.
- **Failure Introspection:** Detect stagnation loops (oscillating patches, repeating test failures, cyclic review comments) and trigger profile escalation.

## Phase R — Event Bus, Observability & Replay
- **Structured Neutral Events:** Correlation IDs across Run $\to$ Task $\to$ Agent $\to$ Tool $\to$ Gate.
- **Chronological Run Replay:** Reconstruct exact timeline of events, decisions, and verifications.
- **TUI Command Center:** Textual UI is strictly a read-only projection of persistent SQLite state.

## Phase S — Governance & Final Acceptance
- **Human Approval Gates:** Configurable gates for destructive commands, secret access, or costly metered spending.
- **Scenario Test Matrix:** 33 deterministic integration scenarios validating all resource, continuity, native agent, and security behaviors.
