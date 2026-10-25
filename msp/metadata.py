"""Validate metadata against documented platform rules and export CSVs.
Generation of the words themselves is the metadata-writer agent's job;
this module only decides whether what it wrote is acceptable."""
from __future__ import annotations

import csv
import io
import re

STOP = {"a", "an", "the", "of", "on", "in", "with", "and", "for", "to", "by", "at", "from", "over", "under", "into", "its"}


def normalize_keywords(kws: list[str]) -> list[str]:
    seen, out = set(), []
    for k in kws:
        k = re.sub(r"\s+", " ", k.strip().lower())
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def validate(m: dict, cfg: dict) -> dict:
    """m = {filename, title, description, keywords[list], category, type}."""
    a, v = cfg["metadata"]["adobe"], cfg["metadata"]["vecteezy"]
    banned = set(cfg["metadata"]["banned_terms"])
    errs, warns = [], []
    t = m.get("title", "").strip()
    if not t:
        errs.append("empty title")
    if len(t) > a["title_max_chars"]:
        errs.append(f"title {len(t)} chars > {a['title_max_chars']}")
    for ch in a["title_forbid_chars"]:
        if ch in t:
            errs.append(f"title contains {ch!r}")
    if not m.get("description", "").strip():
        errs.append("empty description")
    raw = m.get("keywords", [])
    kws = normalize_keywords(raw)
    if len(kws) != len(raw):
        errs.append(f"{len(raw) - len(kws)} duplicate/empty keywords")
    if not a["keywords_min"] <= len(kws) <= a["keywords_max"]:
        errs.append(f"{len(kws)} keywords, need {a['keywords_min']}-{a['keywords_max']}")
    for k in kws:
        if k in banned or any(w in banned for w in k.split()):
            errs.append(f"banned keyword {k!r}")
        if "," in k:
            errs.append(f"keyword contains comma {k!r}")
    words = {w for w in re.findall(r"[a-z]+", t.lower()) if w not in STOP and w not in banned}
    for w in re.findall(r"[a-z]+", t.lower()):
        if w in banned:
            errs.append(f"banned word in title {w!r}")
    top10 = " ".join(kws[:10])
    missing = sorted(w for w in words if w not in top10)
    if missing:
        warns.append(f"title words not in top-10 keywords: {', '.join(missing)}")
    if str(m.get("category")) not in a["categories"]:
        errs.append(f"invalid Adobe category {m.get('category')!r}")
    fn = m.get("filename", "")
    if len(fn) > a["filename_max_chars"]:
        errs.append(f"filename {len(fn)} chars > {a['filename_max_chars']}")
    if v.get("filename_warn_spaces") and " " in fn:
        warns.append("filename has spaces (Vecteezy recommends none)")
    return {"ok": not errs, "errors": errs, "warnings": warns, "keywords": kws}


def _csv(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerows(rows)
    return buf.getvalue()


def adobe_csv(items: list[dict], cfg: dict) -> str:
    cols = cfg["metadata"]["adobe"]["csv_columns"]
    rows = [cols] + [[i["filename"], i["title"], ", ".join(i["keywords"]), str(i["category"]), i.get("releases", "")]
                     for i in items]
    return _csv(rows)


def vecteezy_csv(items: list[dict], cfg: dict) -> str:
    cols = cfg["metadata"]["vecteezy"]["csv_columns"]
    n = cfg["metadata"]["vecteezy"]["keywords_max"]
    rows = [cols] + [[i["filename"], i["title"], i["description"], ", ".join(i["keywords"][:n])] for i in items]
    return _csv(rows)


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))
