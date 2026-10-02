# CURRENT WORK — RESUME POINTER

**Current Phase:** Phase H — CLI Surface, Configuration & Overrides
**Current Objective:** Add `orkestra usage` and `orkestra routing explain` commands to `src/orkestra/cli/main.py` and extend config schema for routing options in `src/orkestra/schemas/config.py`.
**Current Branch:** `feat/adaptive-ai-command-center`
**Current HEAD:** `Checkpoint 6`
**Last Completed Checkpoint:** Checkpoint 6 — Command-Center Terminal UI Redesign (`src/orkestra/cli/watch.py`)

## Active Files
- `src/orkestra/cli/watch.py`
- `src/orkestra/cli/main.py`
- `src/orkestra/schemas/config.py`
- `docs/CLI.md`
- `docs/CONFIGURATION.md`

## Quality Gate Status
- **Tests currently passing:** 60/60 passed
- **Tests currently failing:** 0
- **Ruff / Mypy / Bandit:** Clean

## Known Blockers & Push Status
- **GitHub Push Status:** `PUSH_PENDING`
- **Blocker Detail:** GitHub Personal Access Token for user `BD911-Coder` lacks `createRepository` permission to automatically create a new remote repo via `gh repo create`. Local work proceeding on branch `feat/adaptive-ai-command-center`. Commits are being recorded locally.

## Uncommitted Work Summary
- Completed Phase G (full-screen command center TUI with provider resource cards, live agent hierarchy tree, task DAG, decision explanation stream, and event log).
- Ready to commit Checkpoint 6 and proceed to Phase H.

## Exact Next Action
Expose CLI commands `orkestra usage` and `orkestra routing explain` in `src/orkestra/cli/main.py`.

## Exact Next Verification Command
`uv run pytest tests/cli/test_watch.py`
