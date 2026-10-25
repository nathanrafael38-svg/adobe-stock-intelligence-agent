import os
import subprocess
import tempfile

import pytest
from PIL import Image, IptcImagePlugin

from msp import iptc, load_config, metadata, qc, state, winscp_log

CFG = load_config()
D181 = os.environ.get("D181", "/mnt/user-data/uploads/2. Microstock/2. Setelah Edit/1. Gambar/1. Dari Claude")
real = pytest.mark.skipif(not os.path.isdir(D181), reason="Day 181 sample not staged")

KW = ["coffee", "cup", "line art", "continuous line", "steam", "minimalist", "drawing", "steaming", "hot drink", "mug"] + \
     [f"term{i}" for i in range(36)]
TITLE = "Continuous line drawing of a steaming coffee cup"


# ---------- state machine ----------
def plan(n=3):
    return [{"prompt": f"p{i}", "type": "photo", "aspect": "16:9"} for i in range(n)]


def test_state_forward_only_and_idempotent():
    s = state.new_batch("b", 1, plan())
    assert state.advance(s, 1, "image_generated", {"tile": "x"})
    assert not state.advance(s, 1, "image_generated", {"tile": "x"})  # retry is no-op
    with pytest.raises(state.StateError):
        state.advance(s, 1, "qc_passed", {"x": 1})  # skips downloaded
    with pytest.raises(state.StateError):
        state.advance(s, 2, "image_generated", {})  # no evidence


def test_state_failure_isolated():
    s = state.new_batch("b", 1, plan())
    state.advance(s, 1, "failed", {"error": "timeout"})
    state.advance(s, 2, "image_generated", {"tile": "y"})
    assert state.summary(s) == {"failed": 1, "image_generated": 1, "prompt_generated": 1}
    with pytest.raises(state.StateError):
        state.advance(s, 1, "image_generated", {"tile": "z"})


def test_state_save_load_roundtrip(tmp_path):
    s = state.new_batch("b", 1, plan())
    p = tmp_path / "s.json"
    state.save(s, str(p))
    assert state.load(str(p)) == s


# ---------- metadata ----------
def item(**kw):
    m = {"filename": "Day 181(1).jpg", "title": TITLE, "description": "A minimalist one line drawing of a hot coffee cup.",
         "keywords": list(KW), "category": 8, "type": "illustration"}
    m.update(kw)
    return m


def test_metadata_valid():
    r = metadata.validate(item(), CFG)
    assert r["ok"], r


@pytest.mark.parametrize("bad,needle", [
    ({"title": "x" * 65}, "chars >"),
    ({"title": "Coffee, cup"}, "contains ','"),
    ({"keywords": KW[:20]}, "keywords, need"),
    ({"keywords": KW + ["coffee"]}, "duplicate"),
    ({"keywords": KW[:-1] + ["generative ai"]}, "banned keyword"),
    ({"category": 99}, "invalid Adobe category"),
    ({"filename": "x" * 31 + ".jpg"}, "filename"),
])
def test_metadata_rejects(bad, needle):
    r = metadata.validate(item(**bad), CFG)
    assert not r["ok"] and any(needle in e for e in r["errors"]), r


def test_csv_columns():
    a = metadata.parse_csv(metadata.adobe_csv([item()], CFG))
    v = metadata.parse_csv(metadata.vecteezy_csv([item()], CFG))
    assert list(a[0]) == ["Filename", "Title", "Keywords", "Category", "Releases"]
    assert list(v[0]) == ["Filename", "Title", "Description", "Keywords"]
    assert a[0]["Keywords"].split(", ") == KW


@real
def test_existing_day181_metadata_against_rules():
    """Documents how the current routine's output fares against the rules."""
    rows = metadata.parse_csv(open(f"{D181}/Day 181/Metadata/adobe-metadata.csv", encoding="utf-8").read())
    results = {r["Filename"]: metadata.validate(
        {"filename": r["Filename"], "title": r["Title"], "description": r["Title"],
         "keywords": r["Keywords"].split(", "), "category": r["Category"]}, CFG) for r in rows}
    for fn, r in results.items():
        print(fn, "OK" if r["ok"] else r["errors"], r["warnings"])
    assert len(results) == 4


# ---------- IPTC / XMP ----------
@real
def test_embed_roundtrip_and_pixels_untouched(tmp_path):
    src = f"{D181}/Day 181/Day 181(1).jpg"
    before = qc.sha256(src)
    dst = str(tmp_path / "out.jpg")
    info = iptc.embed(src, dst, TITLE, "A minimalist one line drawing of a hot coffee cup.", KW)
    assert qc.sha256(src) == before, "source modified"
    assert iptc.verify(dst, TITLE, "A minimalist one line drawing of a hot coffee cup.", KW) == []
    assert iptc.image_data_hash(open(dst, "rb").read()) == info["src_image_hash"]
    # independent readers
    with Image.open(dst) as im:
        pil = IptcImagePlugin.getiptcinfo(im)
        assert pil[(2, 5)] == TITLE.encode()
        assert [k.decode() for k in pil[(2, 25)]] == KW
    im_title = subprocess.run(["identify", "-format", "%[IPTC:2:05]", dst], capture_output=True, text=True).stdout
    assert im_title == TITLE
    # re-embedding replaces instead of stacking
    dst2 = str(tmp_path / "out2.jpg")
    iptc.embed(dst, dst2, "Second title", "d", KW[:45])
    assert iptc.read(dst2)["iptc"][5] == ["Second title"]


def test_embed_refuses_truncation(tmp_path):
    p = tmp_path / "a.jpg"
    Image.new("RGB", (64, 64), "white").save(p)
    with pytest.raises(iptc.MetadataError):
        iptc.embed(str(p), str(tmp_path / "b.jpg"), "x" * 65, "d", KW)
    with pytest.raises(iptc.MetadataError):
        iptc.embed(str(p), str(p), "t", "d", KW)


@real
def test_existing_queue_file_iptc_readable():
    r = iptc.read(f"{D181}/_UPLOAD_QUEUE/Day 181(1).jpg")
    assert r["iptc"][5] == ["Continuous line drawing of a steaming coffee cup"]
    assert len(r["iptc"][25]) == 48


# ---------- technical QC ----------
def test_qc_detects_truncation_and_small(tmp_path):
    p = tmp_path / "s.jpg"
    Image.new("RGB", (1000, 1000), "white").save(p, quality=90)
    r = qc.check(str(p), "illustration", "1:1", CFG)
    assert r["verdict"] == "FAIL" and any("px <" in e for e in r["errors"])
    data = p.read_bytes()
    t = tmp_path / "t.jpg"
    t.write_bytes(data[: len(data) // 2])
    assert qc.check(str(t), "illustration", "1:1", CFG)["verdict"] == "FAIL"


@real
def test_qc_on_day181():
    types = {1: ("illustration", "1:1"), 2: ("illustration", "1:1"), 3: ("illustration", "1:1"), 4: ("illustration", "1:1"),
             5: ("photo", "16:9"), 6: ("photo", "16:9"), 7: ("photo", "16:9"), 8: ("photo", "16:9")}
    hashes = {}
    for k, (t, a) in types.items():
        r = qc.check(f"{D181}/Day 181/Day 181({k}).jpg", t, a, CFG)
        hashes[k] = r["measures"]["dhash"]
        print(k, t, r["verdict"], r["measures"], r["errors"], r["flags"])
        assert not r["errors"], r
    print("near-dups:", qc.near_duplicates({str(k): v for k, v in hashes.items()}, CFG["qc"]["near_dup_hamming_max"]))


# ---------- WinSCP log ----------
@real
def test_winscp_log_counts_duplicate_upload():
    runs = winscp_log.parse(open(f"{D181}/_logs/winscp.log", encoding="utf-8", errors="replace").read())
    assert len(runs) == 3
    assert [r["exit_code"] for r in runs] == [None, 1, 1]
    assert winscp_log.upload_counts(runs) == {"Day 181(1).jpg": 2}
