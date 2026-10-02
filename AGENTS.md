# AGENTS.md — Orkestra Operating Contract & Continuity Protocol

This document is the canonical operating contract for any AI coding agent working inside the **Orkestra** codebase.

---

# 1. CORE ARCHITECTURAL DOCTRINE

> **Intelligence proposes. Deterministic kernel disposes.**

- **Kernel Authority:** LLMs recommend actions, strategies, or routing suggestions. Only the deterministic Python kernel (in `src/orkestra/kernel/`) authorizes state transitions, task dispatches, quota gates, policy gates, verification execution, review verdicts, git integration, retries, and human escalations.
- **Dynamic Provider Capability:** Never hardcode fixed roles per provider (e.g. "Claude is architect, Codex is implementer, Antigravity is reviewer"). Provider assignments are dynamically determined by capability, quota, cost, waste-risk, scarcity, and performance.
- **Arbitrary Provider Scalability:** The architecture and UI must support \(2 \dots N\) providers/agents without assuming a fixed count or fixed set.
- **Evidence Over Claims:** Agent claims ("Tests passed", "Task completed", "Quota is 50%") are untrusted until verified by deterministic execution, git diffs, or signed system snapshots.
- **Independent Review:** An implementation attempt cannot self-approve. Cross-profile or cross-provider independent review is strictly enforced.

---

# 2. REPOSITORY STRUCTURE

```text
orkestra/
├── src/orkestra/
│   ├── kernel/          # Deterministic state machine, scheduler, quota & resource router
│   ├── director/        # Logical persistent Director service & prompt construction
│   ├── adapters/        # Provider adapters (Antigravity, Codex CLI, Claude Code, Gemini CLI)
│   ├── policy/          # Rule engine, budgets, gate rules, security constraints
│   ├── store/           # SQLite database persistence & append-only migrations
│   ├── schemas/         # Pydantic state models (tasks, events, decisions, usage)
│   ├── verify/          # Verification runner & gate binding proofs
│   ├── workspace/       # Git worktree & branch isolation manager
│   └── cli/             # Typer CLI application & Textual TUI command center
├── tests/               # Unit, integration, migration & TUI async test suite
├── docs/                # Architecture ADRs, specifications, execution plans & evidence
└── pyproject.toml       # Single source of truth for versioning, dependencies & tooling
```

---

# 3. REQUIRED QUALITY GATES

Before claiming any task or phase is complete, all quality gates must pass cleanly:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run bandit -c pyproject.toml -r src
uv run pip-audit --skip-editable
uv run pytest --cov=orkestra --cov-report=term
uv run coverage report --fail-under=80
uv build
```

---

# 4. CONTINUITY PROTOCOL & RESUME POINTER

Every agent continuing work must follow this sequence before taking action:

1. Read `AGENTS.md` (this file)
2. Read `docs/CURRENT_WORK.md` for the exact active frontier and state
3. Read the relevant Phase in `docs/ORKestra_EXECUTION_PLAN.md`
4. Inspect `git status` and recent `git log`
5. Verify current HEAD matches the pointer in `CURRENT_WORK.md`
6. Execute the `Exact next verification command` from `CURRENT_WORK.md`
7. Continue execution from the exact unfinished boundary

---

# 5. SECURITY & AUTHENTICATION RULES

- Official CLIs / SDKs only (`codex`, `claude`, `agy`).
- NEVER extract OAuth tokens, scrape browser local storage, copy provider credential files, or call private undocumented provider endpoints.
- NEVER rotate credentials to evade rate limits or billing quotas.
- NEVER perform silent pay-as-you-go billing when a subscription quota is empty.
- Treat all provider process output as untrusted external data.

---

# 6. CANONICAL STATE DOCUMENTS

- `docs/ORKestra_EVOLUTION_SPEC.md` — Stable evolution requirement specification.
- `docs/ORKestra_EXECUTION_PLAN.md` — Master phased execution plan with checkboxes & criteria.
- `docs/CURRENT_WORK.md` — Active resume pointer (updated before every major step/compaction).
- `docs/research/PROVIDER_QUOTA_AND_USAGE_RESEARCH_2026-10.md` — Empirical provider research & visibility findings.
- `docs/development/ORKestra_EVOLUTION_EVIDENCE.md` — Verified milestone execution evidence.
