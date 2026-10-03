"""Deterministic human approval gate for high-effect-class operations.

The kernel enforces this gate before authorizing any tool execution at
SE3 (remote evidence) or SE4 (external critical) effect class.

Policy:
- SE0..SE2: auto-approved, no human intervention required.
- SE3: requires explicit human approval token unless the run was pre-authorized.
- SE4: always requires explicit human approval; pre-authorization insufficient.

This module is purely deterministic — it never calls an LLM.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orkestra.schemas.common import utc_now
from orkestra.schemas.tools import EFFECT_CLASS_RANKS, EffectClass

# ---------------------------------------------------------------------------
# Approval decision types
# ---------------------------------------------------------------------------


class ApprovalStatus(StrEnum):
    """Outcome of a human approval gate evaluation."""

    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"


class ApprovalRecord(BaseModel):
    """Immutable record of a human approval decision."""

    model_config = ConfigDict(frozen=True)

    approval_id: str
    run_id: str
    task_key: str
    effect_class: EffectClass
    requested_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: str = "human"
    reason: str = ""
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Inputs to a human approval gate evaluation."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    task_key: str
    effect_class: EffectClass
    description: str
    provider: str = "unknown"
    requested_by: str = "kernel"
    context: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Deterministic approval gate engine
# ---------------------------------------------------------------------------

# SE rank threshold: operations at this rank or above require human approval
_APPROVAL_THRESHOLD_RANK: int = EFFECT_CLASS_RANKS[EffectClass.SE3_REMOTE_EVIDENCE]

# How long a pre-authorization token remains valid (SE3 only)
_PRE_AUTH_TTL_SECONDS: int = 3600  # 1 hour


class HumanApprovalGate:
    """Deterministic kernel gate enforcing human approval for high-effect operations.

    The gate never calls an LLM. It evaluates effect class rank, checks the
    pre-authorization store, issues PENDING records for SE3, and always
    requires interactive approval for SE4.
    """

    def __init__(self) -> None:
        # In-memory pre-authorization tokens: approval_id -> ApprovalRecord
        self._approved: dict[str, ApprovalRecord] = {}
        # Pending requests awaiting human decision: approval_id -> ApprovalRecord
        self._pending: dict[str, ApprovalRecord] = {}

    # ------------------------------------------------------------------
    # Public gate API
    # ------------------------------------------------------------------

    def evaluate(self, request: ApprovalRequest) -> ApprovalRecord:
        """Evaluate whether the requested operation may proceed.

        Returns an ApprovalRecord with status APPROVED, AUTO_APPROVED,
        DENIED, or PENDING.

        Auto-approved  : effect class rank < _APPROVAL_THRESHOLD_RANK (SE0..SE2).
        Pre-auth valid : SE3 with an unexpired pre-authorization token in store.
        Pending        : SE3 with no valid pre-auth (issue to human queue).
        Always pending : SE4 always issues a fresh PENDING record regardless.
        """
        rank = EFFECT_CLASS_RANKS[request.effect_class]
        approval_id = self._make_id(request)

        # SE0..SE2: auto-approve
        if rank < _APPROVAL_THRESHOLD_RANK:
            return ApprovalRecord(
                approval_id=approval_id,
                run_id=request.run_id,
                task_key=request.task_key,
                effect_class=request.effect_class,
                decided_at=utc_now(),
                status=ApprovalStatus.AUTO_APPROVED,
                reason="Effect class below approval threshold (SE0-SE2)",
            )

        # SE4: never pre-authorized; always emit a PENDING record
        if request.effect_class == EffectClass.SE4_EXTERNAL_CRITICAL:
            return self._issue_pending(approval_id, request, force=True)

        # SE3: check pre-auth store
        existing = self._approved.get(approval_id)
        if existing and self._is_valid(existing):
            return existing

        # SE3: no valid pre-auth — issue PENDING
        return self._issue_pending(approval_id, request, force=False)

    def grant(
        self,
        approval_id: str,
        approver: str = "human",
        reason: str = "manually approved",
        ttl_seconds: int = _PRE_AUTH_TTL_SECONDS,
    ) -> ApprovalRecord:
        """Record a human approval decision for a pending request.

        SE3 grants are cached for `ttl_seconds` to reduce interruption on
        repeated similar operations. SE4 grants are single-use only.
        """
        pending = self._pending.pop(approval_id, None)
        effect_class = pending.effect_class if pending else EffectClass.SE3_REMOTE_EVIDENCE

        expires_at: datetime | None = None
        if effect_class != EffectClass.SE4_EXTERNAL_CRITICAL:
            expires_at = utc_now() + timedelta(seconds=ttl_seconds)

        record = ApprovalRecord(
            approval_id=approval_id,
            run_id=pending.run_id if pending else "unknown",
            task_key=pending.task_key if pending else "unknown",
            effect_class=effect_class,
            decided_at=utc_now(),
            status=ApprovalStatus.APPROVED,
            approver=approver,
            reason=reason,
            expires_at=expires_at,
        )

        # Cache SE3 approvals; SE4 are single-use (not stored in _approved)
        if effect_class != EffectClass.SE4_EXTERNAL_CRITICAL:
            self._approved[approval_id] = record

        return record

    def deny(
        self,
        approval_id: str,
        approver: str = "human",
        reason: str = "denied",
    ) -> ApprovalRecord:
        """Record a human denial for a pending request."""
        pending = self._pending.pop(approval_id, None)
        return ApprovalRecord(
            approval_id=approval_id,
            run_id=pending.run_id if pending else "unknown",
            task_key=pending.task_key if pending else "unknown",
            effect_class=pending.effect_class if pending else EffectClass.SE4_EXTERNAL_CRITICAL,
            decided_at=utc_now(),
            status=ApprovalStatus.DENIED,
            approver=approver,
            reason=reason,
        )

    def list_pending(self) -> list[ApprovalRecord]:
        """Return all requests currently awaiting human approval."""
        return list(self._pending.values())

    def is_approved(self, approval_id: str) -> bool:
        """Check if a specific approval ID is currently valid."""
        record = self._approved.get(approval_id)
        return record is not None and self._is_valid(record)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _issue_pending(
        self, approval_id: str, request: ApprovalRequest, *, force: bool
    ) -> ApprovalRecord:
        """Create and store a PENDING record awaiting human review."""
        record = ApprovalRecord(
            approval_id=approval_id,
            run_id=request.run_id,
            task_key=request.task_key,
            effect_class=request.effect_class,
            status=ApprovalStatus.PENDING,
            reason=f"Human approval required for {request.effect_class} effect"
            + (" (SE4: always required)" if force else " (SE3: no valid pre-auth)"),
            metadata={"description": request.description, "provider": request.provider},
        )
        self._pending[approval_id] = record
        return record

    @staticmethod
    def _is_valid(record: ApprovalRecord) -> bool:
        """Check whether an approved record has not expired."""
        if record.status != ApprovalStatus.APPROVED:
            return False
        if record.expires_at is None:
            return True  # No expiry set — indefinitely valid
        return datetime.now(tz=UTC) < record.expires_at

    @staticmethod
    def _make_id(request: ApprovalRequest) -> str:
        """Deterministic approval_id derived from run, task, and effect class.

        SE3 IDs are task-scoped (pre-auth can cover multiple invocations).
        SE4 IDs are unique per request (each invocation requires its own approval).
        """
        if request.effect_class == EffectClass.SE4_EXTERNAL_CRITICAL:
            payload = json.dumps(
                {
                    "run_id": request.run_id,
                    "task_key": request.task_key,
                    "effect_class": request.effect_class,
                    "description": request.description,
                },
                sort_keys=True,
            )
        else:
            payload = json.dumps(
                {
                    "run_id": request.run_id,
                    "task_key": request.task_key,
                    "effect_class": request.effect_class,
                },
                sort_keys=True,
            )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"appr_{digest}"
