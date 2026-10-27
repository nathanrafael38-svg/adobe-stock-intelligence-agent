import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from msp import config as C, metadata as M, plan as P, qc as Q, uploadq as U
from msp.state import Batch, StateError

CFG = C.load()


def _img(path: Path, w: int, h: int, sharp=True, white_border=False):
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, (h, w, 3), dtype=np.uint8) if sharp else np.full((h, w, 3), 128, np.uint8)
    if white_border:
        a[:] = 255
        a[h // 4:3 * h // 4, w // 4:3 * w // 4] = rng.integers(0, 255, (h // 2 - (h // 2) % 1, w // 2, 3), dtype=np.uint8)[: 3 * h // 4 - h // 4, : 3 * w // 4 - w // 4]
    Image.fromarray(a).save(path, "JPEG", quality=92)
    return path


def _plan(n_ill=8, n_photo=12):
    items = []
    subjects = ["pomegranate", "lemon", "fern", "teapot", "owl", "cactus", "anchor", "violin", "bicycle", "lantern",
                "compass", "kettle", "sweater", "candle", "seashell", "feather", "pinecone", "umbrella", "hourglass", "globe"]
    for i in range(n_ill):
        s = subjects[i]
        items.append({"concept": f"watercolor {s}", "type": "illustration", "aspect": "1:1",
                      "prompt": f"Watercolor illustration of a {s}. Clean white background, no text, no letters, no logos, no watermark."})
    for i in range(n_photo):
        s = subjects[n_ill + i]
        items.append({"concept": f"{s} on wooden table", "type": "photo", "aspect": "16:9",
                      "prompt": f"A {s} on a wooden table. Photorealistic, sharp focus, no text, no logos, no watermark."})
    return items


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("MSP_WORKSPACE", str(tmp_path))
    return tmp_path


# ---------------- plan ----------------
def test_plan_valid():
    assert P.validate(_plan(), CFG, []) == []


def test_plan_composition_and_dupes():
    p = _plan()
    p[1]["concept"] = p[0]["concept"]
    errs = P.validate(p[:-1], CFG, [("C100", "watercolor fern")])
    joined = " ".join(errs)
    assert "composition" in joined and "near-duplicate of #1" in joined and "C100" in joined


def test_plan_hands_clause_on_object_flagged():
    p = _plan()
    p[10]["prompt"] += " anatomically correct hands with five fingers"
    assert any("hands clause" in e for e in P.validate(p, CFG, []))


# ---------------- state ----------------
def test_state_transitions_and_evidence(ws):
    b = Batch.create(ws / "C1.json", "C1", 1, _plan()[:1], ["C1_01.jpg"])
    with pytest.raises(StateError):
        b.transition(1, "downloaded", {"sha256": "x", "source": "s", "saved_as": "a"})  # skips image_generated
    with pytest.raises(StateError):
        b.transition(1, "image_generated", {})  # missing evidence
    b.transition(1, "image_generated", {"project": "C-Day 1", "prompt_match": "exact"})
    with pytest.raises(StateError):
        Batch.create(ws / "C1.json", "C1", 1, _plan()[:1], ["C1_01.jpg"])  # no overwrite
    assert Batch.load(ws / "C1.json").asset(1)["status"] == "image_generated"


def test_metadata_embedded_requires_verified(ws):
    b = Batch.create(ws / "C2.json", "C2", 2, _plan()[:1], ["C2_01.jpg"])
    for s, ev in [("image_generated", {"project": "p", "prompt_match": "exact"}),
                  ("downloaded", {"sha256": "x", "source": "s", "saved_as": "a"}),
                  ("qc_passed", {"stage": "visual"}), ("metadata_validated", {})]:
        b.transition(1, s, ev)
    with pytest.raises(StateError):
        b.transition(1, "metadata_embedded", {"verified": False, "sha256": "x", "bytes": 1})


# ---------------- qc ----------------
def test_qc_aspect_mismatch_is_not_upscale_eligible(tmp_path):
    r = Q.tech_qc(_img(tmp_path / "a.jpg", 2048, 2048), "photo", "16:9", CFG)
    assert r["verdict"] == "FAIL" and any(e.startswith("aspect_mismatch") for e in r["errors"])
    assert not r["upscale_eligible"]


def test_qc_small_image_is_upscale_eligible(tmp_path):
    r = Q.tech_qc(_img(tmp_path / "b.jpg", 1600, 900), "photo", "16:9", CFG)
    assert r["errors"] == ["below_min_pixels"] and r["upscale_eligible"]


def test_qc_pass_and_near_duplicate(tmp_path):
    p = _img(tmp_path / "c.jpg", 2752, 1536)
    r = Q.tech_qc(p, "photo", "16:9", CFG)
    assert r["verdict"] == "PASS", r
    r2 = Q.tech_qc(p, "photo", "16:9", CFG, [("C9_01.jpg", r["measures"]["dhash"])])
    assert r2["verdict"] == "REVIEW" and r2["flags"][0].startswith("near_duplicate")


def test_qc_corrupt(tmp_path):
    p = _img(tmp_path / "d.jpg", 2048, 2048)
    p.write_bytes(p.read_bytes()[:5000])
    assert Q.tech_qc(p, "photo", "1:1", CFG)["errors"][0].startswith("corrupt")


# ---------------- metadata ----------------
GOOD_MD = {"filename": "C1_01.jpg", "type": "photo", "title": "Pomegranate half with red seeds watercolor illustration",
           "description": "Watercolor pomegranate cut in half on white.", "category": 7,
           "keywords": M.clean_keywords(["pomegranate", "watercolor", "seeds", "half", "red", "fruit", "food", "fresh",
                                         "ripe", "healthy", "juicy", "botanical", "pink", "organic", "natural", "vegan"])}


def test_metadata_validate_ok():
    errs, _ = M.validate(GOOD_MD, CFG)
    assert errs == []


def test_metadata_validate_catches_limits():
    md = {**GOOD_MD, "title": "x" * 71 + ", y", "category": 99, "keywords": GOOD_MD["keywords"] + ["ai generated"]}
    errs = " ".join(M.validate(md, CFG)[0])
    assert "chars" in errs and "forbidden" in errs and "category" in errs and "banned" in errs


@pytest.mark.skipif(not __import__("shutil").which("exiftool"), reason="exiftool missing")
def test_embed_readback_and_pixels(tmp_path):
    src = _img(tmp_path / "src.jpg", 2048, 2048)
    before = Q.sha256(src)
    ev = M.embed(src, tmp_path / "out" / "C1_01.jpg", GOOD_MD)
    assert ev["verified"] and Q.sha256(src) == before  # source untouched
    rb = M.readback(tmp_path / "out" / "C1_01.jpg")
    assert rb["IPTC:Keywords"] == GOOD_MD["keywords"] and rb["XMP:Title"] == GOOD_MD["title"]


def test_csv_roundtrip(tmp_path):
    M.write_adobe_csv(tmp_path / "a.csv", [GOOD_MD], CFG)
    M.write_vecteezy_csv(tmp_path / "v.csv", [GOOD_MD], CFG)
    assert M.validate_csv(tmp_path / "a.csv", CFG["adobe"]["csv_columns"], ["C1_01.jpg"]) == []
    assert M.validate_csv(tmp_path / "v.csv", CFG["vecteezy"]["csv_columns"], ["C1_01.jpg"]) == []


# ---------------- upload reconcile ----------------
LOG = ("> 2026-10-26 15:11:54.100 Script: put -delete\n"
       ". 2026-10-26 15:11:57.274 Transfer done: 'F:\\x\\_UPLOAD_QUEUE\\C1_01.jpg' => '/C1_01.jpg' [2465744]\n")


def _queued(ws, nbytes):
    b = Batch.create(ws / "C1.json", "C1", 1, _plan()[:1], ["C1_01.jpg"])
    for s, ev in [("image_generated", {"project": "p", "prompt_match": "exact"}),
                  ("downloaded", {"sha256": "x", "source": "s", "saved_as": "a"}),
                  ("qc_passed", {"stage": "visual"}), ("metadata_validated", {}),
                  ("metadata_embedded", {"verified": True, "sha256": "y", "bytes": nbytes}),
                  ("queued", {"sha256": "y", "bytes": nbytes, "device_path": "q", "queued_local_ts": "2026-10-26 15:00:00"})]:
        b.transition(1, s, ev)
    return b


def test_reconcile_marks_uploaded(ws):
    b = _queued(ws, 2465744)
    assert U.reconcile(b, LOG)[0]["result"] == "UPLOADED"
    assert b.asset(1)["status"] == "sftp_uploaded" and b.asset(1)["sftp_upload_count"] == 1
    assert U.reconcile(b, LOG) == []  # idempotent


def test_reconcile_rejects_byte_mismatch(ws):
    b = _queued(ws, 2473363)  # the real C182 discrepancy
    assert U.reconcile(b, LOG)[0]["result"] == "BYTES_MISMATCH"
    assert b.asset(1)["status"] == "queued"


def test_reconcile_ignores_transfers_before_queue(ws):
    b = _queued(ws, 2465744)
    old = LOG.replace("2026-10-26 15:11:57", "2026-10-25 15:11:57")
    assert U.reconcile(b, old) == []


def test_similarity_subject_vs_setting():
    assert P.is_duplicate("watercolor pomegranate slice with seeds", "watercolor pomegranate cut in half")
    assert not P.is_duplicate("bicycle on wooden table", "lantern on wooden table")
    assert not P.is_duplicate("hands kneading bread dough", "hands chopping fresh parsley")
    assert P.is_duplicate("stack of folded wool sweaters", "folded wool sweater pile")


def test_doctor_components_present(capsys):
    from msp import cli
    assert cli.main(["doctor"]) in (0, 2)
    out = json.loads(capsys.readouterr().out)
    for n in cli.REQUIRED_AGENTS:
        assert out["agents"][n]["ok"], out["agents"][n]
    for n in cli.REQUIRED_SKILLS:
        assert out["skills"][n]["ok"], out["skills"][n]


def _st(bid, day, created, statuses, log=None):
    return {"batch_id": bid, "day": day, "created_at": created, "run_log": log or [],
            "assets": {str(i): {"k": i, "status": s} for i, s in enumerate(statuses, 1)}}


def test_due_silent_when_nothing_to_do():
    from datetime import datetime
    from msp.cli import due
    st = [_st("C183", 183, "2026-10-26T11:00:00+00:00", ["submitted", "qc_reject"])]
    r = due(st, datetime.fromisoformat("2026-10-27T10:17+07:00"),
            last_research=datetime.fromisoformat("2026-10-26T09:00+07:00"))
    assert r["silent"] and r["actions"] == []


def test_due_prompts_only_in_evening_once_per_day():
    from datetime import datetime
    from msp.cli import due
    st = [_st("C183", 183, "2026-10-26T11:00:00+00:00", ["submitted"])]
    assert {"do": "prompts"} in due(st, datetime.fromisoformat("2026-10-27T19:17+07:00"))["actions"]
    assert {"do": "prompts"} not in due(st, datetime.fromisoformat("2026-10-27T10:17+07:00"))["actions"]
    st.append(_st("C184", 184, "2026-10-27T12:13:00+00:00", ["prompt_generated"] * 20))
    r = due(st, datetime.fromisoformat("2026-10-27T21:17+07:00"))
    assert {"do": "prompts"} not in r["actions"] and {"do": "check_flow", "batch": "C184"} in r["actions"]


def test_due_checkpoint_quiet_period_and_process():
    from datetime import datetime
    from msp.cli import due
    log = [{"event": "submit_checkpoint", "at": "2026-10-27T01:00:00+00:00"}]
    st = [_st("C184", 184, "2026-10-26T13:13:00+00:00", ["fields_configured", "queued"], log)]
    r = due(st, datetime.fromisoformat("2026-10-27T10:17+07:00"))
    assert {"do": "process", "batch": "C184"} in r["actions"]
    assert {"do": "ask_submit", "batch": "C184"} not in r["actions"]
    r = due(st, datetime.fromisoformat("2026-10-27T22:17+07:00"))
    assert {"do": "ask_submit", "batch": "C184"} in r["actions"]


def test_due_stale_batch_skipped_and_new_prompts():
    from datetime import datetime
    from msp.cli import due
    st = [_st("C184", 184, "2026-10-24T13:13:00+00:00", ["prompt_generated"] * 3)]
    r = due(st, datetime.fromisoformat("2026-10-27T19:17+07:00"))
    assert r["skip_stale"] == [{"batch": "C184", "ks": [1, 2, 3]}] and {"do": "prompts"} in r["actions"]


def test_prompt_xlsx(tmp_path):
    from openpyxl import load_workbook
    plan = _plan()
    fns = [f"C9_{k:02d}.jpg" for k in range(1, 21)]
    P.prompt_xlsx(tmp_path / "p.xlsx", "C9", "C-Day 9", plan, fns)
    ws = load_workbook(tmp_path / "p.xlsx").active
    prompts = [ws.cell(row=r, column=6).value for r in range(5, ws.max_row + 1) if ws.cell(row=r, column=2).value]
    assert len(prompts) == 20 and set(prompts) == {p["prompt"] for p in plan}
    assert ws.cell(row=4, column=6).value == "Prompt"
    assert ws.cell(row=5, column=1).value.startswith("RATIO 1:1")  # plan order, not alphabetical


def test_research_due_rules():
    from datetime import datetime
    from msp.cli import research_due
    mon = datetime.fromisoformat("2026-11-02T08:17+07:00")   # Monday
    assert research_due(mon, datetime.fromisoformat("2026-10-26T09:00+07:00"))
    assert not research_due(mon, datetime.fromisoformat("2026-11-02T08:20+07:00"))  # done today
    assert not research_due(datetime.fromisoformat("2026-11-02T07:17+07:00"), datetime.fromisoformat("2026-10-26T09:00+07:00"))
    assert not research_due(datetime.fromisoformat("2026-10-29T10:17+07:00"), datetime.fromisoformat("2026-10-26T09:00+07:00"))
    assert research_due(datetime.fromisoformat("2026-11-04T10:17+07:00"), datetime.fromisoformat("2026-10-26T09:00+07:00"))  # >8 days
    assert research_due(datetime.fromisoformat("2026-10-27T10:17+07:00"), None)


def test_research_save_requires_evidence(ws, tmp_path):
    from msp import cli
    bad = {"generated_at": "2026-11-02T09:00+07:00", "period": "w45", "sources": [{"where": "dashboard"}],
           "portfolio": {}, "priorities": [{"niche": "christmas"}], "avoid": [], "notes_for_prompts": []}
    f = tmp_path / "b.json"; f.write_text(json.dumps(bad))
    assert cli.main(["research-save", "--file", str(f)]) == 2
    bad["priorities"][0]["evidence"] = "Insights: top downloads in Food"
    f.write_text(json.dumps(bad))
    assert cli.main(["research-save", "--file", str(f)]) == 0
    p, brief = cli.latest_research()
    assert p.name == "RESEARCH_2026-11-02.json" and brief["period"] == "w45"
