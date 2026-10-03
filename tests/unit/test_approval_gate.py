"""Tests for Phase S: Human Approval Gate for SE3/SE4 effect classes."""

from __future__ import annotations

from orkestra.kernel.approval import (
    ApprovalRequest,
    ApprovalStatus,
    HumanApprovalGate,
)
from orkestra.schemas.tools import EffectClass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(effect_class: EffectClass, task_key: str = "task_test") -> ApprovalRequest:
    return ApprovalRequest(
        run_id="run_s_test",
        task_key=task_key,
        effect_class=effect_class,
        description=f"Test {effect_class} operation",
        provider="antigravity",
    )


# ---------------------------------------------------------------------------
# SE0-SE2: auto-approval
# ---------------------------------------------------------------------------


def test_se0_auto_approved() -> None:
    """SE0 read-only operations are auto-approved without human involvement."""
    gate = HumanApprovalGate()
    record = gate.evaluate(_req(EffectClass.SE0_READ_ONLY))
    assert record.status == ApprovalStatus.AUTO_APPROVED
    assert record.effect_class == EffectClass.SE0_READ_ONLY


def test_se1_auto_approved() -> None:
    """SE1 local writes are auto-approved."""
    gate = HumanApprovalGate()
    record = gate.evaluate(_req(EffectClass.SE1_LOCAL_WRITE))
    assert record.status == ApprovalStatus.AUTO_APPROVED


def test_se2_auto_approved() -> None:
    """SE2 process mutations (builds, tests) are auto-approved."""
    gate = HumanApprovalGate()
    record = gate.evaluate(_req(EffectClass.SE2_MUTATION))
    assert record.status == ApprovalStatus.AUTO_APPROVED


# ---------------------------------------------------------------------------
# SE3: requires approval, cacheable
# ---------------------------------------------------------------------------


def test_se3_emits_pending() -> None:
    """SE3 remote evidence operations emit PENDING without pre-authorization."""
    gate = HumanApprovalGate()
    record = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE))
    assert record.status == ApprovalStatus.PENDING
    assert len(gate.list_pending()) == 1


def test_se3_grant_caches_approval() -> None:
    """Granting SE3 approval stores a valid token that satisfies repeat evaluations."""
    gate = HumanApprovalGate()
    pending = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE))
    assert pending.status == ApprovalStatus.PENDING

    granted = gate.grant(pending.approval_id, approver="human-operator", reason="approved in CI")
    assert granted.status == ApprovalStatus.APPROVED
    assert gate.is_approved(pending.approval_id)

    # Second evaluation of same operation uses cached approval
    record2 = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE))
    assert record2.status == ApprovalStatus.APPROVED


def test_se3_denial_removes_pending() -> None:
    """Denying a pending SE3 record removes it from the pending queue."""
    gate = HumanApprovalGate()
    pending = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE))

    denied = gate.deny(pending.approval_id, reason="rejected by policy")
    assert denied.status == ApprovalStatus.DENIED
    assert len(gate.list_pending()) == 0
    assert not gate.is_approved(pending.approval_id)


def test_se3_approval_id_is_deterministic() -> None:
    """Two SE3 evaluations for the same run+task produce the same approval_id."""
    gate = HumanApprovalGate()
    r1 = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE, task_key="push_task"))
    r2 = gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE, task_key="push_task"))
    assert r1.approval_id == r2.approval_id


# ---------------------------------------------------------------------------
# SE4: always requires fresh approval, never cached
# ---------------------------------------------------------------------------


def test_se4_always_pending() -> None:
    """SE4 critical operations always emit PENDING; pre-authorization insufficient."""
    gate = HumanApprovalGate()
    record = gate.evaluate(_req(EffectClass.SE4_EXTERNAL_CRITICAL))
    assert record.status == ApprovalStatus.PENDING


def test_se4_grant_is_single_use() -> None:
    """SE4 grants are NOT cached — the next evaluation emits PENDING again."""
    gate = HumanApprovalGate()
    pending = gate.evaluate(_req(EffectClass.SE4_EXTERNAL_CRITICAL))
    gate.grant(pending.approval_id, approver="human")

    # After granting, SE4 approval_id is NOT stored in _approved
    assert not gate.is_approved(pending.approval_id)

    # A fresh SE4 evaluation still requires a new approval
    record2 = gate.evaluate(_req(EffectClass.SE4_EXTERNAL_CRITICAL))
    assert record2.status == ApprovalStatus.PENDING


def test_se4_approval_ids_are_unique_per_request() -> None:
    """SE4 approval_ids differ between evaluations (description-scoped)."""
    gate = HumanApprovalGate()
    r1 = ApprovalRequest(
        run_id="run_s_test",
        task_key="payment",
        effect_class=EffectClass.SE4_EXTERNAL_CRITICAL,
        description="charge card A",
    )
    r2 = ApprovalRequest(
        run_id="run_s_test",
        task_key="payment",
        effect_class=EffectClass.SE4_EXTERNAL_CRITICAL,
        description="charge card B",
    )
    rec1 = gate.evaluate(r1)
    rec2 = gate.evaluate(r2)
    assert rec1.approval_id != rec2.approval_id


# ---------------------------------------------------------------------------
# list_pending and multi-gate state
# ---------------------------------------------------------------------------


def test_list_pending_returns_all_open_requests() -> None:
    """list_pending returns all outstanding PENDING records."""
    gate = HumanApprovalGate()
    gate.evaluate(_req(EffectClass.SE3_REMOTE_EVIDENCE, task_key="git_push"))
    gate.evaluate(_req(EffectClass.SE4_EXTERNAL_CRITICAL, task_key="billing"))
    pending = gate.list_pending()
    assert len(pending) == 2
    statuses = {r.status for r in pending}
    assert statuses == {ApprovalStatus.PENDING}


def test_approval_record_has_correct_run_id_and_task_key() -> None:
    """ApprovalRecord carries the originating run_id and task_key."""
    gate = HumanApprovalGate()
    record = gate.evaluate(
        ApprovalRequest(
            run_id="run_xyz",
            task_key="deploy_prod",
            effect_class=EffectClass.SE4_EXTERNAL_CRITICAL,
            description="deploy to production",
        )
    )
    assert record.run_id == "run_xyz"
    assert record.task_key == "deploy_prod"
