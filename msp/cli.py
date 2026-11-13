"""Command-line entry point used by the orchestrator agent.

    python -m msp <command> [...]

All commands are idempotent: re-running a command never repeats a stage an
asset has already passed, and never overwrites a file with different content.
Device transfers (stage/commit) are done by the agent with its device tools;
this CLI only works on the local workspace mirror.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import config as C
from . import metadata as M
from . import plan as P
from . import qc as Q
from . import uploadq as U
from .state import Batch, StateError, next_batch_number


def _batch(cfg, n) -> Batch:
    return Batch.load(C.local_state_dir() / f"{C.batch_id(cfg, n)}.json")


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _ks(b: Batch, ks):
    return [b.asset(k) for k in ks] if ks else b.assets()


# ---------------- Stage 1 ----------------
def cmd_next_n(a, cfg):
    _out({"next_n": next_batch_number(C.local_state_dir(), a.device_names)})


def cmd_validate_plan(a, cfg):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    errs = P.validate(plan, cfg, P.history_concepts(C.local_state_dir()))
    _out({"valid": not errs, "errors": errs})
    return 0 if not errs else 2


def cmd_init(a, cfg):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    errs = P.validate(plan, cfg, P.history_concepts(C.local_state_dir()))
    if errs and not a.allow_invalid:
        _out({"created": False, "errors": errs})
        return 2
    bid = C.batch_id(cfg, a.n)
    fns = [C.filename(cfg, a.n, k) for k in range(1, len(plan) + 1)]
    sd = C.local_state_dir()
    (sd / f"{bid}-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    b = Batch.create(sd / f"{bid}.json", bid, a.n, plan, fns)
    project = cfg["flow"]["project_pattern"].format(n=a.n)
    sheet = C.local_day(cfg, a.n) / f"PROMPTS_{bid}.xlsx"
    P.prompt_xlsx(sheet, bid, project, plan, fns)
    b.log("init", project=project, assets=len(plan), plan_warnings=errs)
    _out({"created": True, "batch": bid, "project": project, "commit": [
        {"local": str(sd / f"{bid}-plan.json"), "device": C.device_path(cfg, "_state", f"{bid}-plan.json")},
        {"local": str(sd / f"{bid}.json"), "device": C.device_path(cfg, "_state", f"{bid}.json")},
        {"local": str(sheet), "device": C.device_path(cfg, C.day_dir(cfg, a.n), sheet.name)}]})


# ---------------- Stage 2/3 ----------------
def cmd_generated(a, cfg):
    b = _batch(cfg, a.n)
    ev = {"project": a.project, "prompt_match": a.prompt_match, "tile": a.tile, "generated_by": a.by}
    if a.prompt_match != "exact":
        ev["note"] = "prompt text in Flow differs from plan; needs review"
    b.transition(a.k, "image_generated", ev)
    _out(b.asset(a.k)["status"])


def cmd_regenerate(a, cfg):
    """Reset a tech-QC aspect_mismatch reject to prompt_generated so Nathan can regenerate it in Flow.

    Only for wrong-aspect generations (a Flow ratio mistake). Visual rejects and every other
    tech failure stay rejected: a regenerated image of a bad concept is a new asset, not a fix.
    """
    b = _batch(cfg, a.n)
    asset = b.asset(a.k)
    if asset["status"] != "qc_reject":
        raise StateError(f"{asset['filename']} is {asset['status']}; regenerate needs qc_reject")
    ev = asset["history"][-1].get("evidence", {})
    errs = ev.get("errors") or []
    if ev.get("stage") != "tech" or not errs or not all(str(e).startswith("aspect_mismatch") for e in errs):
        raise StateError(f"{asset['filename']}: only tech aspect_mismatch rejects can be regenerated (got {ev})")
    b.transition(a.k, "prompt_generated", {"regenerated": True, "reason": a.reason, "previous_sha256": asset.get("sha256"),
                                          "previous_errors": errs})
    _out(b.asset(a.k)["status"])


def cmd_ingest(a, cfg):
    """Save a downloaded (or upscaled) file as Day N/_original/C{N}_kk.jpg."""
    b = _batch(cfg, a.n)
    asset = b.asset(a.k)
    src = Path(a.src)
    digest = Q.sha256(src)
    dst = C.local_day(cfg, a.n) / "_original" / asset["filename"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and Q.sha256(dst) == digest and asset["status"] not in ("image_generated", "upscale_pending"):
        _out({"skipped": "already ingested", "file": asset["filename"]})
        return 0
    if asset["status"] not in ("image_generated", "upscale_pending"):
        raise StateError(f"{asset['filename']} is {asset['status']}; ingest needs image_generated or upscale_pending")
    if dst.exists():
        prev = dst.with_name(dst.stem + f"__pre_{asset['status']}" + dst.suffix)
        shutil.move(dst, prev)  # never overwrite: keep the earlier version beside it
    shutil.copy2(src, dst)
    ev = {"sha256": digest, "source": a.source_name or src.name, "saved_as": f"_original/{asset['filename']}",
          "bytes": dst.stat().st_size}
    if asset["status"] == "upscale_pending":
        ev["upscaled"] = True
    b.transition(a.k, "downloaded", ev, sha256=digest)
    _out({"ingested": asset["filename"], "sha256": digest,
          "commit": {"local": str(dst), "device": C.device_path(cfg, C.day_dir(cfg, a.n), "_original", asset["filename"])}})


# ---------------- Stage 4 ----------------
def cmd_qc(a, cfg):
    b = _batch(cfg, a.n)
    known = Q.known_hashes_from_states(C.local_state_dir(), exclude_batch=b.data["batch_id"])
    results = []
    for asset in _ks(b, a.k):
        if a.recheck and asset["status"] == "upscale_pending":
            # QC rule changed: re-evaluate the same original before spending an upscale
            last = next(h for h in reversed(asset["history"]) if h["status"] == "downloaded")["evidence"]
            b.transition(asset["k"], "downloaded", {**last, "recheck": "qc rule change, same file"})
            asset.pop("qc_tech_sha", None)
        if asset["status"] != "downloaded" or (asset.get("qc_tech_sha") == asset.get("sha256") and not a.recheck):
            continue
        path = C.local_day(cfg, a.n) / "_original" / asset["filename"]
        own = [(r, h) for r, h in known if not r.endswith(asset["filename"])]
        r = Q.tech_qc(path, asset["type"], asset["aspect"], cfg, own)
        asset["qc_tech"] = r
        asset["qc_tech_sha"] = asset.get("sha256")
        if r["verdict"] == "FAIL":
            already_upscaled = any(h["evidence"].get("upscaled") for h in asset["history"] if h["status"] == "downloaded")
            if r["upscale_eligible"] and not already_upscaled:
                b.transition(asset["k"], "upscale_pending", {"stage": "tech", "errors": r["errors"]})
            else:
                b.transition(asset["k"], "qc_reject", {"stage": "tech", "errors": r["errors"]})
        else:
            b.save()  # stays 'downloaded' until the visual-qc verdict
        results.append({"file": asset["filename"], "verdict": r["verdict"], "errors": r["errors"], "flags": r["flags"],
                        "status": asset["status"]})
    _out(results)


def cmd_review(a, cfg):
    """Record the visual-qc agent verdict: KIRIM (pass), TOLAK (reject), REVIEW (needs Nathan)."""
    b = _batch(cfg, a.n)
    asset = b.asset(a.k)
    if not asset.get("qc_tech") or asset["qc_tech"]["verdict"] == "FAIL":
        raise StateError("visual review requires a non-FAIL technical QC first")
    ev = {"stage": "visual", "verdict": a.verdict, "note": a.note, "checked": a.checked or []}
    target = {"KIRIM": "qc_passed", "TOLAK": "qc_reject", "REVIEW": "qc_review"}[a.verdict]
    if asset["qc_tech"]["verdict"] == "REVIEW" and target == "qc_passed" and not a.flags_resolved:
        raise StateError(f"tech flags {asset['qc_tech']['flags']} must be addressed: pass --flags-resolved with a note")
    b.transition(a.k, target, ev, qc_review=ev)
    _out(asset["status"])


# ---------------- Stage 5 ----------------
def cmd_metadata(a, cfg):
    """Load metadata JSON ({k: {title, description, keywords, category}}) and validate."""
    b = _batch(cfg, a.n)
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    report = []
    for k, md in data.items():
        asset = b.asset(k)
        if asset["status"] not in ("qc_passed", "metadata_validated"):
            report.append({"k": k, "skipped": asset["status"]})
            continue
        md = {**md, "filename": asset["filename"], "type": asset["type"], "keywords": M.clean_keywords(md["keywords"])}
        errs, warns = M.validate(md, cfg)
        if errs:
            report.append({"k": k, "file": asset["filename"], "errors": errs, "warnings": warns})
            continue
        asset["metadata"] = md
        if asset["status"] == "qc_passed":
            b.transition(k, "metadata_validated", {"warnings": warns})
        else:
            b.save()
        report.append({"k": k, "file": asset["filename"], "ok": True, "warnings": warns})
    _out(report)
    return 2 if any("errors" in r for r in report) else 0


def cmd_embed(a, cfg):
    b = _batch(cfg, a.n)
    day = C.local_day(cfg, a.n)
    commits, out = [], []
    for asset in b.in_status("metadata_validated"):
        src = day / "_original" / asset["filename"]
        dst = day / asset["filename"]
        try:
            ev = M.embed(src, dst, asset["metadata"])
        except Exception as e:
            out.append({"file": asset["filename"], "error": str(e)})
            continue
        b.transition(asset["k"], "metadata_embedded", ev, final_sha256=ev["sha256"], final_bytes=ev["bytes"])
        commits.append({"local": str(dst), "device": C.device_path(cfg, C.day_dir(cfg, a.n), asset["filename"]),
                        "bytes": ev["bytes"]})
        out.append({"file": asset["filename"], "verified": True, "c2pa_kept": ev["c2pa_after"]})
    _out({"results": out, "commit": commits})


def cmd_csv(a, cfg):
    b = _batch(cfg, a.n)
    rows = [x["metadata"] for x in b.assets() if x.get("metadata") and x["status"] not in ("qc_reject", "failed", "skipped")
            and x["status"] != "metadata_validated"]
    mdir = C.local_day(cfg, a.n) / "Metadata"
    ad, ve = mdir / "adobe-metadata.csv", mdir / "vecteezy-metadata.csv"
    M.write_adobe_csv(ad, rows, cfg)
    M.write_vecteezy_csv(ve, rows, cfg)
    fns = [r["filename"] for r in rows]
    errs = M.validate_csv(ad, cfg["adobe"]["csv_columns"], fns) + M.validate_csv(ve, cfg["vecteezy"]["csv_columns"], [M.vz_filename(f, cfg) for f in fns])
    b.log("csv", rows=len(rows), errors=errs)
    _out({"rows": len(rows), "errors": errs, "commit": [
        {"local": str(ad), "device": C.device_path(cfg, C.day_dir(cfg, a.n), "Metadata", ad.name)},
        {"local": str(ve), "device": C.device_path(cfg, C.day_dir(cfg, a.n), "Metadata", ve.name)}]})
    return 2 if errs else 0


DT_AI_SUBCAT = 212  # Illustrations & Clipart > Generative AI (required by Dreamstime for AI content)
DT_FROM_ADOBE = {4: 127, 7: 127, 8: 112, 9: 158, 11: 146, 12: 138, 14: 25, 15: 202}
DT_COLUMNS = ["Filename", "Image Name", "Description", "Category 1", "Category 2", "Category 3",
              "keywords", "Free", "W-EL", "P-EL", "SR-EL", "SR-Price", "Editorial", "MR doc Ids", "Pr Docs"]


def cmd_dt_csv(a, cfg):
    """Dreamstime CSV: Category 1 is always Generative AI and the description says it is AI-made.

    --cats is an optional JSON file {"k": [cat2, cat3]} with Dreamstime subcategory ids; without it
    Category 2 comes from the Adobe category and Category 3 stays empty. Only assets that are
    queued or later (QC-passed, metadata embedded) are written. Files with people as the main
    subject need a model release on Dreamstime, so they are skipped unless --allow-people.
    """
    import csv
    b = _batch(cfg, a.n)
    extra = json.loads(Path(a.cats).read_text()) if a.cats else {}
    skip = set(int(x) for x in (a.skip or "").split(",") if x)
    rows, skipped = [], []
    for x in b.assets():
        md = x.get("metadata")
        if not md or x["status"] in ("qc_reject", "failed", "skipped", "prompt_generated", "metadata_validated"):
            continue
        if x["k"] in skip:
            skipped.append(x["filename"])
            continue
        cats = extra.get(str(x["k"])) or [DT_FROM_ADOBE.get(md.get("category"), 145)]
        cats = [c for c in cats if c and c != DT_AI_SUBCAT][:2]
        desc = md["description"].rstrip(".") + ". Image created with generative AI."
        rows.append([x["filename"], md["title"], desc, DT_AI_SUBCAT] + (cats + ["", ""])[:2] +
                    [",".join(md["keywords"]), 0, 0, 0, 0, 0, 0, "", ""])
    out = C.local_day(cfg, a.n) / "Metadata" / "dreamstime-metadata.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(DT_COLUMNS)
        w.writerows(rows)
    b.log("dt_csv", rows=len(rows), skipped=skipped)
    _out({"rows": len(rows), "skipped": skipped, "file": str(out),
          "device": C.device_path(cfg, C.day_dir(cfg, a.n), "Metadata", out.name)})
    return 0


def cmd_verify_device(a, cfg):
    """Read back the copies that now live on the PC (staged into --dir).

    The device bridge rewrites the C2PA (APP11) segment when it writes a file, so the
    bytes on the PC differ from the local final. Pixels and IPTC/XMP must be identical;
    if they are, the device copy's size/sha become the canonical final for queueing.
    """
    import hashlib
    from PIL import Image
    b = _batch(cfg, a.n)
    out = []
    pix = lambda p: hashlib.sha256(Image.open(p).tobytes()).hexdigest()
    for x in b.in_status("metadata_embedded"):
        dev = Path(a.dir) / x["filename"]
        loc = C.local_day(cfg, a.n) / x["filename"]
        if not dev.exists():
            out.append({"file": x["filename"], "error": "not staged"})
            continue
        rb = M.readback(dev)
        md = x["metadata"]
        probs = []
        if rb.get("XMP:Title") != md["title"]:
            probs.append("title")
        if rb.get("IPTC:Keywords") != md["keywords"]:
            probs.append("keywords")
        if pix(dev) != pix(loc):
            probs.append("pixels")
        if probs:
            out.append({"file": x["filename"], "error": "device copy differs: " + ",".join(probs)})
            continue
        x["final_bytes"], x["final_sha256"] = dev.stat().st_size, Q.sha256(dev)
        x["device_verified"] = {"bytes": x["final_bytes"], "sha256": x["final_sha256"], "c2pa_present": Q.has_c2pa(dev),
                                "note": "bridge rewrote C2PA segment; pixels+IPTC/XMP identical"}
        b.save()
        out.append({"file": x["filename"], "ok": True, "bytes": x["final_bytes"]})
    _out(out)
    return 2 if any("error" in r for r in out) else 0


# ---------------- Stage 6a ----------------
def cmd_enqueue(a, cfg):
    """Phase 1: list files to commit into _incoming (no state change).
    Phase 2 (--confirm with a device listing JSON): mark queued only when the device
    shows the exact byte size; then the agent writes READY.flag LAST."""
    b = _batch(cfg, a.n)
    ready = b.in_status("metadata_embedded")
    if not a.confirm:
        unverified = [x["filename"] for x in ready if not x.get("device_verified")]
        if unverified:
            _out({"error": "run verify-device first", "files": unverified})
            return 2
        _out({"commit": [{"local": str(C.local_day(cfg, a.n) / x["filename"]),
                          "device": C.device_path(cfg, "_UPLOAD_QUEUE", "_incoming", x["filename"]),
                          "bytes": x["final_bytes"]} for x in ready]})
        return 0
    listing = json.loads(Path(a.confirm).read_text(encoding="utf-8"))
    sizes = {e["name"]: e.get("size") for e in listing.get("entries", [])}
    done, bad = [], []
    for x in ready:
        if sizes.get(x["filename"]) == x["final_bytes"]:
            b.transition(x["k"], "queued", {"sha256": x["final_sha256"], "bytes": x["final_bytes"],
                                             "device_path": C.device_path(cfg, "_UPLOAD_QUEUE", "_incoming", x["filename"]),
                                             "queued_local_ts": a.local_ts})
            done.append(x["filename"])
        else:
            bad.append({"file": x["filename"], "expected": x["final_bytes"], "device": sizes.get(x["filename"])})
    flag = C.local_day(cfg, a.n) / "READY.flag"
    flag.write_text(U.ready_flag_text(b.data["batch_id"], done), encoding="utf-8")
    _out({"queued": done, "size_mismatch": bad,
          "ready_flag": None if bad or not done else {"local": str(flag), "device": C.device_path(cfg, "_UPLOAD_QUEUE", "_incoming", "READY.flag")}})
    return 2 if bad else 0


def cmd_requeue(a, cfg):
    """A queued file vanished without a completed upload (e.g. WinSCP killed mid-transfer)
    and the portal does not show it: put it back to metadata_embedded so `msp enqueue`
    queues it again. Needs the reason and the portal check as evidence."""
    b = _batch(cfg, a.n)
    for k in a.k:
        x = b.asset(k)
        if x["status"] != "queued":
            raise SystemExit(f"{x['filename']}: requeue only from queued (is {x['status']})")
        emb = next(h for h in reversed(x["history"]) if h["status"] == "metadata_embedded")["evidence"]
        b.transition(k, "metadata_embedded", {**emb, "verified": True, "requeue": True,
                                              "reason": a.reason, "portal_check": a.portal_check})
    _out(b.summary())


def cmd_reconcile(a, cfg):
    b = _batch(cfg, a.n)
    text = Path(a.log).read_text(encoding="utf-8", errors="replace")
    _out(U.reconcile(b, text))


# ---------------- Stage 6b ----------------
def cmd_mark(a, cfg):
    b = _batch(cfg, a.n)
    ev = json.loads(a.evidence) if a.evidence else {}
    for k in a.k:
        b.transition(k, a.status, ev)
    _out(b.summary())


APPROVAL_WORDS = {"ya", "yes", "submit", "ya submit", "kirim", "ok submit", "boleh", "boleh submit", "boleh submit aja",
                  "silakan submit", "oke submit"}


def is_explicit_yes(text: str) -> bool:
    """Exact-match gate for 'Submit this batch?'. Anything ambiguous ('nanti', 'jangan submit') is not a yes."""
    return text.strip().lower() in APPROVAL_WORDS


def cmd_approve(a, cfg):
    """Record Nathan's explicit 'Submit this batch?' answer for all fields_configured assets."""
    b = _batch(cfg, a.n)
    if not is_explicit_yes(a.text):
        raise StateError(f"approval text {a.text!r} is not an explicit yes; nothing recorded")
    ks = [x["k"] for x in b.in_status("fields_configured")]
    if not ks:
        raise StateError("no assets in fields_configured")
    b.record_approval("submit_batch", a.by, a.text, ks)
    for k in ks:
        b.transition(k, "submit_approved", {"approved_by": a.by, "approval_text": a.text})
    _out({"approved": ks})


# ---------------- scheduling (one run a day, 06:30 WIB) ----------------
PROCESS_STATUSES = {"downloaded", "upscale_pending", "qc_review", "qc_passed", "metadata_validated",
                    "metadata_embedded", "queued", "sftp_uploaded", "submit_approved"}
CHECKPOINT_QUIET_HOURS = 12
PROMPTS_FROM_HOUR = 6
STALE_BATCH_DAYS = 2


def due(states: list[dict], now_local, tz_offset_hours: int = 7, last_research=None) -> dict:
    """Decide what a scheduled run (daily 06:30 WIB) must do. Pure function of batch states and local time.

    Returns {"actions": [...], "skip_stale": [{batch, ks}], "silent": bool}.
    actions: ("process", batch) | ("check_flow", batch) | ("ask_submit", batch) | ("prompts",) | ("research",)
    last_research: aware datetime of the newest research brief, or None.
    """
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=tz_offset_hours))
    now = now_local if now_local.tzinfo else now_local.replace(tzinfo=tz)
    actions, stale = [], []
    for d in sorted(states, key=lambda d: d["day"]):
        st = [a["status"] for a in d["assets"].values()]
        bid = d["batch_id"]
        created = datetime.fromisoformat(d["created_at"]).astimezone(tz)
        if any(x in PROCESS_STATUSES for x in st):
            actions.append({"do": "process", "batch": bid})
        if "fields_configured" in st:
            asked = [e for e in d.get("run_log", []) if e.get("event") == "submit_checkpoint"]
            last = max((datetime.fromisoformat(e["at"]) for e in asked), default=None)
            if last is None or now - last.astimezone(tz) > timedelta(hours=CHECKPOINT_QUIET_HOURS):
                actions.append({"do": "ask_submit", "batch": bid})
        if "prompt_generated" in st:
            if now - created > timedelta(days=STALE_BATCH_DAYS):
                stale.append({"batch": bid, "ks": [a["k"] for a in d["assets"].values() if a["status"] == "prompt_generated"]})
            else:
                actions.append({"do": "check_flow", "batch": bid})
    newest = max(states, key=lambda d: d["day"]) if states else None
    newest_open = newest and any(a["status"] == "prompt_generated" for a in newest["assets"].values()) \
        and not any(s["batch"] == newest["batch_id"] for s in stale)
    created_today = newest and datetime.fromisoformat(newest["created_at"]).astimezone(tz).date() == now.date()
    if research_due(now, last_research):
        actions.insert(0, {"do": "research"})  # first, so tonight's prompts can use it
    if now.hour >= PROMPTS_FROM_HOUR and not created_today and not newest_open:
        actions.append({"do": "prompts"})
    return {"actions": actions, "skip_stale": stale, "silent": not actions and not stale}


# Per-batch stage order used by `msp day-status`. Each stage is "done", "pending" (the orchestrator can act now),
# or "waiting" (needs Nathan or the PC upload task). Terminal assets (rejected/skipped/failed) never block a stage.
STAGE_RULES = [
    ("generate", {"prompt_generated"}, "waiting"),                      # Nathan generates in Flow (check Flow first)
    ("download", {"image_generated"}, "pending"),
    ("qc", {"downloaded", "upscale_pending", "qc_review"}, "pending"),
    ("metadata", {"qc_passed", "metadata_validated"}, "pending"),
    ("embed_queue", {"metadata_embedded"}, "pending"),
    ("upload", {"queued"}, "waiting"),                                  # PC task uploads at 09:30, then reconcile
    ("prepare", {"sftp_uploaded"}, "pending"),
    ("submit", {"fields_configured", "submit_approved"}, "waiting"),    # Nathan submits manually
]


def batch_stages(d: dict) -> dict:
    """Stage checklist for one batch state: {"counts", "stages", "next"}; pure function of the asset statuses."""
    from collections import Counter
    counts = Counter(a["status"] for a in d["assets"].values())
    stages, nxt = {}, None
    for name, statuses, kind in STAGE_RULES:
        n = sum(counts.get(x, 0) for x in statuses)
        stages[name] = {"state": kind if n else "done", "assets": n}
        if n and nxt is None:
            nxt = name
    attention = counts.get("failed", 0)
    return {"batch": d["batch_id"], "counts": dict(counts), "stages": stages, "next": nxt, "failed": attention}


def day_status(states: list[dict], now_local, tz_offset_hours: int = 7, last_research=None) -> dict:
    """What is done and what is left for today: prompts, Flow generation, every later stage per open batch.

    This is what the dailyrun skill reads first, so one run resumes exactly where the previous one stopped
    (for example C-Day 190: prompts done and images generated -> download/QC/metadata come next).
    """
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=tz_offset_hours))
    now = now_local if now_local.tzinfo else now_local.replace(tzinfo=tz)
    plan = due(states, now, tz_offset_hours, last_research)
    batches = [batch_stages(d) for d in sorted(states, key=lambda d: d["day"])]
    open_batches = [b for b in batches if b["next"] or b["failed"]]
    newest = max(states, key=lambda d: d["day"]) if states else None
    created_today = bool(newest) and datetime.fromisoformat(newest["created_at"]).astimezone(tz).date() == now.date()
    if created_today:
        prompts = "done"
    elif now.hour < PROMPTS_FROM_HOUR:
        prompts = "not_yet"
    elif {"do": "prompts"} in plan["actions"]:
        prompts = "pending"
    else:
        prompts = "blocked_by_open_batch"       # newest batch is still waiting for Nathan to generate
    return {
        "now": now.isoformat(),
        "today": now.date().isoformat(),
        "research": "pending" if {"do": "research"} in plan["actions"] else "done",
        "prompts_today": prompts,
        "newest_batch": newest["batch_id"] if newest else None,
        "open_batches": open_batches,
        "actions": plan["actions"],
        "skip_stale": plan["skip_stale"],
        "silent": plan["silent"],
    }


RESEARCH_WEEKDAY = 0      # Monday
RESEARCH_FROM_HOUR = 6
RESEARCH_MAX_AGE_DAYS = 8


def research_due(now, last) -> bool:
    """Weekly research: Mondays from 06:00 if not done today; any day if the newest brief
    is older than 8 days (PC was off on Monday) or there is none at all."""
    from datetime import timedelta
    if last is None:
        return now.hour >= RESEARCH_FROM_HOUR
    last = last.astimezone(now.tzinfo)
    if now - last > timedelta(days=RESEARCH_MAX_AGE_DAYS):
        return True
    return now.weekday() == RESEARCH_WEEKDAY and now.hour >= RESEARCH_FROM_HOUR and last.date() < now.date()


def research_dir() -> Path:
    p = C.workspace() / "_research"
    p.mkdir(parents=True, exist_ok=True)
    return p


def latest_research():
    """(path, brief dict) of the newest RESEARCH_*.json in the workspace, or (None, None)."""
    files = sorted(research_dir().glob("RESEARCH_*.json"))
    if not files:
        return None, None
    return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))


def cmd_research_brief(a, cfg):
    """Print the newest research brief (used by the prompts stage)."""
    p, brief = latest_research()
    _out({"path": str(p) if p else None, "brief": brief})


def cmd_research_save(a, cfg):
    """Validate a research brief JSON from the market-researcher agent and store it."""
    from datetime import datetime
    brief = json.loads(Path(a.file).read_text(encoding="utf-8"))
    errs = []
    for key in ("generated_at", "period", "sources", "portfolio", "priorities", "avoid", "notes_for_prompts"):
        if key not in brief:
            errs.append(f"missing {key}")
    for s_ in brief.get("sources", []):
        if not s_.get("url") and not s_.get("where"):
            errs.append(f"source without url/where: {s_}")
    for pr in brief.get("priorities", []):
        if not pr.get("evidence"):
            errs.append(f"priority without evidence: {pr.get('niche')}")
    if errs:
        _out({"saved": False, "errors": errs})
        return 2
    stamp = datetime.fromisoformat(brief["generated_at"]).strftime("%Y-%m-%d")
    out = research_dir() / f"RESEARCH_{stamp}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    _out({"saved": True, "local": str(out), "device": C.device_path(cfg, "_research", out.name)})


def weekly_stats(states: list[dict], now, days: int = 7) -> dict:
    """Pipeline numbers for the weekly report: what was made, what failed before Adobe, why.

    Pure function of batch states. A batch counts when it was created within `days` of `now`.
    Adobe-side outcomes (accepted / not accepted / sales) are NOT in state; the
    market-researcher reads them from the portal.
    """
    from collections import Counter
    from datetime import datetime, timedelta
    since = now - timedelta(days=days)
    out, tot = [], Counter()
    for d in sorted(states, key=lambda d: d["day"]):
        created = datetime.fromisoformat(d["created_at"])
        if created.astimezone(now.tzinfo) < since:
            continue
        assets = list(d["assets"].values())
        cnt = Counter(a["status"] for a in assets)
        gen = sum(1 for a in assets if a["status"] not in ("prompt_generated", "skipped"))
        rejected = [a for a in assets if a["status"] == "qc_reject"]
        reasons = []
        for a in rejected:
            ev = a.get("qc_review") or a.get("qc_tech") or {}
            note = ev.get("note") or "; ".join(ev.get("errors", []) + ev.get("flags", [])) or "no reason recorded"
            reasons.append({"file": a["filename"], "type": a["type"], "concept": a["concept"], "reason": note[:160]})
        failed = []
        for a in assets:
            if a["status"] == "failed":
                last = a["history"][-1]["evidence"] if a.get("history") else {}
                failed.append({"file": a["filename"], "error": last.get("error"), "detail": str(last.get("detail", ""))[:160]})
        passed = gen - len(rejected)
        out.append({"batch": d["batch_id"], "created": d["created_at"], "assets": len(assets), "generated": gen,
                    "status_counts": dict(cnt), "qc_rejected": len(rejected),
                    "qc_reject_rate": round(len(rejected) / gen, 2) if gen else None,
                    "passed_qc": passed, "submitted": cnt.get("submitted", 0),
                    "reject_reasons": reasons, "failed": failed})
        tot.update({"generated": gen, "qc_rejected": len(rejected), "passed_qc": passed,
                    "submitted": cnt.get("submitted", 0), "failed": len(failed)})
    t = dict(tot)
    t["qc_reject_rate"] = round(t.get("qc_rejected", 0) / t["generated"], 2) if t.get("generated") else None
    return {"since": since.isoformat(), "days": days, "batches": out, "totals": t}


def cmd_weekly_stats(a, cfg):
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=7))
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(tz)
    states = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(C.local_state_dir().glob("C*.json"))
              if not p.name.endswith("-plan.json")]
    _out(weekly_stats(states, now if now.tzinfo else now.replace(tzinfo=tz), a.days))


def cmd_due(a, cfg):
    from datetime import datetime
    states = []
    for p in sorted(C.local_state_dir().glob("C*.json")):
        if p.name.endswith("-plan.json"):
            continue
        states.append(json.loads(p.read_text(encoding="utf-8")))
    now = datetime.fromisoformat(a.now) if a.now else datetime.now()
    p, brief = latest_research()
    last = datetime.fromisoformat(brief["generated_at"]) if brief else None
    _out(due(states, now, last_research=last))


def cmd_day_status(a, cfg):
    """Checklist of what is done / pending today per stage and batch (read-only)."""
    from datetime import datetime
    states = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(C.local_state_dir().glob("C*.json"))
              if not p.name.endswith("-plan.json")]
    now = datetime.fromisoformat(a.now) if a.now else datetime.now()
    p, brief = latest_research()
    last = datetime.fromisoformat(brief["generated_at"]) if brief else None
    _out(day_status(states, now, last_research=last))


def cmd_checkpoint(a, cfg):
    """Record that "Submit this batch?" was sent, so scheduled runs do not ask again for 12 h."""
    b = _batch(cfg, a.n)
    ks = [x["k"] for x in b.in_status("fields_configured")]
    b.log("submit_checkpoint", assets=ks)
    _out({"logged": ks})


# ---------------- component check ----------------
REQUIRED_AGENTS = ["visual-qc", "browser-operator", "market-researcher"]
REQUIRED_SKILLS = ["dailyrun"]      # the only skill; stage details are in dailyrun/reference/
REQUIRED_REFERENCES = ["prompts", "download", "qc", "metadata", "portal", "weekly"]


def _frontmatter_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    for line in text.split("---", 2)[1].splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


def cmd_doctor(a, cfg):
    """Verify the agent and skill files the orchestrator depends on exist and are well-formed.

    This only checks the repo files. Whether the session registered them as Agent types /
    skills must be checked by the orchestrator in its own context (see dailyrun step 3).
    """
    import shutil as _sh
    root = C.REPO / ".claude"
    agents = {n: (root / "agents" / f"{n}.md") for n in REQUIRED_AGENTS}
    skills = {n: (root / "skills" / n / "SKILL.md") for n in REQUIRED_SKILLS}
    report = {"agents": {}, "skills": {}, "exiftool": bool(_sh.which("exiftool"))}
    ok = report["exiftool"]
    for kind, items in (("agents", agents), ("skills", skills)):
        for n, p in items.items():
            name = _frontmatter_name(p)
            good = name == n
            report[kind][n] = {"path": str(p.relative_to(C.REPO)), "ok": good,
                               "error": None if good else ("missing" if not p.exists() else f"frontmatter name {name!r}")}
            ok = ok and good
    refs = {n: root / "skills" / "dailyrun" / "reference" / f"{n}.md" for n in REQUIRED_REFERENCES}
    report["references"] = {n: {"ok": p.exists()} for n, p in refs.items()}
    ok = ok and all(r["ok"] for r in report["references"].values())
    bo = (root / "agents" / "browser-operator.md")
    if bo.exists() and "no submit mode" not in bo.read_text(encoding="utf-8"):
        report["agents"]["browser-operator"].update(ok=False, error="must not contain a submit mode")
        ok = False
    report["ok"] = ok
    _out(report)
    return 0 if ok else 2


# ---------------- reporting ----------------
def cmd_status(a, cfg):
    b = _batch(cfg, a.n)
    rows = [{"k": x["k"], "file": x["filename"], "type": x["type"], "status": x["status"],
             "concept": x["concept"]} for x in b.assets()]
    pending = {
        "needs_nathan_generation": [r["file"] for r in rows if r["status"] == "prompt_generated"],
        "needs_review": [r["file"] for r in rows if r["status"] == "qc_review"],
        "upscale_pending": [r["file"] for r in rows if r["status"] == "upscale_pending"],
        "awaiting_submit_approval": [r["file"] for r in rows if r["status"] == "fields_configured"],
    }
    _out({"batch": b.data["batch_id"], "summary": b.summary(), "pending": pending, "assets": rows})


def cmd_qc_report(a, cfg):
    b = _batch(cfg, a.n)
    rep = {"batch": b.data["batch_id"], "summary": b.summary(), "assets": [
        {"file": x["filename"], "type": x["type"], "concept": x["concept"], "status": x["status"],
         "tech": (x.get("qc_tech") or {}).get("verdict"), "tech_errors": (x.get("qc_tech") or {}).get("errors"),
         "tech_flags": (x.get("qc_tech") or {}).get("flags"), "visual": (x.get("qc_review") or {}).get("verdict"),
         "note": (x.get("qc_review") or {}).get("note"), "title": (x.get("metadata") or {}).get("title")}
        for x in b.assets()]}
    p = C.local_day(cfg, a.n) / f"QC_{b.data['batch_id']}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    _out({"commit": {"local": str(p), "device": C.device_path(cfg, C.day_dir(cfg, a.n), p.name)}, **rep["summary"]})


def main(argv=None):
    cfg = C.load()
    ap = argparse.ArgumentParser(prog="msp")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args):
        p = sp.add_parser(name)
        p.set_defaults(fn=fn)
        for spec in args:
            flags, kw = spec
            p.add_argument(*flags, **kw)
        return p

    N = (["--n"], {"type": int, "required": True})
    K1 = (["--k"], {"type": int, "required": True})
    KS = (["--k"], {"type": int, "nargs": "*"})
    add("next-n", cmd_next_n, (["--device-names"], {"nargs": "*", "default": []}))
    add("validate-plan", cmd_validate_plan, (["plan"], {}))
    add("init", cmd_init, N, (["--plan"], {"required": True}), (["--allow-invalid"], {"action": "store_true"}))
    add("generated", cmd_generated, N, K1, (["--project"], {"required": True}), (["--tile"], {"default": ""}),
        (["--prompt-match"], {"choices": ["exact", "differs"], "required": True}), (["--by"], {"default": "nathan"}))
    add("regenerate", cmd_regenerate, N, K1, (["--reason"], {"default": "wrong aspect in Flow"}))
    add("ingest", cmd_ingest, N, K1, (["--src"], {"required": True}), (["--source-name"], {"default": None}))
    add("qc", cmd_qc, N, KS, (["--recheck"], {"action": "store_true"}))
    add("review", cmd_review, N, K1, (["--verdict"], {"choices": ["KIRIM", "TOLAK", "REVIEW"], "required": True}),
        (["--note"], {"required": True}), (["--checked"], {"nargs": "*"}), (["--flags-resolved"], {"action": "store_true"}))
    add("metadata", cmd_metadata, N, (["--file"], {"required": True}))
    add("embed", cmd_embed, N)
    add("csv", cmd_csv, N)
    add("dt-csv", cmd_dt_csv, N, (["--cats"], {"default": None}), (["--skip"], {"default": ""}))
    add("verify-device", cmd_verify_device, N, (["--dir"], {"required": True}))
    add("enqueue", cmd_enqueue, N, (["--confirm"], {"default": None}), (["--local-ts"], {"default": ""}))
    add("requeue", cmd_requeue, N, (["--k"], {"type": int, "nargs": "+", "required": True}),
        (["--reason"], {"required": True}), (["--portal-check"], {"required": True}))
    add("reconcile", cmd_reconcile, N, (["--log"], {"required": True}))
    add("mark", cmd_mark, N, (["--k"], {"type": int, "nargs": "+", "required": True}),
        (["--status"], {"required": True}), (["--evidence"], {"default": None}))
    add("approve", cmd_approve, N, (["--text"], {"required": True}), (["--by"], {"default": "nathan"}))
    add("doctor", cmd_doctor)
    add("due", cmd_due, (["--now"], {"default": None, "help": "local time ISO, e.g. 2026-10-27T19:17+07:00"}))
    add("day-status", cmd_day_status, (["--now"], {"default": None, "help": "local time ISO, e.g. 2026-11-04T06:30+07:00"}))
    add("checkpoint", cmd_checkpoint, N)
    add("weekly-stats", cmd_weekly_stats, (["--days"], {"type": int, "default": 7}), (["--now"], {"default": None}))
    add("research-brief", cmd_research_brief)
    add("research-save", cmd_research_save, (["--file"], {"required": True}))
    add("status", cmd_status, N)
    add("qc-report", cmd_qc_report, N)
    a = ap.parse_args(argv)
    try:
        return a.fn(a, cfg) or 0
    except StateError as e:
        _out({"error": str(e)})
        return 3


if __name__ == "__main__":
    sys.exit(main())
