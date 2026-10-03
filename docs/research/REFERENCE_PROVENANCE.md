# ORKESTRA V2 — REFERENCE ARCHITECTURE PROVENANCE & LICENSE POLICY

This document defines the strict intellectual property, license compliance, and provenance tracking policy for all architectural inspirations mined from local reference repositories.

---

## 1. Core Provenance Doctrine

1. **Deterministic Kernel Authority:** Orkestra's deterministic kernel architecture (`src/orkestra/kernel/`) is authoritatively designed in Python. No reference runtime is copied, vendored, or made a dependency.
2. **Clean Reimplementation:** All adopted ideas are independently and natively reimplemented in Python using standard Orkestra schemas and abstractions.
3. **Strict AGPL Boundary:** Code from AGPL-licensed references is **NEVER** copied into Orkestra. Only high-level architectural patterns are studied and reimplemented as clean-room original software.
4. **Attribution Integrity:** Conceptual provenance is documented with transparency, recording source paths and rationales.

---

## 2. Reference Repositories Audit & License Matrix

| Repository | Local Path | License | Permissible Reuse Level | Orkestra Handling |
| :--- | :--- | :--- | :--- | :--- |
| **Ruflo** | `C:\projects\references\ruflo-main` | MIT / Apache-2.0 compatible | Architectural adaptation & structural patterns | Clean Python native reimplementation of Swarm Topology & Parallel Efficiency metrics |
| **OmniRoute** | `C:\projects\references\OmniRoute-release-v3.8.52` | MIT | Architectural adaptation & formula models | Clean Python native reimplementation of multi-window quota, headroom, and reset pressure scoring |
| **OpenMontage** | `C:\projects\references\OpenMontage-main` | **AGPL-3.0** | **READ-ONLY CONCEPTUAL INSPIRATION ONLY** | **NO CODE COPIED**. Clean Python reimplementation of typed artifacts, atomic checkpoints, and append-only decision ledgers |
| **ECC** | `C:\projects\references\ECC` | MIT | Architectural adaptation & benchmark concepts | Clean Python reimplementation of context optimization and lazy capability loading |

---

## 3. Specific Subsystem Conceptual Provenance

### Phase M — Typed Execution Artifacts & Checkpoint Governance
- **Inspiration Source:** OpenMontage (`lib/checkpoint.py`, `schemas/artifacts/`)
- **License Constraint:** AGPL-3.0 — **Zero code copied**.
- **Orkestra Implementation:** Clean Pydantic schemas in `src/orkestra/schemas/artifacts.py` and atomic checkpoint management in `src/orkestra/kernel/checkpoints.py` integrating directly into Orkestra SQLite persistence.

### Phase N — Resource Intelligence Engine V2
- **Inspiration Source:** OmniRoute (`open-sse/services/autoCombo/scoring.ts`, `subscriptionLadder.ts`, `freeAccessQuota.ts`)
- **License Constraint:** MIT
- **Orkestra Implementation:** Clean Python implementation in `src/orkestra/kernel/resources_v2.py` implementing multi-window quotas (5h, daily, weekly, monthly), quota provenance confidence, headroom, reset pressure, and burn rate. Rejects OmniRoute's unknown-is-abundant flaw (`UNKNOWN != ABUNDANT`).

### Phase P — Swarm & Execution Topology Intelligence
- **Inspiration Source:** Ruflo (`v3/src/coordination/application/SwarmCoordinator.ts`)
- **License Constraint:** MIT
- **Orkestra Implementation:** Native topology representation in `src/orkestra/schemas/topology.py` (`HIERARCHICAL`, `MESH`, `STAR`, `ADAPTIVE`), nested worker tracking, and parallel efficiency measurement in `src/orkestra/kernel/topology.py`.

### Phase Q & R — Performance Intelligence & Replay Event Bus
- **Inspiration Source:** Ruflo (Arena / Metrics), OpenMontage (Event replay, Backlot observer)
- **License Constraint:** MIT / AGPL-3.0 conceptual
- **Orkestra Implementation:** Native event hierarchy, chronological replay synthesizer in `src/orkestra/report/replay.py`, and counterfactual evaluation in `src/orkestra/kernel/counterfactual.py`.
