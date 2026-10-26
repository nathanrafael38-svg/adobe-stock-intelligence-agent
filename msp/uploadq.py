"""Upload queue hand-off to the existing WinSCP batch (Stage 6a) and log reconciliation.

Hand-off contract (matches _tools/adobe_upload.bat):
  1. commit final JPGs into _UPLOAD_QUEUE\\_incoming\\
  2. verify sizes on the device
  3. commit READY.flag LAST
The .bat promotes them atomically and WinSCP uploads with put -delete.
"""
from __future__ import annotations

import re
from pathlib import Path

TRANSFER_RE = re.compile(
    r"^\. (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) Transfer done: '(?P<src>[^']+)' => '(?P<dst>[^']+)' \[(?P<bytes>\d+)\]"
)
ERROR_RE = re.compile(r"^[*.] (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) .*(Error|error occurred|Script: Failed)")


def parse_winscp_log(text: str) -> list[dict]:
    """All successful transfers: {ts, src, dst, name, bytes}."""
    out = []
    for line in text.splitlines():
        m = TRANSFER_RE.match(line.strip("\r"))
        if m:
            src = m["src"]
            out.append({"ts": m["ts"], "src": src, "dst": m["dst"], "name": re.split(r"[\\/]", src)[-1],
                        "bytes": int(m["bytes"])})
    return out


def reconcile(batch, log_text: str) -> list[dict]:
    """Mark queued assets as sftp_uploaded when the log shows a transfer of the
    same filename with the same byte count AFTER they were queued.

    Returns list of changes. Assets whose name matches but bytes differ are
    reported (status unchanged) so a wrong file is never counted as uploaded.
    """
    transfers = parse_winscp_log(log_text)
    changes = []
    for a in batch.in_status("queued"):
        q = next(h for h in reversed(a["history"]) if h["status"] == "queued")["evidence"]
        queued_at = q.get("queued_local_ts", "")  # 'YYYY-MM-DD HH:MM:SS' local PC time
        hits = [t for t in transfers if t["name"] == a["filename"] and t["ts"] >= queued_at]
        if not hits:
            continue
        t = hits[-1]
        if t["bytes"] != q["bytes"]:
            changes.append({"file": a["filename"], "result": "BYTES_MISMATCH", "queued": q["bytes"], "sent": t["bytes"]})
            continue
        batch.transition(a["k"], "sftp_uploaded", {"winscp_bytes": t["bytes"], "log_ts": t["ts"], "remote": t["dst"]},
                         sftp_upload_count=a.get("sftp_upload_count", 0) + 1)
        changes.append({"file": a["filename"], "result": "UPLOADED", "ts": t["ts"]})
    return changes


def ready_flag_text(batch_id: str, files: list[str]) -> str:
    return f"batch={batch_id}\nfiles={len(files)}\n" + "\n".join(files) + "\n"
