"""Embed title/description/keywords as IPTC-IIM (APP13) and XMP (APP1) without
re-encoding pixels. Stdlib only. The source file is never modified: output
goes to a new path, and image data after the header segments is verified
byte-identical."""
from __future__ import annotations

import hashlib
import re
import struct
from xml.sax.saxutils import escape

XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
PS_NS = b"Photoshop 3.0\x00"
IIM_LIMITS = {5: 64, 25: 64, 105: 256, 120: 2000}  # IPTC IIM 4.2 max octets


class MetadataError(Exception):
    pass


def _segments(data: bytes):
    """Yield (marker, start, end) for header segments up to SOS; then ('SOS', pos, len)."""
    if data[:2] != b"\xff\xd8":
        raise MetadataError("not a JPEG")
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise MetadataError(f"bad marker at {i}")
        m = data[i + 1]
        if m == 0xDA:  # SOS: rest is entropy-coded data
            yield ("SOS", i, len(data))
            return
        if m in (0x01,) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        (ln,) = struct.unpack(">H", data[i + 2:i + 4])
        yield (m, i, i + 2 + ln)
        i += 2 + ln


def _is_xmp(data, s, e):
    return data[s + 4:s + 4 + len(XMP_NS)] == XMP_NS


def _is_ps(data, s, e):
    return data[s + 4:s + 4 + len(PS_NS)] == PS_NS


def _iim(rec: int, ds: int, val: bytes) -> bytes:
    if len(val) > 32767:
        raise MetadataError("IIM value too long")
    return b"\x1c" + bytes([rec, ds]) + struct.pack(">H", len(val)) + val


def build_app13(title: str, description: str, keywords: list[str]) -> bytes:
    t, d = title.encode("utf-8"), description.encode("utf-8")
    for ds, v in ((5, t), (105, t), (120, d)):
        if len(v) > IIM_LIMITS[ds]:
            raise MetadataError(f"IPTC 2:{ds:02d} {len(v)} bytes > {IIM_LIMITS[ds]} (would be truncated)")
    iim = _iim(1, 90, b"\x1b%G")  # coded character set = UTF-8
    iim += _iim(2, 0, b"\x00\x04")
    iim += _iim(2, 5, t)
    for kw in keywords:
        kb = kw.encode("utf-8")
        if len(kb) > IIM_LIMITS[25]:
            raise MetadataError(f"keyword too long: {kw!r}")
        iim += _iim(2, 25, kb)
    iim += _iim(2, 105, t) + _iim(2, 120, d)
    if len(iim) % 2:
        iim += b"\x00"
    res = b"8BIM" + struct.pack(">H", 0x0404) + b"\x00\x00" + struct.pack(">I", len(iim)) + iim
    payload = PS_NS + res
    return b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload


def build_xmp(title: str, description: str, keywords: list[str]) -> bytes:
    li = "".join(f"<rdf:li>{escape(k)}</rdf:li>" for k in keywords)
    xml = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(title)}</rdf:li></rdf:Alt></dc:title>'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{escape(description)}</rdf:li></rdf:Alt></dc:description>'
        f"<dc:subject><rdf:Bag>{li}</rdf:Bag></dc:subject>"
        f"<photoshop:Headline>{escape(title)}</photoshop:Headline>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")
    payload = XMP_NS + xml
    if len(payload) + 2 > 65535:
        raise MetadataError("XMP packet too large for one APP1")
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def image_data_hash(data: bytes) -> str:
    """Hash of everything except APPn/COM segments: proves pixels untouched."""
    h = hashlib.sha256()
    for m, s, e in _segments(data):
        if m == "SOS":
            h.update(data[s:e])
        elif not (0xE0 <= m <= 0xEF or m == 0xFE):
            h.update(data[s:e])
    return h.hexdigest()


def embed(src: str, dst: str, title: str, description: str, keywords: list[str]) -> dict:
    if src == dst:
        raise MetadataError("refusing to modify source in place")
    with open(src, "rb") as f:
        data = f.read()
    segs = list(_segments(data))
    keep, insert_at = [], None
    for m, s, e in segs:
        if m == "SOS" or not (0xE0 <= m <= 0xEF):
            if insert_at is None:
                insert_at = len(keep)
            keep.append(data[s:e])
            continue
        if (m == 0xE1 and _is_xmp(data, s, e)) or (m == 0xED and _is_ps(data, s, e)):
            continue  # replaced below
        keep.append(data[s:e])
    new = [b"\xff\xd8"] + keep[:insert_at] + [build_xmp(title, description, keywords),
                                             build_app13(title, description, keywords)] + keep[insert_at:]
    out = b"".join(new)
    if image_data_hash(out) != image_data_hash(data):
        raise MetadataError("image data changed during embed")
    with open(dst, "wb") as f:
        f.write(out)
    return {"src_image_hash": image_data_hash(data), "dst_bytes": len(out)}


def read(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    out = {"iptc": {}, "xmp": {}}
    for m, s, e in _segments(data):
        if m == 0xED and _is_ps(data, s, e):
            body = data[s + 4 + len(PS_NS):e]
            j = 0
            while j + 12 <= len(body) and body[j:j + 4] == b"8BIM":
                rid = struct.unpack(">H", body[j + 4:j + 6])[0]
                nl = body[j + 6]
                j2 = j + 7 + nl + ((nl + 1) % 2)
                size = struct.unpack(">I", body[j2:j2 + 4])[0]
                blob = body[j2 + 4:j2 + 4 + size]
                if rid == 0x0404:
                    p = 0
                    while p + 5 <= len(blob) and blob[p] == 0x1C:
                        rec, ds = blob[p + 1], blob[p + 2]
                        ln = struct.unpack(">H", blob[p + 3:p + 5])[0]
                        val = blob[p + 5:p + 5 + ln]
                        if rec == 2 and ds != 0:
                            out["iptc"].setdefault(ds, []).append(val.decode("utf-8", "replace"))
                        p += 5 + ln
                j = j2 + 4 + size + (size % 2)
        elif m == 0xE1 and _is_xmp(data, s, e):
            x = data[s + 4 + len(XMP_NS):e].decode("utf-8", "replace")
            t = re.search(r"<dc:title>.*?<rdf:li[^>]*>(.*?)</rdf:li>", x, re.S)
            d = re.search(r"<dc:description>.*?<rdf:li[^>]*>(.*?)</rdf:li>", x, re.S)
            bag = re.search(r"<dc:subject>(.*?)</dc:subject>", x, re.S)
            from xml.sax.saxutils import unescape
            out["xmp"] = {
                "title": unescape(t.group(1)) if t else None,
                "description": unescape(d.group(1)) if d else None,
                "keywords": [unescape(k) for k in re.findall(r"<rdf:li>(.*?)</rdf:li>", bag.group(1))] if bag else [],
            }
    return out


def verify(path: str, title: str, description: str, keywords: list[str]) -> list[str]:
    r = read(path)
    errs = []
    i = r["iptc"]
    if i.get(5) != [title]:
        errs.append(f"IPTC 2:05 {i.get(5)}")
    if i.get(105) != [title]:
        errs.append(f"IPTC 2:105 {i.get(105)}")
    if i.get(120) != [description]:
        errs.append(f"IPTC 2:120 {i.get(120)}")
    if i.get(25) != keywords:
        errs.append(f"IPTC 2:25 {len(i.get(25) or [])} keywords, expected {len(keywords)}")
    x = r["xmp"]
    if x.get("title") != title or x.get("description") != description or x.get("keywords") != keywords:
        errs.append("XMP mismatch")
    return errs
