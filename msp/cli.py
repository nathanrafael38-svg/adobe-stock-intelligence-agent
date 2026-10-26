"""Orchestrator entry points. Each command reads/writes the batch state file
and prints a JSON result. Commands are idempotent: re-running after a crash
skips assets already past that stage.

The orchestrator moves files between the PC and the working directory with
the device bridge (stage/commit); this CLI only ever touches local paths.

  python -m msp.cli next-day --existing "Day 181" "Day 182" [--state-dir DIR]
  python -m msp.cli init     --day N --plan plan.json --state S [--history titles.txt]
  python -m msp.cli generated --state S --k K --evidence '{"tile":"...", "tiles_for_prompt":1}'
  python -m msp.cli ingest   --state S --k K --file DL.jpg --out-dir DAYDIR [--source-name X_2K_.jpg]
  python -m msp.cli qc-tech  --state S --day-dir DAYDIR [--history-hashes H.json]
  python -m msp.cli review   --state S --review review.json
  python -m msp.cli meta     --state S --meta meta.json --day-dir DAYDIR --queue-dir QDIR --meta-dir MDIR
  python -m msp.cli sftp     --state S --log winscp.log
  python -m msp.cli portal   --state S --status portal_configured|submit_approved|submitted --evidence '{...}' [--all]
  python -m msp.cli report   --state S
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

from . import iptc, load_config, metadata, plan, qc, state, winscp_log

CFG = load_config()


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fname(day: int, k: int) -> str:
    return CFG["naming"]["asset_filename"].format(n=day, k=k)


def cmd_next_day(a):
    nums = [int(m.group(1)) for d in a.existing if (m := re.fullmatch(r"Day (\d+)", d))]
    # Resume an unfinished batch before starting a new one.
    if a.state_dir and os.path.isdir(a.state_dir):
        for f in sorted(os.listdir(a.state_dir)):
            if re.fullmatch(r"C\d+\.json", f):
                s = state.load(os.path.join(a.state_dir, f))
                open_assets = [x for x in s["assets"].values()
                               if x["status"] not in state.SIDE and not state.at_least(x, "sftp_uploaded")]
                if open_assets:
                    return out({"action": "resume", "day": s["day"], "state_file": f, "open": len(open_assets)})
    n = max(nums + [CFG["naming"]["first_new_day"] - 1]) + 1
    return out({"action": "new", "day": n, "folder": CFG["naming"]["batch_folder"].format(n=n),
                "flow_project": CFG["naming"]["flow_project"].format(n=n)})


def cmd_init(a):
    if os.path.exists(a.state):
        return out({"action": "exists", "summary": state.summary(state.load(a.state))})
    items = json.load(open(a.plan, encoding="utf-8"))
    hist = open(a.history, encoding="utf-8").read().splitlines() if a.history else []
    v = plan.validate(items, CFG, hist, partial=a.partial)
    if not v["ok"]:
        out({"action": "rejected", **v})
        sys.exit(2)
    s = state.new_batch(f"C{a.day}", a.day, items)
    for k, it in zip(s["assets"].values(), items):
        k["concept"] = it["concept"]
        k["filename"] = fname(a.day, k["k"])
    state.save(s, a.state)
    out({"action": "created", "warnings": v["warnings"], "assets": len(items)})


def cmd_generated(a):
    s = state.load(a.state)
    ev = json.loads(a.evidence)
    if ev.get("tiles_for_prompt") != CFG["flow"]["outputs_per_prompt"]:
        state.advance(s, a.k, "failed", {"error": f"expected {CFG['flow']['outputs_per_prompt']} output, got {ev.get('tiles_for_prompt')}", **ev})
    else:
        state.advance(s, a.k, "image_generated", ev)
    state.save(s, a.state)
    out({"k": a.k, "status": s["assets"][str(a.k)]["status"]})


def cmd_ingest(a):
    s = state.load(a.state)
    asset = s["assets"][str(a.k)]
    if state.at_least(asset, "downloaded"):
        return out({"k": a.k, "action": "skip", "status": asset["status"]})
    digest = qc.sha256(a.file)
    for other in s["assets"].values():  # same file claimed twice = wrong mapping
        if other.get("sha256") == digest and other["k"] != asset["k"]:
            state.advance(s, a.k, "failed", {"error": f"same file already ingested as k={other['k']}"})
            state.save(s, a.state)
            return out({"k": a.k, "status": "failed"})
    errs = qc.integrity(a.file)
    if errs:
        state.advance(s, a.k, "failed", {"error": "; ".join(errs), "source": a.source_name or a.file})
        state.save(s, a.state)
        return out({"k": a.k, "status": "failed", "errors": errs})
    os.makedirs(a.out_dir, exist_ok=True)
    dst = os.path.join(a.out_dir, asset["filename"])
    if os.path.exists(dst) and qc.sha256(dst) != digest:
        raise SystemExit(f"collision: {dst} exists with different content")
    shutil.copyfile(a.file, dst)
    asset["sha256"] = digest
    state.advance(s, a.k, "downloaded", {"sha256": digest, "source": a.source_name or os.path.basename(a.file),
                                          "saved_as": asset["filename"]})
    state.save(s, a.state)
    out({"k": a.k, "status": "downloaded", "file": asset["filename"]})


def cmd_qc_tech(a):
    s = state.load(a.state)
    hist = json.load(open(a.history_hashes)) if a.history_hashes else {}
    res, hashes = {}, {}
    for asset in s["assets"].values():
        if asset["status"] != "downloaded":
            continue
        r = qc.check(os.path.join(a.day_dir, asset["filename"]), asset["type"], asset["aspect"], CFG)
        asset["qc_tech"] = r
        res[asset["k"]] = r["verdict"]
        if "dhash" in r["measures"]:
            hashes[asset["filename"]] = r["measures"]["dhash"]
        if r["verdict"] == "FAIL":
            state.advance(s, asset["k"], "qc_reject", {"stage": "tech", "errors": r["errors"]})
    dups = qc.near_duplicates(hashes, CFG["qc"]["near_dup_hamming_max"], hist)
    for x, y, d in dups:
        for asset in s["assets"].values():
            if asset["filename"] == x and "qc_tech" in asset:
                asset["qc_tech"]["flags"].append(f"near-duplicate of {y} (dHash {d})")
    state.save(s, a.state)
    out({"tech": res, "near_duplicates": dups,
         "for_visual_review": [x["filename"] for x in s["assets"].values() if x["status"] == "downloaded"]})


def cmd_review(a):
    """review.json: {"<k>": {"verdict": "KIRIM|TAHAN|BUANG", "note": "...", "checked": [...]}}"""
    s = state.load(a.state)
    rv = json.load(open(a.review, encoding="utf-8"))
    for k, r in rv.items():
        asset = s["assets"][str(k)]
        if asset["status"] != "downloaded":
            continue
        if not r.get("checked"):
            raise SystemExit(f"k={k}: review lacks the list of regions checked")
        st = {"KIRIM": "qc_passed", "TAHAN": "qc_hold", "BUANG": "qc_reject"}[r["verdict"]]
        asset["qc_review"] = r
        state.advance(s, k, st, {"stage": "visual", **r})
    state.save(s, a.state)
    out(state.summary(s))


def cmd_meta(a):
    s = state.load(a.state)
    meta = json.load(open(a.meta, encoding="utf-8"))
    os.makedirs(a.queue_dir, exist_ok=True)
    os.makedirs(a.meta_dir, exist_ok=True)
    ready, problems = [], {}
    for asset in s["assets"].values():
        if not (asset["status"] == "qc_passed" or state.at_least(asset, "metadata_validated")):
            continue
        m = meta.get(str(asset["k"]))
        if m is None:
            problems[asset["k"]] = ["no metadata supplied"]
            continue
        item = {"filename": asset["filename"], "type": asset["type"], **m}
        v = metadata.validate(item, CFG)
        if not v["ok"]:
            problems[asset["k"]] = v["errors"]
            continue
        item["keywords"] = v["keywords"]
        if asset["status"] == "qc_passed":
            state.advance(s, asset["k"], "metadata_validated", {"warnings": v["warnings"]})
        asset["metadata"] = item
        if asset["status"] == "metadata_validated":
            dst = os.path.join(a.queue_dir, asset["filename"])
            info = iptc.embed(os.path.join(a.day_dir, asset["filename"]), dst, item["title"], item["description"], item["keywords"])
            errs = iptc.verify(dst, item["title"], item["description"], item["keywords"])
            if errs:
                problems[asset["k"]] = errs
                os.remove(dst)
                continue
            state.advance(s, asset["k"], "metadata_embedded", {"verified": True, "queue_file": asset["filename"], **info})
        ready.append(item)
    with open(os.path.join(a.meta_dir, "adobe-metadata.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(metadata.adobe_csv(ready, CFG))
    with open(os.path.join(a.meta_dir, "vecteezy-metadata.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(metadata.vecteezy_csv(ready, CFG))
    state.save(s, a.state)
    out({"embedded": [i["filename"] for i in ready], "problems": problems})


def cmd_sftp(a):
    s = state.load(a.state)
    runs = winscp_log.parse(open(a.log, encoding="utf-8", errors="replace").read())
    counts = winscp_log.upload_counts(runs)
    done = []
    for asset in s["assets"].values():
        c = counts.get(asset["filename"], 0)
        asset["sftp_upload_count"] = c
        if c and asset["status"] == "metadata_embedded":
            state.advance(s, asset["k"], "sftp_uploaded", {"winscp_log_uploads": c})
            done.append(asset["filename"])
    state.save(s, a.state)
    out({"uploaded_now": done, "duplicates": {f: c for f, c in counts.items() if c > 1},
         "last_exit_code": runs[-1]["exit_code"] if runs else None})


def cmd_portal(a):
    s = state.load(a.state)
    ev = json.loads(a.evidence)
    prev = state.ORDER[state.RANK[a.status] - 1]
    moved = []
    for asset in s["assets"].values():
        if asset["status"] == prev and (a.all or asset["filename"] in ev.get("files", [])):
            state.advance(s, asset["k"], a.status, ev)
            moved.append(asset["filename"])
    state.save(s, a.state)
    out({"status": a.status, "moved": moved})


def cmd_report(a):
    s = state.load(a.state)
    rows = []
    for x in s["assets"].values():
        last = x["history"][-1]
        rows.append({"file": x["filename"], "type": x["type"], "concept": x.get("concept"), "status": x["status"],
                     "title": x.get("metadata", {}).get("title"), "note": last["evidence"].get("note") or last["evidence"].get("error")})
    out({"batch": s["batch_id"], "summary": state.summary(s), "assets": rows})


def main(argv=None):
    p = argparse.ArgumentParser(prog="msp")
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("next-day"); c.add_argument("--existing", nargs="*", default=[]); c.add_argument("--state-dir")
    c = sp.add_parser("init"); c.add_argument("--day", type=int, required=True); c.add_argument("--plan", required=True); c.add_argument("--state", required=True); c.add_argument("--history"); c.add_argument("--partial", action="store_true", help="test batch: skip composition count")
    c = sp.add_parser("generated"); c.add_argument("--state", required=True); c.add_argument("--k", type=int, required=True); c.add_argument("--evidence", required=True)
    c = sp.add_parser("ingest"); c.add_argument("--state", required=True); c.add_argument("--k", type=int, required=True); c.add_argument("--file", required=True); c.add_argument("--out-dir", required=True); c.add_argument("--source-name")
    c = sp.add_parser("qc-tech"); c.add_argument("--state", required=True); c.add_argument("--day-dir", required=True); c.add_argument("--history-hashes")
    c = sp.add_parser("review"); c.add_argument("--state", required=True); c.add_argument("--review", required=True)
    c = sp.add_parser("meta"); c.add_argument("--state", required=True); c.add_argument("--meta", required=True); c.add_argument("--day-dir", required=True); c.add_argument("--queue-dir", required=True); c.add_argument("--meta-dir", required=True)
    c = sp.add_parser("sftp"); c.add_argument("--state", required=True); c.add_argument("--log", required=True)
    c = sp.add_parser("portal"); c.add_argument("--state", required=True); c.add_argument("--status", required=True, choices=["portal_configured", "submit_approved", "submitted"]); c.add_argument("--evidence", required=True); c.add_argument("--all", action="store_true")
    c = sp.add_parser("report"); c.add_argument("--state", required=True)
    a = p.parse_args(argv)
    globals()["cmd_" + a.cmd.replace("-", "_")](a)


if __name__ == "__main__":
    main()
