# ORKESTRA EVOLUTION SPECIFICATION

## 1. Executive Overview

Orkestra is evolving into a persistent, quota-aware, multi-provider **AI Engineering Command Center**. It autonomously continues software development work across multiple subscription-authenticated coding agents (Google Antigravity, OpenAI Codex CLI, Claude Code, Gemini CLI, and arbitrary future providers) while dynamically optimizing provider selection, model profiles, quota windows, scarcity risks, waste risks, mid-task handoffs, and deterministic fallback options.

---

# 2. Key Architecture Principles

1. **Deterministic Kernel Authority:** LLMs recommend; the Python kernel disposes. State transitions, gate evaluations, dispatch, retries, and review independence remain strictly kernel-owned.
2. **Dynamic Role Assignment:** No fixed roles by provider (e.g. no hardcoded "Claude = architect, Codex = implementer"). Allocations are determined dynamically based on task requirements and provider resource states.
3. **Arbitrary Provider Count:** The kernel, storage layer, resource router, and UI natively support \(2 \dots N\) agents, providers, and profiles.
4. **Independent Review:** Implementation attempts cannot self-approve. Cross-profile or cross-provider verification & review policies are enforced.
5. **Evidence Over Claims:** Quota and task progress are tracked via structured provider outputs, deterministic execution, and git state—never unverified agent assertions.

---

# 3. Target System Capabilities

- **First-Class Provider Resource Model:** Support multiple simultaneous quota windows (e.g. 5-hour rolling limit, weekly allowance, monthly credits) with explicit data provenance (`EXACT`, `ESTIMATED`, `INFERRED`, `UNKNOWN`).
- **Deterministic Adaptive Resource Router:** Scores candidate execution profiles based on task fit, quality floor, time-to-reset expiry pressure, scarcity, target utilization, provider health, and historical performance.
- **Mid-Task Provider Handoff:** On quota exhaustion or rate limits, task state, git diffs, worktree context, and verification history are checkpointed; successor agents resume seamlessly without losing progress.
- **Logical Persistent Director:** The Director role is a logical project entity backed by persistent SQLite memory. It survives provider engine failovers without losing project continuity.
- **Waiting for Quota State:** When all candidate providers are exhausted or cooling down, the scheduler transitions safely to `WAITING_FOR_QUOTA` with bounded sleep rather than busy polling or retry storms.
- **Stagnation Detection & Escalation:** Repeated verification or review failures trigger deterministic escalation (higher model profile, cross-provider handoff, or human decision).
- **Command-Center Terminal UI (TUI):** A rich Textual layout displaying the logical Director, live agent tree, task DAG, real-time provider resource cards, decision stream with plain-language explanations, and event logs.

---

# 4. Security & Compliance Rules

- Official provider CLIs/SDKs only (`codex`, `claude`, `agy`).
- Zero private credential scraping or token extraction.
- Zero rate-limit evasion or billing bypass.
- Default CI runs zero paid provider calls.
