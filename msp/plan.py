"""Validate a prompt plan (Stage 1) and render the prompt sheet for Flow."""
from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED_KEYS = {"concept", "type", "aspect", "prompt"}
ILLU_SUFFIX_MARKERS = ["no text", "no watermark"]
PHOTO_SUFFIX_MARKERS = ["photorealistic", "no text", "no watermark"]
HAND_WORDS = re.compile(r"\b(hand|hands|finger|fingers|person|people|man|woman|child|chef|worker)\b", re.I)
HAND_CLAUSE = re.compile(r"anatomically correct hands", re.I)
STOP = set("a an the of on in with and or to for at by from into over under beside near".split())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", text.lower()) if t not in STOP and len(t) > 2}


STYLE = set("watercolor watercolour illustration photo photograph flat vector line drawing close closeup macro "
            "cartoon minimalist isolated single top view".split())
SETTING_SPLIT = re.compile(r"\b(on|in|with|beside|near|at|over|under|against|inside|during)\b", re.I)


def _subject(text: str) -> set[str]:
    head = SETTING_SPLIT.split(text, maxsplit=1)[0]
    return {t[:-1] if t.endswith("s") and len(t) > 4 else t for t in _tokens(head)} - STYLE


def similarity(a: str, b: str) -> float:
    """Max of whole-concept Jaccard and subject-phrase overlap coefficient.

    'watercolor pomegranate slice' vs 'watercolor pomegranate cut in half' -> 0.5 (same subject),
    'bicycle on wooden table' vs 'lantern on wooden table' -> low (setting ignored).
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    sa, sb = _subject(a), _subject(b)
    ovl = len(sa & sb) / min(len(sa), len(sb)) if sa and sb else 0.0
    return max(jac, ovl)


def is_duplicate(a: str, b: str) -> bool:
    """Duplicate when the whole concept is very similar (Jaccard >= 0.6) or the
    subject phrases overlap by half or more."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if len(ta & tb) / len(ta | tb) >= 0.6:
        return True
    sa, sb = _subject(a), _subject(b)
    return bool(sa and sb) and len(sa & sb) / min(len(sa), len(sb)) >= 0.5


def history_concepts(state_dir: Path) -> list[tuple[str, str]]:
    """(batch_id, concept) for every asset in previous batch states."""
    out = []
    for p in sorted(state_dir.glob("C*.json")):
        if p.name.endswith("-plan.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for a in d.get("assets", {}).values():
            out.append((d.get("batch_id", p.stem), a.get("concept", "")))
    return out


def validate(plan: list[dict], cfg: dict, history: list[tuple[str, str]]) -> list[str]:
    """Return a list of human-readable errors; empty list means valid."""
    errors: list[str] = []
    want = {(c["type"], c["aspect"]): c["count"] for c in cfg["composition"]}
    got: dict[tuple[str, str], int] = {}
    banned = [t.lower() for t in cfg["metadata"]["banned_terms"]]
    for i, item in enumerate(plan, start=1):
        tag = f"#{i} ({item.get('concept', '?')})"
        missing = REQUIRED_KEYS - set(item)
        if missing:
            errors.append(f"{tag}: missing {sorted(missing)}")
            continue
        key = (item["type"], item["aspect"])
        got[key] = got.get(key, 0) + 1
        p = item["prompt"].lower()
        markers = ILLU_SUFFIX_MARKERS if item["type"] == "illustration" else PHOTO_SUFFIX_MARKERS
        for m in markers:
            if m not in p:
                errors.append(f"{tag}: prompt lacks required phrase '{m}'")
        if HAND_CLAUSE.search(item["prompt"]) and not HAND_WORDS.search(item["concept"] + " " + item["prompt"].split(".")[0]):
            errors.append(f"{tag}: hands clause present but subject has no people/hands (invites stray hands)")
        for b in banned:
            if b in ("4k", "8k", "hd"):
                continue  # resolution words are tolerated in prompts, banned only in metadata
            if b in p:
                errors.append(f"{tag}: banned term '{b}' in prompt")
        for j, other in enumerate(plan[:i - 1], start=1):
            if is_duplicate(item["concept"], other.get("concept", "")):
                errors.append(f"{tag}: near-duplicate of #{j} in this plan")
        for bid, c in history:
            if is_duplicate(item["concept"], c):
                errors.append(f"{tag}: near-duplicate of earlier concept '{c}' ({bid})")
                break
    if got != want:
        errors.append(f"composition {dict((f'{t} {a}', n) for (t, a), n in got.items())} != required "
                      f"{dict((f'{t} {a}', n) for (t, a), n in want.items())}")
    return errors


def prompt_sheet(batch_id: str, project: str, plan: list[dict], filenames: list[str]) -> str:
    """Plain-text sheet Nathan pastes from, one prompt per block, grouped by aspect."""
    lines = [f"{batch_id} — Flow project: {project}", "Settings: Nano Banana Pro, x1 output per prompt.",
             "CHECK the aspect ratio before each group; Flow keeps the last used ratio.", ""]
    for aspect in sorted({p["aspect"] for p in plan}):
        lines.append(f"===== ASPECT {aspect} =====")
        for k, (item, fn) in enumerate(zip(plan, filenames), start=1):
            if item["aspect"] != aspect:
                continue
            lines += [f"[{k:02d}] {fn} — {item['type']} — {item['concept']}", item["prompt"], ""]
    return "\n".join(lines)
