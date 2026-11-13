"""Per-batch persistent state (compatible with the existing _state/C{N}.json).

Every asset is one traceable unit of work. A status is only recorded together
with evidence; attempted actions are never recorded as completed.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Ordered lifecycle. Branch states are listed separately.
LIFECYCLE = [
    "prompt_generated",
    "image_generated",
    "downloaded",
    "qc_passed",
    "metadata_validated",
    "metadata_embedded",
    "queued",
    "sftp_uploaded",
    "fields_configured",
    "submit_approved",
    "submitted",
    "platform_accepted",
]
BRANCH = ["qc_reject", "qc_review", "upscale_pending", "platform_rejected", "failed", "skipped"]
ALL = set(LIFECYCLE) | set(BRANCH)

# Which statuses may follow which. 'failed' and 'skipped' are allowed from anywhere.
TRANSITIONS: dict[str, set[str]] = {
    None: {"prompt_generated"},
    "prompt_generated": {"image_generated"},
    "image_generated": {"downloaded"},
    "downloaded": {"qc_passed", "qc_reject", "qc_review", "upscale_pending"},
    "upscale_pending": {"downloaded"},  # re-ingest of the upscaled file
    "qc_review": {"qc_passed", "qc_reject"},
    "qc_passed": {"metadata_validated", "qc_reject"},  # visual QC can still reject
    "metadata_validated": {"metadata_embedded"},
    "metadata_embedded": {"queued", "metadata_validated"},
    "queued": {"sftp_uploaded"},
    "sftp_uploaded": {"fields_configured", "submitted"},  # "submitted" only as a manual submission (see transition)
    "fields_configured": {"submit_approved", "fields_configured", "submitted"},
    "submit_approved": {"submitted"},
    "submitted": {"platform_accepted", "platform_rejected"},
    "qc_reject": {"prompt_generated"},  # only via `msp regenerate` (tech aspect_mismatch)
    "platform_accepted": set(),
    "platform_rejected": set(),
    "failed": {"prompt_generated"},  # explicit reset only
    "skipped": set(),
}

# Evidence keys required before a status may be recorded.
REQUIRED_EVIDENCE = {
    "image_generated": {"project", "prompt_match"},
    "downloaded": {"sha256", "source", "saved_as"},
    "qc_passed": {"stage"},
    "qc_reject": {"stage"},
    "metadata_embedded": {"verified", "sha256", "bytes"},
    "queued": {"sha256", "bytes", "device_path"},
    "sftp_uploaded": {"winscp_bytes", "log_ts"},
    "fields_configured": {"category", "ai_label"},
    "submit_approved": {"approved_by", "approval_text"},
    "submitted": {"portal_evidence"},
    "failed": {"error"},
}


class StateError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Batch:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data

    # ---------- persistence ----------
    @classmethod
    def load(cls, path: Path) -> "Batch":
        with open(path, encoding="utf-8") as f:
            return cls(path, json.load(f))

    @classmethod
    def create(cls, path: Path, batch_id: str, n: int, plan: list[dict], filenames: list[str]) -> "Batch":
        if path.exists():
            raise StateError(f"{path} already exists; refusing to overwrite a batch")
        assets = {}
        ts = now()
        for k, (item, fn) in enumerate(zip(plan, filenames), start=1):
            assets[str(k)] = {
                "k": k,
                "concept": item["concept"],
                "prompt": item["prompt"],
                "type": item["type"],
                "aspect": item["aspect"],
                "filename": fn,
                "status": "prompt_generated",
                "sftp_upload_count": 0,
                "history": [{"status": "prompt_generated", "at": ts, "evidence": {"source": "plan"}}],
            }
        b = cls(path, {"batch_id": batch_id, "day": n, "created_at": ts, "run_log": [], "approvals": [], "assets": assets})
        b.save()
        return b

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # atomic

    # ---------- access ----------
    def asset(self, k: int | str) -> dict:
        try:
            return self.data["assets"][str(k)]
        except KeyError:
            raise StateError(f"asset {k} not in {self.data['batch_id']}")

    def assets(self) -> list[dict]:
        return [self.data["assets"][key] for key in sorted(self.data["assets"], key=int)]

    def in_status(self, *statuses: str) -> list[dict]:
        return [a for a in self.assets() if a["status"] in statuses]

    # ---------- mutation ----------
    def transition(self, k: int | str, status: str, evidence: dict | None = None, *, force: bool = False, **fields) -> dict:
        if status not in ALL:
            raise StateError(f"unknown status {status}")
        a = self.asset(k)
        cur = a.get("status")
        evidence = evidence or {}
        allowed = TRANSITIONS.get(cur, set()) | {"failed", "skipped"}
        if not force and status not in allowed:
            raise StateError(f"{a['filename']}: {cur} -> {status} not allowed")
        missing = REQUIRED_EVIDENCE.get(status, set()) - set(evidence)
        if missing:
            raise StateError(f"{a['filename']}: {status} needs evidence {sorted(missing)}")
        if status == "submitted" and cur != "submit_approved" and not force:
            # Nathan submitted by hand (Terms + CAPTCHA); only allowed with portal proof and his name on it.
            if evidence.get("submitted_by") != "nathan_manual":
                raise StateError(f"{a['filename']}: {cur} -> submitted needs approval, or evidence submitted_by=nathan_manual")
        if status == "metadata_embedded" and evidence.get("verified") is not True:
            raise StateError("metadata_embedded requires verified=True (read-back)")
        a["status"] = status
        a["history"].append({"status": status, "at": now(), "evidence": evidence})
        a.update(fields)
        self.save()
        return a

    def log(self, event: str, **info) -> None:
        self.data.setdefault("run_log", []).append({"at": now(), "event": event, **info})
        self.save()

    def record_approval(self, kind: str, approved_by: str, text: str, ks: list[int]) -> None:
        self.data.setdefault("approvals", []).append(
            {"at": now(), "kind": kind, "approved_by": approved_by, "text": text, "assets": ks}
        )
        self.save()

    def summary(self) -> dict:
        out: dict[str, int] = {}
        for a in self.assets():
            out[a["status"]] = out.get(a["status"], 0) + 1
        return out


def next_batch_number(state_dir: Path, device_state_names: list[str] | None = None) -> int:
    """Next N = max existing C{N}.json (local + names listed from the device) + 1."""
    import re

    names = [p.name for p in state_dir.glob("C*.json")] + list(device_state_names or [])
    nums = [int(m.group(1)) for n in names if (m := re.fullmatch(r"C(\d+)\.json", n))]
    if not nums:
        raise StateError("no existing batch state found; pass --n explicitly")
    return max(nums) + 1
