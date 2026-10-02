# ORKESTRA EVOLUTION EXECUTION PLAN

This document details the ordered engineering phases, dependencies, acceptance criteria, and status for the Orkestra Adaptive Multi-AI Command Center implementation.

---

## Phase Summary

- [x] **Phase A — Bootstrap & Research**
  - [x] Audit repository & environment tools
  - [x] Establish durable continuity documentation (`AGENTS.md`, spec, execution plan, current work, evidence)
  - [x] Research provider CLI usage interfaces & status commands
  - [x] Git branch & initial checkpoint commit
- [ ] **Phase B — Resource & Routing Schemas & Persistence**
  - [ ] Define ProviderUsageSnapshot, QuotaWindow, QuotaSource, QuotaConfidence, RoutingDecision models
  - [ ] Implement SQLite schema migrations for provider resources, routing decisions, director state, handoffs
  - [ ] Write DB repository methods & unit/migration tests
- [ ] **Phase C — Provider Usage Collectors & Redacted Fixtures**
  - [ ] Implement usage collectors for Codex CLI, Claude Code, Antigravity CLI, Gemini CLI, Unknown fallback
  - [ ] Capture redacted test fixtures for parser verification
  - [ ] Implement low-overhead caching & snapshot polling
- [ ] **Phase D — Deterministic Adaptive Resource Router**
  - [ ] Implement scoring algorithm (task fit, quality floor, waste-risk, scarcity, under-utilization)
  - [ ] Implement explainability engine for routing decisions
  - [ ] Unit test score boundaries, tie-breakers, and quality floor constraints
- [ ] **Phase E — Scheduler Integration & Handoff Infrastructure**
  - [ ] Integrate router into Orchestrator dispatch loop
  - [ ] Implement `WAITING_FOR_QUOTA` state and bounded sleep
  - [ ] Implement mid-task state serialization and successor handoff
  - [ ] Implement stagnation detection and automatic profile escalation
- [ ] **Phase F — Logical Persistent Director & Failover**
  - [ ] Structure persistent Director context in SQLite
  - [ ] Implement Director engine failover across providers
  - [ ] Support optional provider session continuation
- [ ] **Phase G — Command-Center Terminal UI Redesign**
  - [ ] Implement header, provider resource cards, live agent tree, task DAG, decision stream
  - [ ] Differentiate estimated vs exact quota visually
  - [ ] Decouple UI refresh from provider polling
  - [ ] Test UI view-models and events with Textual test harness
- [ ] **Phase H — CLI Surface, Configuration & Overrides**
  - [ ] Expose `orkestra usage` and `orkestra routing explain` commands
  - [ ] Extend configuration for adaptive routing, waste-risk, handoffs, overrides
  - [ ] Update product documentation (`README.md`, `docs/CLI.md`, `docs/PROVIDERS.md`, etc.)
- [ ] **Phase I — Hardening, Verification & Evidence**
  - [ ] Full quality gate suite execution (ruff, mypy, bandit, pip-audit, pytest, coverage >= 80%, build)
  - [ ] Windows local smoke validation
  - [ ] Demonstration scenarios (reset pressure, multi-window scarcity, quota handoff, stagnation escalation, waiting for quota)
  - [ ] Final evidence report update & milestone push
