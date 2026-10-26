"""Technical QC (Stage 4). Deterministic checks only.

Passing technical QC does NOT mean an image is commercially acceptable; the
visual-qc agent gives the subjective verdict and the platform decides acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ASPECTS = {"1:1": 1.0, "16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "3:4": 3 / 4, "3:2": 1.5, "2:3": 2 / 3}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(img: Image.Image, size: int = 8) -> str:
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def sharpness(img: Image.Image, long_edge: int = 1024, grid: int = 16, top: float = 0.05) -> float:
    """Subject sharpness: mean Laplacian variance of the most detailed 5% of tiles.

    A global variance punishes images with large empty areas (flat vector art,
    minimal interiors) although their subject is crisp. Calibrated on C183:
    sharp images 286-9456; a 2 px Gaussian blur drops a photo to ~150 and flat art to ~25.
    """
    g = img.convert("L")
    s = long_edge / max(g.size)
    if s < 1:
        g = g.resize((round(g.width * s), round(g.height * s)), Image.LANCZOS)
    a = np.asarray(g, dtype=np.float32)
    lap = a[1:-1, :-2] + a[1:-1, 2:] + a[:-2, 1:-1] + a[2:, 1:-1] - 4 * a[1:-1, 1:-1]
    h, w = lap.shape
    th, tw = h // grid, w // grid
    v = sorted((float(lap[i * th:(i + 1) * th, j * tw:(j + 1) * tw].var()) for i in range(grid) for j in range(grid)),
               reverse=True)
    n = max(1, int(len(v) * top))
    return round(sum(v[:n]) / n, 1)


def border_stats(img: Image.Image, frac: float = 0.03) -> tuple[float, float]:
    a = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = a.shape
    bh, bw = max(1, int(h * frac)), max(1, int(w * frac))
    border = np.concatenate([a[:bh].ravel(), a[-bh:].ravel(), a[:, :bw].ravel(), a[:, -bw:].ravel()])
    return round(float(border.mean()), 1), round(float(border.std()), 1)


def has_c2pa(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(65536)
    return b"c2pa" in head


def tech_qc(path: Path, expected_type: str, expected_aspect: str, cfg: dict,
            known_hashes: list[tuple[str, str]] | None = None) -> dict:
    """Return {verdict: PASS|FAIL|REVIEW, errors, flags, measures, upscale_eligible}.

    errors -> FAIL (hard technical problem); flags -> REVIEW (needs a human/agent look).
    Error codes are stable strings so the orchestrator can decide on upscaling.
    """
    q = cfg["qc"]
    errors: list[str] = []
    flags: list[str] = []
    m: dict = {}
    try:
        with Image.open(path) as im:
            im.verify()
        im = Image.open(path)
        im.load()
    except Exception as e:  # truncated / corrupt
        return {"verdict": "FAIL", "errors": [f"corrupt:{e}"], "flags": [], "measures": {}, "upscale_eligible": False}

    m.update(format=im.format, mode=im.mode, width=im.width, height=im.height, pixels=im.width * im.height)
    if im.format != "JPEG":
        errors.append("not_jpeg")
    if im.mode != "RGB":
        errors.append(f"mode_{im.mode}")
    ratio = im.width / im.height
    want = ASPECTS.get(expected_aspect)
    m["aspect"] = round(ratio, 4)
    if want is None:
        flags.append(f"unknown_expected_aspect:{expected_aspect}")
    elif abs(ratio - want) / want > q["aspect_tolerance"]:
        errors.append(f"aspect_mismatch:{ratio:.3f}!={expected_aspect}")
    if m["pixels"] < q["min_pixels"]:
        errors.append("below_min_pixels")
    m["sharpness"] = sharpness(im)
    if m["sharpness"] < q["sharpness_min"]:
        errors.append("low_sharpness")
    m["dhash"] = dhash(im)
    m["c2pa"] = has_c2pa(path)
    if expected_type == "illustration":
        bm, bs = border_stats(im)
        m.update(border_mean=bm, border_std=bs)
        if bm < q["illustration_border_mean_min"] or bs > q["illustration_border_std_max"]:
            flags.append("border_not_clean_white")
    for ref, h in known_hashes or []:
        d = hamming(m["dhash"], h)
        if d <= q["near_duplicate_hamming"]:
            flags.append(f"near_duplicate:{ref}:hamming={d}")
    eligible = bool(errors) and all(e in q["upscale_eligible_errors"] for e in errors)
    verdict = "FAIL" if errors else ("REVIEW" if flags else "PASS")
    return {"verdict": verdict, "errors": errors, "flags": flags, "measures": m, "upscale_eligible": eligible}


def known_hashes_from_states(state_dir: Path, exclude_batch: str | None = None) -> list[tuple[str, str]]:
    out = []
    for p in state_dir.glob("C*.json"):
        if p.name.endswith("-plan.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for a in d.get("assets", {}).values():
            h = (a.get("qc_tech") or {}).get("measures", {}).get("dhash")
            if h and a.get("status") not in ("qc_reject",):
                ref = a.get("filename", "?")
                if exclude_batch and d.get("batch_id") == exclude_batch:
                    ref = "same-batch:" + ref
                out.append((ref, h))
    return out
