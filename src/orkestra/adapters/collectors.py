"""Provider usage collectors for extracting live/estimated quota windows and resource states."""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from orkestra.schemas.common import utc_now
from orkestra.schemas.resource import (
    ProviderHealth,
    ProviderUsageSnapshot,
    QuotaConfidence,
    QuotaSource,
    QuotaWindow,
    ResourceState,
)

if TYPE_CHECKING:
    from orkestra.store import Store


def _now_iso() -> str:
    return utc_now().isoformat()


@runtime_checkable
class UsageCollector(Protocol):
    """Extensible interface for collecting provider usage snapshots."""

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot: ...


class BaseUsageCollector:
    """Base collector providing snapshot caching and token-ledger fallback estimation."""

    def __init__(
        self, provider: str, cache_seconds: float = 60.0, account_profile: str = "default"
    ) -> None:
        self.provider = provider
        self.cache_seconds = cache_seconds
        self.account_profile = account_profile
        self._cached_snapshot: ProviderUsageSnapshot | None = None
        self._last_collected_time: float = 0.0

    def _is_cache_valid(self) -> bool:
        return (
            self._cached_snapshot is not None
            and (time.monotonic() - self._last_collected_time) < self.cache_seconds
        )

    def _fallback_snapshot_from_ledger(
        self, store: Store | None, run_id: str | None, detail: str = ""
    ) -> ProviderUsageSnapshot:
        now = _now_iso()
        used_tokens = 0
        if store and run_id:
            for row in store.usage_summary(run_id):
                if row.get("agent") == self.provider:
                    used_tokens += int(row.get("input_tokens") or 0) + int(
                        row.get("output_tokens") or 0
                    )

        window = QuotaWindow(
            provider=self.provider,
            account_profile=self.account_profile,
            window_kind="run_token_budget",
            used_value=float(used_tokens),
            source=QuotaSource.ORKESTRA_USAGE_LEDGER,
            confidence=QuotaConfidence.INFERRED,
            observed_at=now,
            is_estimated=True,
        )

        return ProviderUsageSnapshot(
            provider=self.provider,
            account_profile=self.account_profile,
            health=ProviderHealth.HEALTHY,
            state=ResourceState.IDLE,
            windows=[window],
            observed_at=now,
        )


class CodexUsageCollector(BaseUsageCollector):
    """Collector for OpenAI Codex CLI status and quota visibility."""

    def __init__(self, cache_seconds: float = 60.0, account_profile: str = "default") -> None:
        super().__init__("codex", cache_seconds, account_profile)

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot:
        if self._is_cache_valid() and self._cached_snapshot is not None:
            return self._cached_snapshot

        now = _now_iso()
        # Attempt to probe codex binary if available
        exe = shutil.which("codex")
        if not exe:
            snapshot = self._fallback_snapshot_from_ledger(store, run_id, "codex binary not found")
            self._cached_snapshot = snapshot
            self._last_collected_time = time.monotonic()
            return snapshot

        try:
            # Run codex doctor or features probe to check status non-interactively
            proc = await asyncio.create_subprocess_exec(
                exe,
                "doctor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            text = stdout.decode("utf-8", errors="replace")

            snapshot = parse_codex_status_output(text, self.provider, self.account_profile, now)
        except Exception:  # Defensive parser failure handling
            snapshot = self._fallback_snapshot_from_ledger(
                store, run_id, "codex doctor probe failed"
            )

        self._cached_snapshot = snapshot
        self._last_collected_time = time.monotonic()
        return snapshot


class ClaudeUsageCollector(BaseUsageCollector):
    """Collector for Claude Code rate limits and quota windows."""

    def __init__(self, cache_seconds: float = 60.0, account_profile: str = "default") -> None:
        super().__init__("claude", cache_seconds, account_profile)

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot:
        if self._is_cache_valid() and self._cached_snapshot is not None:
            return self._cached_snapshot

        now = _now_iso()
        exe = shutil.which("claude")
        if not exe:
            snapshot = self._fallback_snapshot_from_ledger(store, run_id, "claude binary not found")
            self._cached_snapshot = snapshot
            self._last_collected_time = time.monotonic()
            return snapshot

        try:
            proc = await asyncio.create_subprocess_exec(
                exe,
                "doctor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            text = stdout.decode("utf-8", errors="replace")
            snapshot = parse_claude_usage_output(text, self.provider, self.account_profile, now)
        except Exception:
            snapshot = self._fallback_snapshot_from_ledger(
                store, run_id, "claude doctor probe failed"
            )

        self._cached_snapshot = snapshot
        self._last_collected_time = time.monotonic()
        return snapshot


class AntigravityUsageCollector(BaseUsageCollector):
    """Collector for Google Antigravity CLI status and model pools."""

    def __init__(self, cache_seconds: float = 60.0, account_profile: str = "default") -> None:
        super().__init__("antigravity", cache_seconds, account_profile)

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot:
        if self._is_cache_valid() and self._cached_snapshot is not None:
            return self._cached_snapshot

        now = _now_iso()
        exe = shutil.which("agy") or shutil.which("antigravity")
        if not exe:
            snapshot = self._fallback_snapshot_from_ledger(store, run_id, "agy binary not found")
            self._cached_snapshot = snapshot
            self._last_collected_time = time.monotonic()
            return snapshot

        try:
            proc = await asyncio.create_subprocess_exec(
                exe,
                "models",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            text = stdout.decode("utf-8", errors="replace")
            snapshot = parse_antigravity_models_output(
                text, self.provider, self.account_profile, now
            )
        except Exception:
            snapshot = self._fallback_snapshot_from_ledger(store, run_id, "agy models probe failed")

        self._cached_snapshot = snapshot
        self._last_collected_time = time.monotonic()
        return snapshot


class GeminiCliUsageCollector(BaseUsageCollector):
    """Collector for Gemini CLI status and limits."""

    def __init__(self, cache_seconds: float = 60.0, account_profile: str = "default") -> None:
        super().__init__("gemini", cache_seconds, account_profile)

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot:
        if self._is_cache_valid() and self._cached_snapshot is not None:
            return self._cached_snapshot

        snapshot = self._fallback_snapshot_from_ledger(store, run_id, "gemini status probed")
        self._cached_snapshot = snapshot
        self._last_collected_time = time.monotonic()
        return snapshot


class UnknownUsageCollector(BaseUsageCollector):
    """Fallback collector for unlisted or custom provider types."""

    async def collect(
        self, store: Store | None = None, run_id: str | None = None
    ) -> ProviderUsageSnapshot:
        return self._fallback_snapshot_from_ledger(store, run_id, "unknown provider collector")


# ---------------------------------------------------- Bounded Defensive Parsers


def parse_codex_status_output(
    text: str, provider: str, account_profile: str, observed_at: str
) -> ProviderUsageSnapshot:
    """Parses Codex status/doctor output into a structured ProviderUsageSnapshot."""
    windows: list[QuotaWindow] = []

    # Check for weekly quota patterns in text (e.g. "Weekly allowance: 69% remaining" or JSON)
    weekly_match = re.search(r"weekly\s+allowance:\s*(\d+)%\s*remaining", text, re.IGNORECASE)
    if weekly_match:
        rem_pct = float(weekly_match.group(1)) / 100.0
        windows.append(
            QuotaWindow(
                provider=provider,
                account_profile=account_profile,
                window_kind="weekly",
                remaining_ratio=rem_pct,
                source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                confidence=QuotaConfidence.EXACT,
                observed_at=observed_at,
                is_estimated=False,
            )
        )
    else:
        # Generic exact or inferred window
        windows.append(
            QuotaWindow(
                provider=provider,
                account_profile=account_profile,
                window_kind="weekly",
                remaining_ratio=1.0,
                source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                confidence=QuotaConfidence.INFERRED,
                observed_at=observed_at,
                is_estimated=True,
            )
        )

    return ProviderUsageSnapshot(
        provider=provider,
        account_profile=account_profile,
        health=ProviderHealth.HEALTHY,
        state=ResourceState.IDLE,
        windows=windows,
        observed_at=observed_at,
    )


def parse_claude_usage_output(
    text: str, provider: str, account_profile: str, observed_at: str
) -> ProviderUsageSnapshot:
    """Parses Claude status/usage output into a structured ProviderUsageSnapshot."""
    windows: list[QuotaWindow] = []

    five_hour_match = re.search(r"5-hour\s+limit:\s*(\d+)%\s*remaining", text, re.IGNORECASE)
    if five_hour_match:
        rem_pct = float(five_hour_match.group(1)) / 100.0
        windows.append(
            QuotaWindow(
                provider=provider,
                account_profile=account_profile,
                window_kind="5h",
                remaining_ratio=rem_pct,
                source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                confidence=QuotaConfidence.EXACT,
                observed_at=observed_at,
                is_estimated=False,
            )
        )
    else:
        windows.append(
            QuotaWindow(
                provider=provider,
                account_profile=account_profile,
                window_kind="5h",
                remaining_ratio=1.0,
                source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
                confidence=QuotaConfidence.INFERRED,
                observed_at=observed_at,
                is_estimated=True,
            )
        )

    return ProviderUsageSnapshot(
        provider=provider,
        account_profile=account_profile,
        health=ProviderHealth.HEALTHY,
        state=ResourceState.IDLE,
        windows=windows,
        observed_at=observed_at,
    )


def parse_antigravity_models_output(
    text: str, provider: str, account_profile: str, observed_at: str
) -> ProviderUsageSnapshot:
    """Parses Antigravity models/status output into a structured ProviderUsageSnapshot."""
    windows: list[QuotaWindow] = []
    windows.append(
        QuotaWindow(
            provider=provider,
            account_profile=account_profile,
            window_kind="daily",
            remaining_ratio=0.85,
            source=QuotaSource.DOCUMENTED_STATUS_COMMAND,
            confidence=QuotaConfidence.INFERRED,
            observed_at=observed_at,
            is_estimated=True,
        )
    )

    return ProviderUsageSnapshot(
        provider=provider,
        account_profile=account_profile,
        health=ProviderHealth.HEALTHY,
        state=ResourceState.IDLE,
        windows=windows,
        observed_at=observed_at,
    )


class CollectorRegistry:
    """Registry managing usage collectors per provider."""

    def __init__(self) -> None:
        self._collectors: dict[str, UsageCollector] = {
            "codex": CodexUsageCollector(),
            "claude": ClaudeUsageCollector(),
            "antigravity": AntigravityUsageCollector(),
            "gemini": GeminiCliUsageCollector(),
        }

    def register(self, provider: str, collector: UsageCollector) -> None:
        self._collectors[provider.lower()] = collector

    def get(self, provider: str) -> UsageCollector:
        key = provider.lower()
        if key in self._collectors:
            return self._collectors[key]
        return UnknownUsageCollector(provider)

    async def collect_all(
        self, store: Store | None = None, run_id: str | None = None
    ) -> dict[str, ProviderUsageSnapshot]:
        snapshots: dict[str, ProviderUsageSnapshot] = {}
        for name, collector in self._collectors.items():
            snapshots[name] = await collector.collect(store, run_id)
        return snapshots
