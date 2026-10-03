# ORKESTRA EVOLUTION EXECUTION PLAN

This document details the ordered engineering phases, dependencies, acceptance criteria, and status for the Orkestra Adaptive Multi-AI Command Center implementation.

---

## Phase Summary

- [x] **Phase A — Bootstrap & Research**
  - [x] Audit repository & environment tools
  - [x] Establish durable continuity documentation (`AGENTS.md`, spec, execution plan, current work, evidence)
  - [x] Research provider CLI usage interfaces & status commands
  - [x] Git branch & initial checkpoint commit
- [x] **Phase B — Resource & Routing Schemas & Persistence**
  - [x] Define ProviderUsageSnapshot, QuotaWindow, QuotaSource, QuotaConfidence, RoutingDecision models
  - [x] Implement SQLite schema migrations for provider resources, routing decisions, director state, handoffs
  - [x] Write DB repository methods & unit/migration tests
- [x] **Phase C — Provider Usage Collectors & Redacted Fixtures**
  - [x] Implement usage collectors for Codex CLI, Claude Code, Antigravity CLI, Gemini CLI, Unknown fallback
  - [x] Capture redacted test fixtures for parser verification
  - [x] Implement low-overhead caching & snapshot polling
- [x] **Phase D — Deterministic Adaptive Resource Router**
  - [x] Implement scoring algorithm (task fit, quality floor, waste-risk, scarcity, under-utilization)
  - [x] Implement explainability engine for routing decisions
  - [x] Unit test score boundaries, tie-breakers, and quality floor constraints
- [x] **Phase E — Scheduler Integration & Handoff Infrastructure**
  - [x] Integrate router into Orchestrator dispatch loop
  - [x] Implement `WAITING_FOR_QUOTA` state and bounded sleep
  - [x] Implement mid-task state serialization and successor handoff
  - [x] Implement stagnation detection and automatic profile escalation
- [x] **Phase F — Logical Persistent Director & Failover**
  - [x] Structure persistent Director context in SQLite
  - [x] Implement Director engine failover across providers
  - [x] Support optional provider session continuation
- [x] **Phase G — Command-Center Terminal UI Redesign**
  - [x] Implement header, provider resource cards, live agent tree, task DAG, decision stream
  - [x] Differentiate estimated vs exact quota visually
  - [x] Decouple UI refresh from provider polling
  - [x] Test UI view-models and events with Textual test harness
- [x] **Phase H — CLI Surface, Configuration & Overrides**
  - [x] Expose `orkestra usage` and `orkestra routing explain` commands
  - [x] Extend configuration for adaptive routing, waste-risk, handoffs, overrides
  - [x] Update product documentation (`README.md`, `docs/CLI.md`, `docs/PROVIDERS.md`, etc.)
- [ ] **Phase I — Hardening, Verification & Evidence**
  - [ ] Full quality gate suite execution (ruff, mypy, bandit, pip-audit, pytest, coverage >= 80%, build)
  - [ ] Windows local smoke validation
  - [ ] Demonstration scenarios (reset pressure, multi-window scarcity, quota handoff, stagnation escalation, waiting for quota)
  - [ ] Final evidence report update & milestone push
- [ ] **Phase J — Native Multi-Agent Policy & Nested Worker Governance**
  - [ ] Implement `NativeMultiAgentPolicyConfig` in `src/orkestra/schemas/config.py`:
    - `allow_subagents`: bool = True (Allow provider-native subagents)
    - `allow_agent_teams`: bool = True (Allow provider-native agent teams)
    - `max_nested_workers`: int = 4 (Maximum nested workers)
    - `max_total_concurrent_agents`: int = 8 (Maximum total concurrent agents)
    - `max_subagent_depth`: int = 2 (Maximum depth: 2)
    - `allow_provider_auto_decide`: bool = True (Within Orkestra limits)
    - `count_nested_in_quota`: bool = True (ALWAYS count in quota/resource planning)
  - [ ] Implement deterministic PolicyEngine governance rules for nested dispatches & nesting depth
  - [ ] Integrate nested agent token & concurrency accounting into QuotaTracker & ResourceRouter
  - [ ] Expose subagent hierarchy in Director prompt and Command Center TUI (`agent_tree`)
  - [ ] Write unit & integration tests validating multi-agent constraints and nesting limit enforcement

