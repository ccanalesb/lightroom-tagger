#!/usr/bin/env python3
# Run: python3 .cursor/skills/investigate-job/scripts/inspect_job.py <job-id>
"""Inspect a lightroom-tagger visualizer job by ID."""

import sqlite3
import json
import sys
import re
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parents[4] / "apps/visualizer/visualizer.db"


def find_db():
    if DB_PATH.exists():
        return DB_PATH
    # fallback: backend/visualizer.db
    alt = Path(__file__).parents[4] / "apps/visualizer/backend/visualizer.db"
    if alt.exists():
        return alt
    raise FileNotFoundError(f"Could not find visualizer.db (tried {DB_PATH} and {alt})")


def get_job(conn, job_id):
    c = conn.cursor()
    c.execute(
        "SELECT id, type, status, progress, current_step, created_at, started_at, completed_at, error, error_severity, metadata, logs "
        "FROM jobs WHERE id = ?",
        (job_id,),
    )
    return c.fetchone()


def list_recent(conn, n=10):
    c = conn.cursor()
    c.execute(
        "SELECT id, type, status, progress, current_step, created_at FROM jobs ORDER BY created_at DESC LIMIT ?",
        (n,),
    )
    return c.fetchall()


def parse_latencies(logs):
    """Extract per-batch API latencies from vision_match logs."""
    batch_starts = {}
    latencies = []
    for l in logs:
        msg = l.get("message", "")
        ts = datetime.fromisoformat(l["timestamp"])
        m = re.search(r"\[(.+?)\] Batch (\d+)/\d+", msg)
        if m and "candidates" in msg:
            batch_starts[(m.group(1), m.group(2))] = ts
        elif "[vision_batch] Raw response length:" in msg and batch_starts:
            last_key = list(batch_starts.keys())[-1]
            start = batch_starts.pop(last_key)
            latencies.append((ts - start).total_seconds())
    return latencies


def print_job(row):
    cols = ["id", "type", "status", "progress", "current_step",
            "created_at", "started_at", "completed_at", "error", "error_severity"]
    print("=" * 60)
    for col, val in zip(cols, row[:10]):
        print(f"  {col:<18} {val}")

    meta = json.loads(row[10]) if row[10] else {}
    logs = json.loads(row[11]) if row[11] else []

    print(f"\n  {'metadata':<18}", end="")
    if meta:
        # print key fields inline, skip checkpoint blob
        compact = {k: v for k, v in meta.items() if k != "checkpoint"}
        checkpoint = meta.get("checkpoint", {})
        print(json.dumps(compact))
        if checkpoint:
            processed = checkpoint.get("processed_media_keys", [])
            print(f"  {'checkpoint':<18} version={checkpoint.get('checkpoint_version')} | {len(processed)} keys processed")
    else:
        print("{}")

    print(f"\n  {'log entries':<18} {len(logs)}")

    # Last 5 log messages
    if logs:
        print("\n  --- Last 5 log entries ---")
        for l in logs[-5:]:
            ts = l["timestamp"][11:19]  # HH:MM:SS
            lvl = l.get("level", "info").upper()[:5]
            print(f"  [{ts}] {lvl:<5} {l['message'][:100]}")

    # Latency analysis for vision jobs
    if row[1] == "vision_match" and logs:
        latencies = parse_latencies(logs)
        if latencies:
            print(f"\n  --- API latency ({len(latencies)} calls) ---")
            print(f"  avg={sum(latencies)/len(latencies):.1f}s  "
                  f"min={min(latencies):.1f}s  "
                  f"max={max(latencies):.1f}s")
            slow10 = sum(1 for l in latencies if l > 10)
            slow20 = sum(1 for l in latencies if l > 20)
            print(f"  >10s={slow10} ({slow10/len(latencies)*100:.0f}%)  "
                  f">20s={slow20} ({slow20/len(latencies)*100:.0f}%)")

            # estimate remaining
            progress = row[3] or 0
            if progress and progress < 100:
                # parse total images from current_step e.g. "Matching 118/228"
                m = re.search(r"Matching (\d+)/(\d+)", row[4] or "")
                if m:
                    done, total = int(m.group(1)), int(m.group(2))
                    remaining = total - done
                    avg = sum(latencies) / len(latencies)
                    # batches per image = total calls / done images
                    calls_per_img = len(latencies) / max(done, 1)
                    eta_s = remaining * calls_per_img * avg
                    print(f"\n  --- ETA estimate ---")
                    print(f"  {done}/{total} images done | ~{calls_per_img:.0f} calls/image | avg {avg:.1f}s/call")
                    print(f"  Estimated remaining: {eta_s/3600:.1f} hours")

    print("=" * 60)


def main():
    db = find_db()
    conn = sqlite3.connect(str(db))

    if len(sys.argv) < 2:
        print(f"Usage: python inspect_job.py <job-id>\n       python inspect_job.py --recent [N]\n")
        print("Recent jobs:")
        for r in list_recent(conn):
            print(f"  {r[0]}  {r[1]:<20} {r[2]:<10} {r[5]}")
        conn.close()
        return

    if sys.argv[1] == "--recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        for r in list_recent(conn, n):
            print(f"  {r[0]}  {r[1]:<20} {r[2]:<10} {r[3]:>3}%  {r[4] or ''}  [{r[5]}]")
        conn.close()
        return

    job_id = sys.argv[1]
    row = get_job(conn, job_id)
    conn.close()

    if not row:
        print(f"Job {job_id!r} not found.")
        print("Try: python inspect_job.py --recent")
        sys.exit(1)

    print_job(row)


if __name__ == "__main__":
    main()
