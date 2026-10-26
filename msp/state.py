"""Persistent per-batch state. One JSON file per batch, one record per asset.

Rules enforced here (not in prompts):
- Statuses only move forward through ORDER; a stage cannot be skipped.
- Every transition needs non-empty evidence (no "attempted == done").
- Re-applying the current status is a no-op (idempotent retries).
- Terminal side-states (qc_hold, qc_reject, failed) stop an asset without
  touching the rest of the batch.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

ORDER = [
    "prompt_generated",
    "image_generated",
    "downloaded",
    "qc_passed",
    "metadata_validated",
    "metadata_embedded",
    "sftp_uploaded",
    "portal_configured",
    "submit_approved",
    "submitted",
    "platform_accepted",
]
SIDE = {"qc_hold", "qc_reject", "failed", "platform_rejected"}
RANK = {s: i for i, s in enumerate(ORDER)}


class StateError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_batch(batch_id: str, day: int, plan: list[dict]) -> dict:
    assets = {}
    for i, p in enumerate(plan, 1):
        for key in ("prompt", "type", "aspect"):
            if not p.get(key):
                raise StateError(f"plan item {i} missing {key}")
        assets[str(i)] = {
            "k": i,
            "prompt": p["prompt"],
            "type": p["type"],
            "aspect": p["aspect"],
            "status": "prompt_generated",
            "history": [{"status": "prompt_generated", "at": now(), "evidence": {"source": "plan"}}],
        }
    return {"batch_id": batch_id, "day": day, "created_at": now(), "run_log": [], "assets": assets}


def advance(state: dict, k: int | str, status: str, evidence: dict) -> bool:
    """Move asset k to status. Returns False if already there (no-op)."""
    a = state["assets"][str(k)]
    if not evidence:
        raise StateError(f"asset {k}: transition to {status} without evidence")
    cur = a["status"]
    if cur == status:
        return False
    if cur in SIDE:
        raise StateError(f"asset {k} is {cur}; reset explicitly before advancing")
    if status in SIDE:
        pass  # any active asset may drop out
    else:
        if status not in RANK:
            raise StateError(f"unknown status {status}")
        if RANK[status] != RANK[cur] + 1:
            raise StateError(f"asset {k}: {cur} -> {status} skips or reverses a stage")
    a["status"] = status
    a["history"].append({"status": status, "at": now(), "evidence": evidence})
    return True


def reset(state: dict, k: int | str, to: str, evidence: dict) -> None:
    """Explicitly return a side-state asset (failed/qc_hold) to an active status."""
    a = state["assets"][str(k)]
    if a["status"] not in SIDE:
        raise StateError(f"asset {k} is {a['status']}, not in a side state")
    if to not in RANK or not evidence:
        raise StateError("reset needs a valid target status and evidence")
    a["status"] = to
    a["history"].append({"status": to, "at": now(), "evidence": {"reset": True, **evidence}})


def at_least(asset: dict, status: str) -> bool:
    return asset["status"] in RANK and RANK[asset["status"]] >= RANK[status]


def pending(state: dict, status: str) -> list[dict]:
    """Assets whose next step is `status` (i.e. currently one stage before)."""
    prev = ORDER[RANK[status] - 1]
    return [a for a in state["assets"].values() if a["status"] == prev]


def summary(state: dict) -> dict:
    out: dict[str, int] = {}
    for a in state["assets"].values():
        out[a["status"]] = out.get(a["status"], 0) + 1
    return out


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(state: dict, path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
