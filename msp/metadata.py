"""Metadata validation, IPTC/XMP embedding with read-back, and CSV export (Stage 5).

Embedding writes a NEW file; the source image is never modified.
Uses exiftool (must be on PATH).
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

from .qc import has_c2pa, sha256


def _norm_kw(k: str) -> str:
    return re.sub(r"\s+", " ", k.strip().lower())


def clean_keywords(keywords: list[str]) -> list[str]:
    seen, out = set(), []
    for k in keywords:
        n = _norm_kw(k)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def validate(md: dict, cfg: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one asset's metadata dict.

    md = {filename, type, title, description, keywords[list], category(int)}
    """
    a, v, g = cfg["adobe"], cfg["vecteezy"], cfg["metadata"]
    errors: list[str] = []
    warnings: list[str] = []
    title = md.get("title", "") or ""
    if not title:
        errors.append("title empty")
    if len(title) > a["title_max_chars"]:
        errors.append(f"title {len(title)} chars > {a['title_max_chars']} (Adobe CSV limit)")
    bad = [c for c in a["title_forbidden_chars"] if c in title]
    if bad:
        errors.append(f"title contains forbidden chars {bad}")
    if len(md.get("filename", "")) > a["filename_max_chars"]:
        errors.append("filename too long for Adobe CSV")
    desc = md.get("description", "") or ""
    if not desc:
        warnings.append("description empty (Vecteezy field)")
    kws = md.get("keywords") or []
    if kws != clean_keywords(kws):
        errors.append("keywords not normalised/deduplicated (run clean_keywords)")
    if not (a["keywords_min"] <= len(kws) <= a["keywords_max"]):
        errors.append(f"{len(kws)} keywords outside Adobe range {a['keywords_min']}-{a['keywords_max']}")
    if len(kws) < v["keywords_min"]:
        errors.append("fewer keywords than Vecteezy minimum")
    for k in kws:
        if len(k.encode("utf-8")) > g["keyword_max_bytes"]:
            errors.append(f"keyword too long for IPTC: {k!r}")
        if "," in k:
            errors.append(f"keyword contains comma: {k!r}")
    text = " ".join([title, desc, " ".join(kws)]).lower()
    for b in g["banned_terms"]:
        if re.search(rf"\b{re.escape(b)}\b", text):
            errors.append(f"banned term '{b}' in metadata")
    cat = str(md.get("category", ""))
    if cat not in a["categories"]:
        errors.append(f"category {cat!r} not in Adobe list 1-21")
    # Keyword relevance sanity: the first 10 should overlap the title words.
    tw = set(re.findall(r"[a-z]+", title.lower()))
    top = set(w for k in kws[:10] for w in k.split())
    if tw and not (tw & top):
        warnings.append("none of the first 10 keywords appear in the title (ordering/relevance)")
    return errors, warnings


def require_exiftool() -> str:
    exe = shutil.which("exiftool")
    if not exe:
        raise RuntimeError("exiftool not found on PATH (apt-get install libimage-exiftool-perl)")
    return exe


def embed(src: Path, dst: Path, md: dict) -> dict:
    """Write IPTC+XMP into a copy of src at dst, then read back and compare.

    Returns evidence {verified, sha256, bytes, readback, c2pa_before, c2pa_after}.
    Raises on any mismatch; dst is removed if verification fails.
    """
    exe = require_exiftool()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)
    kws = md["keywords"]
    args = [exe, "-q", "-overwrite_original", "-charset", "iptc=UTF8", "-codedcharacterset=utf8",
            "-IPTC:ObjectName=" + md["title"][:64],
            "-IPTC:Caption-Abstract=" + (md.get("description") or md["title"]),
            "-IPTC:Headline=" + md["title"][:256],
            "-XMP-dc:Title=" + md["title"],
            "-XMP-dc:Description=" + (md.get("description") or md["title"]),
            "-XMP-photoshop:Headline=" + md["title"],
            "-IPTC:Keywords=", "-XMP-dc:Subject="]
    args += [f"-IPTC:Keywords={k}" for k in kws]
    args += [f"-XMP-dc:Subject={k}" for k in kws]
    args.append(str(dst))
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        dst.unlink(missing_ok=True)
        raise RuntimeError(f"exiftool write failed: {r.stderr.strip()}")
    rb = readback(dst)
    problems = []
    if rb.get("XMP:Title") != md["title"]:
        problems.append("XMP title mismatch")
    if rb.get("IPTC:ObjectName") != md["title"][:64]:
        problems.append("IPTC ObjectName mismatch")
    if rb.get("IPTC:Keywords") != kws:
        problems.append("IPTC keywords mismatch")
    if rb.get("XMP:Subject") != kws:
        problems.append("XMP subject mismatch")
    # pixels must be unchanged: compare decoded image hashes
    from PIL import Image
    import hashlib
    def pix(p):
        with Image.open(p) as im:
            return hashlib.sha256(im.tobytes()).hexdigest()
    if pix(src) != pix(dst):
        problems.append("pixel data changed")
    c2pa_before, c2pa_after = has_c2pa(src), has_c2pa(dst)
    if problems:
        dst.unlink(missing_ok=True)
        raise RuntimeError("read-back verification failed: " + "; ".join(problems))
    return {"verified": True, "sha256": sha256(dst), "bytes": dst.stat().st_size,
            "src_sha256": sha256(src), "c2pa_before": c2pa_before, "c2pa_after": c2pa_after,
            "readback": {"title": rb.get("XMP:Title"), "keywords": len(rb.get("IPTC:Keywords") or [])}}


def readback(path: Path) -> dict:
    exe = require_exiftool()
    r = subprocess.run([exe, "-j", "-G0", "-charset", "iptc=UTF8", "-IPTC:all", "-XMP-dc:all", str(path)],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)[0]
    for key in ("IPTC:Keywords", "XMP:Subject"):
        if isinstance(d.get(key), str):
            d[key] = [d[key]]
    return d


def write_adobe_csv(path: Path, rows: list[dict], cfg: dict) -> None:
    cols = cfg["adobe"]["csv_columns"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(cols)
        for md in rows:
            w.writerow([md["filename"], md["title"], ", ".join(md["keywords"][: cfg["adobe"]["keywords_max"]]),
                        str(md["category"]), md.get("releases", "")])


def write_vecteezy_csv(path: Path, rows: list[dict], cfg: dict) -> None:
    cols = cfg["vecteezy"]["csv_columns"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(cols)
        for md in rows:
            w.writerow([md["filename"], md["title"], md.get("description", ""),
                        ", ".join(md["keywords"][: cfg["vecteezy"]["keywords_max"]])])


def validate_csv(path: Path, expected_cols: list[str], filenames: list[str]) -> list[str]:
    errs = []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != expected_cols:
        errs.append(f"{path.name}: header {rows[0] if rows else None} != {expected_cols}")
    got = [r[0] for r in rows[1:]]
    if got != filenames:
        errs.append(f"{path.name}: filenames {got} != {filenames}")
    for r in rows[1:]:
        if len(r) != len(expected_cols):
            errs.append(f"{path.name}: row {r[0]} has {len(r)} columns")
    return errs
