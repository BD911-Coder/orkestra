# PROVIDER QUOTA AND USAGE RESEARCH (2026-10)

## 1. Executive Summary

This document records empirical research on official provider CLI and SDK surfaces for retrieving usage, quota limits, reset windows, and rate limit status as of October 2026.

---

## 2. Provider Inventory & Official Interfaces

### 2.1 OpenAI Codex CLI (`codex-cli 0.159.3`)
- **Location:** `C:\Users\furka\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`
- **Automation Surface:** `codex exec`, `codex doctor`, `codex app-server`, `codex features`
- **Quota / Usage Inspection:**
  - Interactive mode exposes status and rate-limit details.
  - Subprocess execution captures rate limit output (`429 Too Many Requests`, retry-after headers, rate-limit state in JSON/NDJSON outputs).
- **Data Provenance:** `EXACT` when parsed from status commands/rate-limit response headers; `INFERRED` / `ESTIMATED` when tracked via Orkestra's token usage ledger.

### 2.2 Claude Code (`claude 2.1.280`)
- **Location:** `C:\Users\furka\.local\bin\claude.exe`
- **Automation Surface:** `claude doctor`, `claude project`, `claude agents`
- **Quota / Usage Inspection:**
  - Exposes plan rate-limit warnings and `/usage` state.
  - Rate limit errors report wait/reset windows.
- **Data Provenance:** `EXACT` when parsed from rate limit / quota state output; `ESTIMATED` via Orkestra local token ledger.

### 2.3 Google Antigravity CLI (`agy 1.2.15`)
- **Location:** `C:\Users\furka\AppData\Local\agy\bin\agy.exe`
- **Automation Surface:** `agy models`, `agy agents`, `agy --print --output-format json`
- **Quota / Usage Inspection:**
  - `agy models` reports available models (`antigravity-pro`, `antigravity-flash`, etc.).
  - Output stream reports model/token usage.
- **Data Provenance:** `ESTIMATED` / `INFERRED` via token usage and rate limit error captures.

### 2.4 Gemini CLI
- Integrated via standard API key / Vertex auth status probe.

---

## 3. Quota Extraction Hierarchy

To maintain high data integrity without violating security rules:

1. **Documented Machine-Readable Output:** Structured JSON/NDJSON from CLI invocation.
2. **Documented CLI Output:** Text output from official status / doctor / models subcommands.
3. **Normalized Rate-Limit & Reset Errors:** Extract reset countdowns from error payloads.
4. **Orkestra Token Ledger:** Inferred remaining allowance based on local per-run / historical usage logs.
5. **UNKNOWN:** Explicit fallback when quota cannot be determined. Never fabricate fake numbers.
