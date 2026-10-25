"""Simulated batch through every local stage, using Day 181 files as stand-in
downloads. Browser/SFTP/portal steps are represented by the evidence the
orchestrator would record."""
import json
import os
import subprocess
import sys

import pytest

from msp import iptc, load_config, plan, state

CFG = load_config()
D181 = os.environ.get("D181", "/mnt/user-data/uploads/2. Microstock/2. Setelah Edit/1. Gambar/1. Dari Claude")
pytestmark = pytest.mark.skipif(not os.path.isdir(D181), reason="Day 181 sample not staged")

ILL = ["kawaii gingerbread cookie sticker", "watercolor lemon slice", "line art coffee cup", "pumpkin autumn leaf",
       "cartoon cactus pot", "watercolor hot air balloon", "kawaii sushi roll", "snowflake ornament"]
PH = ["hands kneading bread dough", "antique brass compass map", "hands chopping fresh herbs", "wrapped gift ribbon",
      "piggy bank coins savings", "vintage camera macro", "laundry basket towels", "barista pouring latte",
      "potted houseplant watering", "hands counting banknotes", "cutting birthday cake", "knitting wool needles"]


def make_plan():
    items = [{"concept": c, "type": "illustration", "aspect": "1:1", "prompt": f"A {c}. {plan.ILLU_SUFFIX}"} for c in ILL]
    items += [{"concept": c, "type": "photo", "aspect": "16:9", "prompt": f"A {c}. {plan.PHOTO_SUFFIX}"} for c in PH]
    return items


def run(*args):
    r = subprocess.run([sys.executable, "-m", "msp.cli", *args], capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(__file__)))
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else r.stdout), r.stderr


def test_plan_validator_catches_problems():
    good = make_plan()
    assert plan.validate(good, CFG)["ok"], plan.validate(good, CFG)
    bad = make_plan()
    bad[1] = dict(bad[0])  # duplicate concept (what happened in Day 181)
    assert any("too similar" in e for e in plan.validate(bad, CFG)["errors"])
    bad = make_plan()
    bad[9]["prompt"] = f"A vintage typewriter on a desk. {plan.PHOTO_SUFFIX}"
    assert any("fake-text" in e for e in plan.validate(bad, CFG)["errors"])
    assert not plan.validate(make_plan()[:19], CFG)["ok"]


def test_full_batch(tmp_path):
    st, day_dir, q, md = str(tmp_path / "C182.json"), str(tmp_path / "Day 182"), str(tmp_path / "Q"), str(tmp_path / "Day 182/Metadata")
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(make_plan()))

    rc, o, _ = run("next-day", "--existing", "Day 181", "--state-dir", str(tmp_path))
    assert o == {"action": "new", "day": 182, "folder": "Day 182", "flow_project": "C-Day 182"}
    rc, o, _ = run("init", "--day", "182", "--plan", str(pf), "--state", st)
    assert o["action"] == "created"
    rc, o, _ = run("init", "--day", "182", "--plan", str(pf), "--state", st)
    assert o["action"] == "exists"  # idempotent

    # Stage 2: k=2 produced two tiles -> failed, others fine
    for k in range(1, 21):
        tiles = 2 if k == 2 else 1
        run("generated", "--state", st, "--k", str(k), "--evidence", json.dumps({"tile": f"t{k}", "tiles_for_prompt": tiles}))
    s = state.load(st)
    assert s["assets"]["2"]["status"] == "failed"

    # Interrupted run: crash after first ingest, then resume detects open batch
    src = {1: 1, 3: 4, 4: 2}  # illustrations from Day 181
    run("ingest", "--state", st, "--k", "1", "--file", f"{D181}/Day 181/Day 181(1).jpg", "--out-dir", day_dir)
    rc, o, _ = run("next-day", "--existing", "Day 181", "Day 182", "--state-dir", str(tmp_path))
    assert o["action"] == "resume" and o["day"] == 182
    # retry same k is a no-op; same file for another k is caught
    rc, o, _ = run("ingest", "--state", st, "--k", "1", "--file", f"{D181}/Day 181/Day 181(1).jpg", "--out-dir", day_dir)
    assert o["action"] == "skip"
    rc, o, _ = run("ingest", "--state", st, "--k", "3", "--file", f"{D181}/Day 181/Day 181(1).jpg", "--out-dir", day_dir)
    assert o["status"] == "failed"
    run("ingest", "--state", st, "--k", "4", "--file", f"{D181}/Day 181/Day 181(4).jpg", "--out-dir", day_dir)
    run("ingest", "--state", st, "--k", "9", "--file", f"{D181}/Day 181/Day 181(5).jpg", "--out-dir", day_dir)
    run("ingest", "--state", st, "--k", "10", "--file", f"{D181}/Day 181/Day 181(8).jpg", "--out-dir", day_dir)
    assert sorted(os.listdir(day_dir)) == ["C182_01.jpg", "C182_04.jpg", "C182_09.jpg", "C182_10.jpg"]

    rc, o, _ = run("qc-tech", "--state", st, "--day-dir", day_dir)
    assert set(o["tech"].values()) == {"PASS"}

    # review without listing what was inspected is refused
    rv = tmp_path / "rv.json"
    rv.write_text(json.dumps({"1": {"verdict": "KIRIM", "note": "ok"}}))
    rc, o, err = run("review", "--state", st, "--review", str(rv))
    assert rc != 0
    rv.write_text(json.dumps({
        "1": {"verdict": "KIRIM", "note": "clean", "checked": ["edges", "text areas"]},
        "4": {"verdict": "KIRIM", "note": "clean", "checked": ["edges", "face"]},
        "9": {"verdict": "KIRIM", "note": "clean", "checked": ["hand", "compass dial"]},
        "10": {"verdict": "BUANG", "note": "extra finger", "checked": ["hands"]}}))
    run("review", "--state", st, "--review", str(rv))

    kw = lambda base: base + [f"extra{i}" for i in range(45 - len(base))]
    meta = {
        "1": {"title": "Continuous line drawing of a steaming coffee cup", "description": "One line drawing of a hot coffee cup.",
              "keywords": kw(["coffee", "cup", "line", "drawing", "continuous", "steaming", "steam", "mug", "minimal", "art"]), "category": 8},
        "4": {"title": "Kawaii gingerbread cookie sticker with icing and bow tie", "description": "Cute gingerbread man sticker.",
              "keywords": kw(["gingerbread", "cookie", "kawaii", "sticker", "icing", "bow", "tie", "christmas", "cute", "holiday"]), "category": 8},
        "9": {"title": "Antique brass compass on an old paper map, warm light", "description": "Vintage compass on a map.",
              "keywords": kw(["compass", "antique", "brass", "map", "paper", "old", "warm", "light", "vintage", "travel"]), "category": 21},
    }
    mf = tmp_path / "meta.json"
    mf.write_text(json.dumps(meta))
    rc, o, _ = run("meta", "--state", st, "--meta", str(mf), "--day-dir", day_dir, "--queue-dir", q, "--meta-dir", md)
    assert o["problems"] == {"9": ["title contains ','"]}
    meta["9"]["title"] = "Antique brass compass on an old paper map in warm light"
    mf.write_text(json.dumps(meta))
    rc, o, _ = run("meta", "--state", st, "--meta", str(mf), "--day-dir", day_dir, "--queue-dir", q, "--meta-dir", md)
    assert sorted(o["embedded"]) == ["C182_01.jpg", "C182_04.jpg", "C182_09.jpg"] and not o["problems"]
    assert sorted(os.listdir(q)) == ["C182_01.jpg", "C182_04.jpg", "C182_09.jpg"]
    assert iptc.read(f"{q}/C182_09.jpg")["iptc"][5] == [meta["9"]["title"]]
    assert iptc.read(f"{day_dir}/C182_09.jpg")["iptc"] == {}  # master untouched
    vz = open(f"{md}/vecteezy-metadata.csv", encoding="utf-8").read().splitlines()
    assert vz[0] == '"Filename","Title","Description","Keywords"'
    assert all(len(l.split('","')[3].split(", ")) <= 30 for l in vz[1:])

    # SFTP: synthetic log with one success and one duplicate
    log = tmp_path / "winscp.log"
    log.write_text(
        ". 2026-10-26 09:30:00.000 Command-line: x\n"
        ". 2026-10-26 09:30:01.000 Copying \"F:\\Q\\C182_01.jpg\" to remote directory started.\n"
        ". 2026-10-26 09:30:02.000 Transfer done: 'F:\\Q\\C182_01.jpg' => '/C182_01.jpg' [1]\n"
        ". 2026-10-26 09:30:03.000 Copying \"F:\\Q\\C182_04.jpg\" to remote directory started.\n"
        ". 2026-10-26 09:30:05.000 Script: Exit code: 1\n"
        ". 2026-10-26 09:40:00.000 Command-line: x\n"
        ". 2026-10-26 09:40:02.000 Transfer done: 'F:\\Q\\C182_01.jpg' => '/C182_01.jpg' [1]\n"
        ". 2026-10-26 09:40:05.000 Script: Exit code: 0\n")
    rc, o, _ = run("sftp", "--state", st, "--log", str(log))
    assert o["uploaded_now"] == ["C182_01.jpg"] and o["duplicates"] == {"C182_01.jpg": 2}

    # portal: cannot submit before configured+approved
    rc, o, _ = run("portal", "--state", st, "--status", "submitted", "--evidence", '{"x":1}', "--all")
    assert o["moved"] == []
    run("portal", "--state", st, "--status", "portal_configured", "--evidence", '{"category":"set","ai_label":true}', "--all")
    run("portal", "--state", st, "--status", "submit_approved", "--evidence", '{"by":"nathan","reply":"submit C182"}', "--all")
    rc, o, _ = run("portal", "--state", st, "--status", "submitted", "--evidence", '{"portal_msg":"ok"}', "--all")
    assert o["moved"] == ["C182_01.jpg"]

    rc, o, _ = run("report", "--state", st)
    assert o["summary"] == {"submitted": 1, "metadata_embedded": 2, "qc_reject": 1, "failed": 2, "image_generated": 14}
