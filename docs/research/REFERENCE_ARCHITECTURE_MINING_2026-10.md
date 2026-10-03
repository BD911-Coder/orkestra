# ORKESTRA V2 — REFERENCE ARCHITECTURE MINING & REVISION AUDIT

This document records the exhaustive technical audit of the local reference repositories (`Ruflo`, `OmniRoute`, `OpenMontage`, and `ECC`), distinguishing actual implementation from documentation claims, and categorizing capabilities into ADOPT, ADAPT, DEFER, or REJECT decisions for Orkestra V2.

---

## 1. Comprehensive Mining Matrix

| Capability Area | Ruflo (`ruflo-main`) | OmniRoute (`OmniRoute-v3.8.52`) | OpenMontage (`OpenMontage-main`) | ECC (`ECC`) | Orkestra V1 Baseline | V2 Decision & Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Typed Stage Artifacts** | Partial (Generic `TaskResult`) | Not implemented | **Implemented** (`lib/checkpoint.py`, `schemas/artifacts/`) | Partial (prompt guidelines) | Partial (`ArtifactBundle`, receipts) | **ADAPT** — Implement canonical typed artifacts per task kind (Research, Plan, Architecture, Implementation, Review, Verification, Handoff). |
| **Atomic Checkpointing** | In-memory `AgentMetrics` | In-memory session state | **Implemented** (`history/` directory, atomic replace) | In-memory / git commits | SQLite rows | **ADAPT** — Implement atomic versioned checkpoint history in SQLite + worktree snapshots. |
| **Append-Only Decision Ledger** | EventBus in-memory | Event emission | **Implemented** (auditable JSON logs) | File logs | Single-row update in SQLite | **ADAPT** — Support decision revisions, supersedes links, and audit history. |
| **Multi-Window Quota Model** | Coarse rate limits | **Implemented** (`scoring.ts`, multi-window affinity) | Not implemented | Provider CLI polling | 1 window per snapshot | **ADOPT** — Support concurrent windows (5h, daily, weekly, monthly) where long-window scarcity overrides short abundance. |
| **Quota Provenance & Confidence** | Absent | Flawed (Unknown treated as 100% headroom) | Absent | Empirical CLI checks | `QuotaSource`, `QuotaConfidence` | **ADAPT & HARDEN** — Maintain `UNKNOWN != ABUNDANT` doctrine; confidence states `EXACT`, `ESTIMATED`, `INFERRED`, `UNKNOWN`. |
| **Reset Pressure & Headroom** | Absent | **Implemented** (`resetWindowAffinity`) | Absent | Basic reset timestamp | `seconds_to_reset` in router | **ADAPT** — Elevate preference for expiring quota ONLY when useful in-scope backlog exists and quality floors are met. |
| **Execution Continuity & Handoff** | Basic memory injection | `contextAffinity`, `cacheAffinity` | **Implemented** (`delivery_promise.py`, pipeline resume) | Compact memory carryover | `mid_task_handoff` in scheduler | **ADAPT** — First-class switching cost modeling (warm session vs cold session) and structured handoff contracts. |
| **Swarm & Execution Topologies** | **Implemented** (`SwarmCoordinator.ts`: hierarchical, mesh, star, adaptive) | Linear model chains | Linear DAG stages | Linear agent calls | Parallel worktrees, native multi-agent policy | **ADAPT** — First-class `ExecutionTopology` schema and measurable parallel efficiency tracking. |
| **Parallelism Efficiency Metrics** | Basic latency logging | Connection density | Not implemented | Token tracking | Wall duration | **ADOPT** — Measure speedup vs compute multiplier ($T_{seq} / T_{par}$ vs resource expenditure); detect negative-yield fanout. |
| **Useful Background Work** | Background workers | Idle connection pool | Not implemented | Idle sweeps | Not implemented | **ADOPT** — Execute non-destructive backlog tasks (test gap analysis, lint/type improvements) during high reset pressure. |
| **Historical Memory & Similar Tasks** | `AgentDB`, vector memory (in-progress) | Cache routing history | Checkpoint history | Project memory file | SQLite performance records | **ADAPT** — Deterministic tokenized keyword similarity and provider/strategy outcome matching. |
| **Strategy Arena & Counterfactuals** | `Arena` (experimental) | A/B testing harnesses | Not implemented | Benchmark loop | Continuous learning / Shadow promotion | **ADAPT** — Offline counterfactual replay comparing actual routing against static provider baselines without LLM gambling. |
| **Structured Replay & Observability** | EventEmitter | SSE trace streaming | **Implemented** (`backlot/` reader) | Markdown dashboards | RichLog in watch TUI | **ADAPT** — Reconstruct exact chronological execution history from persisted event streams. |
| **Deterministic Human Approval Gates** | Advisory hooks | Manual API tokens | **Implemented** (`human_approval_default` per stage) | Manual user prompts | Typer decision prompts | **ADAPT & HARDEN** — Kernel-enforced approval requirements on destructive/economic effect classes (`SE3`/`SE4`). |
| **Independent Review Authority** | Advisory | Not modeled | Advisory reviewer prompt | Prompts | Kernel-enforced implementer $\neq$ reviewer | **MAINTAIN & HARDEN** — Cross-provider review remains mandatory; native subagents in same hierarchy cannot approve each other. |

---

## 2. Deep Dive by Reference Repository

### A. Ruflo (`C:\projects\references\ruflo-main`)
- **Key Source Modules Inspected:**
  - `v3/src/coordination/application/SwarmCoordinator.ts`: Defines `SwarmTopology` (`hierarchical`, `mesh`, `star`, `adaptive`). Maintains `agentMetrics` with execution time and success rate.
  - `v3/src/task-execution/application/WorkflowEngine.ts`: Graph execution of tasks with dependency resolution.
  - `v3/src/shared/types/`: Defines agent lifecycle contracts, mesh connections, and consensus results.
- **Adopted / Adapted:**
  - `SwarmTopology` enum and metadata modeling.
  - Parent-child agent hierarchy tracking with resource and latency attribution.
  - Parallel efficiency metrics calculating whether multi-agent fanout produced real speedup or wasteful duplication.
- **Rejected / Deferred:**
  - Complex in-memory mesh gossip protocol (unnecessary overhead for local-first software orchestration).
  - External vector database dependencies (AgentDB/Qdrant) — deterministic keyword and hash indexing is faster, zero-dependency, and verifiable.

### B. OmniRoute (`C:\projects\references\OmniRoute-release-v3.8.52`)
- **Key Source Modules Inspected:**
  - `open-sse/services/autoCombo/scoring.ts`: 15+ factor candidate scoring model (`quota`, `health`, `costInv`, `latencyInv`, `taskFit`, `stability`, `tierPriority`, `contextAffinity`, `cacheAffinity`, `resetWindowAffinity`, `quality`, `reliability`).
  - `open-sse/services/autoCombo/subscriptionLadder.ts`: Priority ordering between free tiers, subscription pools, and metered models.
  - `open-sse/services/autoCombo/freeAccessQuota.ts`: Multi-window quota tracking and reset projections.
- **Adopted / Adapted:**
  - Multi-window quota evaluation where the most constrained window governs eligibility.
  - Reset pressure optimization favoring expiring quotas only when quality floors are satisfied.
  - Session and context affinity to avoid unnecessary cold-start provider switching costs.
- **Hardened / Corrected:**
  - **OmniRoute Flaw:** When quota is unknown or unmeasured, OmniRoute defaults to treating it as 100% available headroom.
  - **Orkestra Rule:** `UNKNOWN != ABUNDANT`. Unknown quota is flagged with `UNKNOWN` confidence and given a conservative neutral prior to protect against unexpected rate-limit exhaustion.

### C. OpenMontage (`C:\projects\references\OpenMontage-main`)
- **Key Source Modules Inspected:**
  - `lib/checkpoint.py`: Canonical stage artifacts (`CANONICAL_STAGE_ARTIFACTS`), atomic writing with temporary files, and historical archive directory (`history/`).
  - `lib/delivery_promise.py`: Preflight checks and stage prerequisite verification.
  - `schemas/artifacts/`: Schema validation for stage products.
- **License Constraint:** AGPL-3.0. Zero lines of code copied.
- **Adopted / Adapted (Clean-Room Reimplementation):**
  - Strongly typed artifacts for each task lifecycle stage (Planning, Architecture, Implementation, Review, Verification, Handoff).
  - Atomic checkpointing and non-destructive versioned historical tracking in SQLite.
  - Append-only decision revision ledger recording full context and supersedes pointers.
  - Human approval gates on sensitive actions enforced by the deterministic kernel.
- **Rejected:**
  - LLM self-review and loose validation where retry exhaustion silently passes failing stages. In Orkestra, verification failure is terminal unless repaired.

### D. ECC (`C:\projects\references\ECC`)
- **Key Source Modules Inspected:**
  - `skills/`: Comprehensive skill declarations with frontmatter.
  - `contexts/`: Modular context injection patterns.
  - `hooks/`: Execution interceptors.
- **Adopted / Adapted:**
  - Context economics: Lazy skill and capability injection, ensuring only relevant capabilities enter context.
  - Continuous learning loop: Extracting failure patterns and synthesizing policy candidates.
