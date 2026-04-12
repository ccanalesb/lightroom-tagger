"""Tests for checkpoint-aware orphan job recovery on server restart."""

import json
import os
import tempfile
from datetime import datetime

from database import create_job, get_job, init_db


def test_recover_running_job_with_checkpoint_requeues_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "jobs.db")
        db = init_db(db_path)
        job_id = create_job(db, "batch_describe", {})
        meta = {
            "checkpoint": {
                "checkpoint_version": 1,
                "job_type": "batch_describe",
                "fingerprint": "x",
                "processed_pairs": [],
            }
        }
        db.execute(
            "UPDATE jobs SET status = ?, metadata = ?, started_at = ? WHERE id = ?",
            ("running", json.dumps(meta), datetime.now().isoformat(), job_id),
        )
        db.commit()

        from app import _recover_orphaned_jobs

        _recover_orphaned_jobs(db)

        row = get_job(db, job_id)
        assert row is not None
        assert row["status"] == "pending"
        logs = row.get("logs") or []
        messages = [e.get("message", "") for e in logs]
        assert any(
            "Recovered after restart; job re-queued with checkpoint." in m for m in messages
        )


def test_recover_running_job_without_checkpoint_marks_failed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "jobs.db")
        db = init_db(db_path)
        job_id = create_job(db, "batch_describe", {})
        db.execute(
            "UPDATE jobs SET status = ?, metadata = ?, started_at = ? WHERE id = ?",
            ("running", "{}", datetime.now().isoformat(), job_id),
        )
        db.commit()

        from app import _recover_orphaned_jobs

        _recover_orphaned_jobs(db)

        row = get_job(db, job_id)
        assert row is not None
        assert row["status"] == "failed"
        logs = row.get("logs") or []
        messages = [e.get("message", "") for e in logs]
        assert any(
            "This job was still running when the server restarted." in m for m in messages
        )
