# ECC (Everything Claude Code) Reference Audit & Adaptation Analysis

**Date:** 2026-10-03  
**Auditor:** Antigravity / Orkestra Lead Autonomous Implementation Engine  
**Local Reference Path:** `C:\projects\references\ECC`  
**Upstream Repository:** `https://github.com/affaan-m/ECC`  
**Audited Git Commit SHA:** `ef648e01899ba3e8dc6371642deaaf64b4477775`  
**Detected Version:** `2.2.3` (`ecc-universal`)  

---

## 1. Executive Summary

A comprehensive reference audit of the ECC (Everything Claude Code / Universal Agent Harness Operating System) codebase was conducted to inform the expansion of Orkestra into a **General-Purpose AI Performance and Work Orchestration Operating System (Phase K)**.

ECC represents an exhaustive ecosystem of agent workflows, skills, multi-harness adapters (Claude Code, OpenAI Codex, OpenCode, Cursor, Gemini), hooks, token optimization protocols, session snapshot specifications (`ecc.session.v1`), and an experimental evaluation capsule harness.

### Operating Boundary & Inviolable Principles
1. **Zero Runtime Dependency:** Orkestra **does not** depend on Node.js, npm, or ECC at runtime. Orkestra is a pure Python application powered by uv, Textual, Typer, and SQLite.
2. **No Repository Vendoring:** Orkestra will not copy ECC's hundreds of individual domain skill directories or Node hooks into `src/orkestra`.
3. **Deterministic Kernel Authority:** LLMs and external adapters propose actions, skills, or candidates. The deterministic Python kernel (`src/orkestra/kernel/`) disposes, verifies, gates, and authorizes state changes.
4. **Clean Native Reimplementation:** Architectural principles derived from ECC are reimagined as clean, typed Python abstractions complying with Orkestra's schema, SQLite persistence, and security doctrine.

---

## 2. Detailed Subsystem Audit

### 2.1 Multi-Harness & Session Architecture
- **ECC Artifacts:** `docs/architecture/cross-harness.md`, `docs/architecture/session-adapter-contract.md`, `scripts/lib/session-adapters/canonical-session.js`.
- **Findings:**
  - ECC defines `ecc.session.v1` as a canonical JSON snapshot normalizing tmux worktrees, local process histories, and worker states (`running`, `healthy`, `intent`, `artifacts`).
  - Distinguishes shared assets (`SKILL.md`, rules, instructions) from harness-specific adapters (Claude native hooks, OpenCode plugins, Codex instruction layer).
  - Effect classes (`SE0` to `SE4`) categorize tool and action impacts:
    - `SE0`: Read-only evaluation / schema validation.
    - `SE1`: Reversible local writes inside work root.
    - `SE2`: Process/filesystem mutation without live network writes.
    - `SE3`: Append-only remote evidence publication.
    - `SE4`: Economic, counterparty, payment, or secret handling.
- **Orkestra Adaptation:**
  - Adopt effect classes (`SE0`-`SE4`) into Orkestra's tool and policy registries (`src/orkestra/tools/registry.py`) to govern tool permissions and replay safety deterministically.
  - Extend Orkestra's native session hierarchy: `Provider -> Profile -> Session -> Agent -> Subagent`.

### 2.2 Token Optimization & Context Intelligence
- **ECC Artifacts:** `docs/token-optimization.md`, `skills/strategic-compact/`, `skills/token-budget-advisor/`.
- **Findings:**
  - Identifies token exhaustion and context pollution as primary drivers of agent degradation.
  - Recommends explicit compaction breakpoints (post-planning, post-debugging, pre-focus switch).
  - Distinguishes subagent models (e.g. lightweight models for exploration/file reading) vs primary reasoning models.
  - Alerts on context growth thresholds and loop conditions.
- **Orkestra Adaptation:**
  - Build `ContextIntelligenceEngine` (`src/orkestra/kernel/context.py`).
  - Track session-level context window consumption, token velocities, and compaction boundaries.
  - Differentiate session context exhaustion from subscription quota exhaustion (a provider may have abundant quota but an exhausted session context window requiring compaction or fresh session fork).

### 2.3 Continuous Learning & Instinct Evolution
- **ECC Artifacts:** `skills/continuous-learning-v2/`, `scripts/lib/instinct-relevance.js`, `tests/skills/observer-status-instinct-count.test.js`.
- **Findings:**
  - ECC evolved from coarse skill generation to atomic "instincts": structured observations (`id`, `trigger`, `confidence` 0.3-0.9, `domain`, `evidence`, `scope`).
  - Scopes instincts into project-isolated vs global to prevent cross-contamination.
  - Hooks into tool use lifecycle to detect repeated workflows and errors.
- **Orkestra Adaptation:**
  - Implement Orkestra's **Continuous Learning & Policy Engine** (`src/orkestra/policy/learning.py`).
  - Strict lifecycle: `Observation -> Hypothesis -> Candidate Policy -> Shadow Evaluation -> Human/Kernel Promotion/Rejection`.
  - Inviolable constraint: Learned policies *cannot* relax or rewrite security gates, quota limits, or deterministic kernel rules.

### 2.4 Evaluation, Replay & Capsule Harness
- **ECC Artifacts:** `docs/architecture/eval-harness-frameworks.md`, `scripts/lib/eval-harness/`, `ecc2/src/harness_eval.rs`.
- **Findings:**
  - Five core evaluation modules: Envelope, Capsule (append-only NDJSON journal with sha256 predecessor chaining), Gate, Replay (fail-closed fixtures, effect fence), Receipt (verifiable offline proof with detached signature).
- **Orkestra Adaptation:**
  - Complement existing verification runner with generalized artifact evaluators (`src/orkestra/verify/evaluators.py`):
    - Software code & test gates.
    - Research & factual consistency evaluators.
    - Document, audio, video, and data asset evaluators.
  - Telemetry tracking: `pass@1`, `pass@N`, repair count, duration, token cache efficiency.

### 2.5 Skill Discovery & Lazy Loading
- **ECC Artifacts:** `skills/*/SKILL.md`, `docs/architecture/SELECTIVE-INSTALL-ARCHITECTURE.md`.
- **Findings:**
  - Over 100 domain-specific skills exist in ECC. Preloading all skills exhausts prompt context.
  - Selective activation loads only relevant skills based on intent matching and repository marker detection.
- **Orkestra Adaptation:**
  - Implement `CapabilityRegistry` and `ToolRegistry` (`src/orkestra/capabilities/registry.py`, `src/orkestra/tools/registry.py`).
  - Lazy resolution: match task requirements to capability descriptors, injecting only required tool schemas and guidelines into agent prompts.
  - Security scanner for external capability imports (`src/orkestra/capabilities/scanner.py`) to verify schema validity and detect prompt injection attempts.

---

## 3. Concepts Adopted vs. Rejected

| Concept | Source in ECC | Disposition | Orkestra Architecture Location | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Effect Classes (SE0-SE4)** | `eval-harness/envelope.js` | **ADOPTED** | `src/orkestra/schemas/tools.py`, `policy/` | Clean categorization of tool side effects and safety boundaries. |
| **Context Compaction Boundaries** | `token-optimization.md` | **ADOPTED** | `src/orkestra/kernel/context.py` | Proactively triggers compaction or session restart before degradation. |
| **Atomic Instincts & Promotion** | `continuous-learning-v2` | **ADOPTED** | `src/orkestra/policy/learning.py` | Safe, empirical policy evolution from observations to shadow evaluation. |
| **Artifact / Multi-Domain Evaluators** | `eval-harness/` | **ADOPTED** | `src/orkestra/verify/evaluators.py` | Generalizes Orkestra from pure software coding to arbitrary technical tasks. |
| **Lazy Skill & Capability Matching** | `skills/*/SKILL.md` | **ADOPTED** | `src/orkestra/capabilities/registry.py` | Context-efficient dynamic capability resolution without prompt pollution. |
| **Untrusted Capability Scanner** | Security guidelines | **ADOPTED** | `src/orkestra/capabilities/scanner.py` | Validates external/imported skills before allowing execution. |
| **Node.js / npm Runtime** | ECC package root | **REJECTED** | N/A | Orkestra is self-contained Python (`uv`). No external runtime bloat. |
| **Wholesale Vendoring of 100+ Skills** | `skills/` | **REJECTED** | N/A | Bloats repository; replaced by dynamic capability discovery and clean interfaces. |
| **Ad-Hoc Shell/Tmux Orchestration** | `scripts/` | **REJECTED** | N/A | Orkestra relies on SQLite-backed deterministic kernel and worktrees. |
| **Uncontained Candidate Execution** | `eval-harness/gate.js` | **REJECTED** | N/A | All candidates run under strict policy boundaries and deterministic gates. |

---

## 4. Attribution & Licensing Notice

ECC is licensed under the MIT License by Affaan Mustafa and contributors.
Orkestra respects all MIT license terms. No proprietary code from ECC is copied verbatim. Conceptual designs, effect taxonomies, and architectural patterns referenced from ECC commit `ef648e01899ba3e8dc6371642deaaf64b4477775` are noted with gratitude.
