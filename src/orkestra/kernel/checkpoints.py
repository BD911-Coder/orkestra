"""Atomic versioned checkpoint management with historical recovery archives."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from orkestra.schemas.common import utc_now


class CheckpointRecord:
    """In-memory or serialized representation of a versioned checkpoint."""

    def __init__(
        self,
        checkpoint_id: str,
        run_id: str,
        stage: str,
        version: int,
        data: dict[str, Any],
        created_at: datetime,
    ) -> None:
        self.checkpoint_id = checkpoint_id
        self.run_id = run_id
        self.stage = stage
        self.version = version
        self.data = data
        self.created_at = created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "run_id": self.run_id,
            "stage": self.stage,
            "version": self.version,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CheckpointRecord:
        return cls(
            checkpoint_id=d["checkpoint_id"],
            run_id=d["run_id"],
            stage=d["stage"],
            version=d["version"],
            data=d.get("data", {}),
            created_at=datetime.fromisoformat(d["created_at"]),
        )


class AtomicCheckpointManager:
    """Manages atomic checkpoint writes, historical archiving, and recovery."""

    def __init__(self, checkpoints_dir: Path) -> None:
        self.checkpoints_dir = checkpoints_dir
        self.history_dir = checkpoints_dir / "history"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        run_id: str,
        stage: str,
        data: dict[str, Any],
    ) -> CheckpointRecord:
        """Atomically persist a checkpoint and archive previous versions."""
        current_file = self.checkpoints_dir / f"checkpoint_{run_id}.json"
        version = 1

        # Check existing version
        if current_file.exists():
            try:
                existing_data = json.loads(current_file.read_text(encoding="utf-8"))
                version = existing_data.get("version", 0) + 1
                # Archive existing into history/
                old_ver = existing_data.get("version", 0)
                old_cid = existing_data.get("checkpoint_id", "init")
                archive_name = f"checkpoint_{run_id}_v{old_ver}_{old_cid}.json"
                archive_path = self.history_dir / archive_name
                shutil.copy2(current_file, archive_path)
            except (json.JSONDecodeError, OSError):
                version = 1

        record = CheckpointRecord(
            checkpoint_id=f"chk_{uuid4().hex[:8]}",
            run_id=run_id,
            stage=stage,
            version=version,
            data=data,
            created_at=utc_now(),
        )

        # Write to temporary file first, then atomic rename
        temp_file = self.checkpoints_dir / f"checkpoint_{run_id}.tmp.{uuid4().hex[:6]}"
        serialized = json.dumps(record.to_dict(), indent=2)

        try:
            temp_file.write_text(serialized, encoding="utf-8")
            temp_file.replace(current_file)
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

        return record

    def load_latest_checkpoint(self, run_id: str) -> CheckpointRecord | None:
        """Load the latest active checkpoint for a run."""
        current_file = self.checkpoints_dir / f"checkpoint_{run_id}.json"
        if not current_file.exists():
            return None
        try:
            data = json.loads(current_file.read_text(encoding="utf-8"))
            return CheckpointRecord.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def list_history(self, run_id: str) -> list[CheckpointRecord]:
        """List all historical superseded checkpoints for a run in chronological order."""
        records: list[CheckpointRecord] = []
        pattern = f"checkpoint_{run_id}_v*.json"

        for p in self.history_dir.glob(pattern):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                records.append(CheckpointRecord.from_dict(data))
            except (json.JSONDecodeError, OSError):
                continue

        # Also include latest if exists
        latest = self.load_latest_checkpoint(run_id)
        if latest:
            records.append(latest)

        records.sort(key=lambda r: (r.version, r.created_at))
        return records

    def rollback(self, run_id: str, target_version: int) -> CheckpointRecord | None:
        """Roll back current checkpoint state to a designated historical version."""
        history = self.list_history(run_id)
        target = next((r for r in history if r.version == target_version), None)
        if not target:
            return None

        # Atomically save target as the new latest version (incremented)
        return self.save_checkpoint(
            run_id=run_id,
            stage=f"rollback_to_v{target_version}",
            data=target.data,
        )
