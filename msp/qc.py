"""Technical QC. Objective checks only; visual judgement (text artifacts,
hands, faces, composition, commercial suitability) belongs to the
qc-reviewer agent and is recorded separately."""
from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _aspect(s: str) -> float:
    w, h = s.split(":")
    return float(w) / float(h)


def integrity(path: str) -> list[str]:
    errs = []
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"\xff\xd8"):
        errs.append("not a JPEG (no SOI)")
    if not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
        errs.append("truncated JPEG (no EOI)")
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
    except Exception as e:  # noqa: BLE001
        errs.append(f"decode failed: {e}")
    return errs


def sharpness(gray: np.ndarray, tile: int, pct: float) -> float:
    """Laplacian variance per tile; return the given percentile across tiles
    (high percentile = 'sharpest regions', robust to flat backgrounds)."""
    g = gray.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    h, w = lap.shape
    vals = [lap[y:y + tile, x:x + tile].var()
            for y in range(0, h - tile + 1, tile) for x in range(0, w - tile + 1, tile)]
    return float(np.percentile(vals, pct)) if vals else float(lap.var())


def dhash(img: Image.Image, size: int = 8) -> int:
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def white_border(rgb: np.ndarray, px: int) -> tuple[float, float]:
    b = np.concatenate([rgb[:px].reshape(-1, 3), rgb[-px:].reshape(-1, 3),
                        rgb[:, :px].reshape(-1, 3), rgb[:, -px:].reshape(-1, 3)]).astype(np.float32)
    return float(b.mean()), float(b.std())


def check(path: str, asset_type: str, aspect: str, cfg: dict) -> dict:
    """Return {'verdict': PASS|FAIL|REVIEW, 'errors': [...], 'flags': [...], 'measures': {...}}."""
    q = cfg["qc"]
    res: dict = {"errors": [], "flags": [], "measures": {}}
    res["errors"] += integrity(path)
    if res["errors"]:
        res["verdict"] = "FAIL"
        return res
    with Image.open(path) as im:
        res["measures"].update(format=im.format, mode=im.mode, width=im.width, height=im.height)
        if im.format != "JPEG":
            res["errors"].append(f"format {im.format}, expected JPEG")
        if im.mode != "RGB":
            res["errors"].append(f"mode {im.mode}, expected RGB")
        px = im.width * im.height
        res["measures"]["pixels"] = px
        if px < q["min_pixels"]:
            res["errors"].append(f"{px} px < {q['min_pixels']}")
        want, got = _aspect(aspect), im.width / im.height
        if abs(got - want) / want > q["aspect_tolerance"]:
            res["errors"].append(f"aspect {got:.3f} != {aspect}")
        rgb = np.asarray(im.convert("RGB"))
        res["measures"]["dhash"] = f"{dhash(im):016x}"
    s = sharpness(np.asarray(Image.fromarray(rgb).convert("L")), q["sharpness_tile"], q["sharpness_percentile"])
    res["measures"]["sharpness"] = round(s, 1)
    smin = q["sharpness_min"].get(asset_type)
    if smin is not None and s < smin:
        res["flags"].append(f"sharpness {s:.0f} < {smin}")
    if asset_type == "illustration":
        mean, std = white_border(rgb, q["white_bg_border_px"])
        res["measures"].update(border_mean=round(mean, 1), border_std=round(std, 1))
        if mean < q["white_bg_min_mean"] or std > q["white_bg_max_std"]:
            res["flags"].append(f"background not plain white (border mean {mean:.0f}, std {std:.1f})")
    res["verdict"] = "FAIL" if res["errors"] else ("REVIEW" if res["flags"] else "PASS")
    return res


def near_duplicates(hashes: dict[str, str], max_dist: int, history: dict[str, str] | None = None) -> list[tuple]:
    """Pairs (a, b, dist) within the batch and against history (name->hex)."""
    items = list(hashes.items())
    out = []
    for i, (a, ha) in enumerate(items):
        for b, hb in items[i + 1:]:
            d = hamming(int(ha, 16), int(hb, 16))
            if d <= max_dist:
                out.append((a, b, d))
        for b, hb in (history or {}).items():
            d = hamming(int(ha, 16), int(hb, 16))
            if d <= max_dist:
                out.append((a, b, d))
    return out
