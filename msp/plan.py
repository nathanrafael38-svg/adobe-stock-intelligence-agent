"""Validate a prompt plan (Stage 1 output) before anything is generated."""
from __future__ import annotations

import re

ILLU_SUFFIX = ("Clean illustration isolated on a plain white background, crisp edges, generous empty space "
               "around the subject, no text, no letters, no logos, no watermark, no signature.")
PHOTO_SUFFIX = ("Photorealistic, shot on a full-frame camera with a 50mm lens, sharp focus on the main subject, "
                "natural textures, realistic proportions, anatomically correct hands with five fingers, no text, "
                "no letters, no logos, no brand names, no watermark.")
# Subjects that make generators produce fake text (existing routine rule).
FAKE_TEXT = ["form", "forms", "label", "labels", "sign", "signs", "signage", "keyboard", "typewriter", "book page",
             "newspaper", "receipt", "calendar", "clock face", "dial", "menu board", "poster", "license plate"]
STOP = {"a", "an", "the", "of", "on", "in", "with", "and", "for", "to", "by", "at", "from", "over", "under", "into",
        "its", "is", "are", "close", "up", "shot", "view"}


def concept_tokens(text: str) -> set[str]:
    body = text.replace(ILLU_SUFFIX, "").replace(PHOTO_SUFFIX, "")
    return {w for w in re.findall(r"[a-z]+", body.lower()) if w not in STOP and len(w) > 2}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def validate(items: list[dict], cfg: dict, history_concepts: list[str] | None = None,
             max_similarity: float = 0.5) -> dict:
    """items: [{prompt, type: illustration|photo, aspect, concept, beauty: bool}].
    history_concepts: titles/concepts from earlier batches."""
    comp = cfg["composition"]
    errs, warns = [], []
    n_ill = sum(i.get("type") == "illustration" for i in items)
    n_ph = sum(i.get("type") == "photo" for i in items)
    if len(items) != comp["total"] or n_ill != comp["illustration"]["count"] or n_ph != comp["photo"]["count"]:
        errs.append(f"composition {len(items)} total / {n_ill} illustration / {n_ph} photo, "
                    f"need {comp['total']}/{comp['illustration']['count']}/{comp['photo']['count']}")
    if sum(bool(i.get("beauty")) for i in items) > comp["beauty_max"]:
        errs.append(f"more than {comp['beauty_max']} beauty prompts")
    toks = []
    for idx, i in enumerate(items, 1):
        t, p = i.get("type"), i.get("prompt", "")
        want_aspect = comp.get(t, {}).get("aspect")
        if i.get("aspect") != want_aspect:
            errs.append(f"#{idx}: aspect {i.get('aspect')} != {want_aspect}")
        suffix = ILLU_SUFFIX if t == "illustration" else PHOTO_SUFFIX
        if not p.rstrip().endswith(suffix):
            errs.append(f"#{idx}: missing {t} suffix")
        body = p.replace(suffix, "").lower()
        hits = [w for w in FAKE_TEXT if re.search(rf"\b{re.escape(w)}\b", body)]
        if hits:
            errs.append(f"#{idx}: fake-text-prone subject {hits}")
        if not i.get("concept"):
            errs.append(f"#{idx}: missing concept label")
        toks.append(concept_tokens(i.get("concept", "") + " " + body))
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            s = jaccard(toks[a], toks[b])
            if s >= max_similarity:
                errs.append(f"#{a + 1} and #{b + 1} too similar ({s:.2f})")
        for h in history_concepts or []:
            s = jaccard(concept_tokens(items[a].get("concept", "")), concept_tokens(h))
            if s >= max_similarity:
                warns.append(f"#{a + 1} resembles earlier concept {h!r} ({s:.2f})")
    return {"ok": not errs, "errors": errs, "warnings": warns}
