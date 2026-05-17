"""Shared title normalization and catalog matching for MMM walkthrough scrapers."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from html import unescape


def normalize_title(text: str) -> str:
    """Lowercase, strip prefixes, fold accents, drop punctuation for fuzzy compare."""
    s = unescape(text or "").strip().lower()
    s = re.sub(r"^lösung\s*-\s*", "", s)
    s = re.sub(r"^mmm-x-mas\s+\d+:\s*", "", s)
    s = re.sub(r"^hollywood special\s*-\s*", "", s)
    s = re.sub(r"^episode\s+h\d+-\d+:\s*", "", s)
    s = re.sub(r"^#\d+:\s*", "", s)
    s = re.sub(r"^raum\s+\d+:\s*", "", s)
    s = re.sub(r"\s+v\.?\s*\d+(\.\d+)*\s*$", "", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_specials_label(label: str) -> dict:
    """Structured hints from a Komplettlösungen specials list link title."""
    raw = unescape(re.sub(r"\s+", " ", label)).strip()
    s = re.sub(r"^Lösung\s*-\s*", "", raw, flags=re.IGNORECASE)

    m = re.search(r"MD\s*-\s*Room\s*(\d+)", s, re.IGNORECASE)
    if m:
        return {"kind": "md", "room": int(m.group(1))}

    m = re.search(r"Halloween\s+(2005|2006|2010|2011)\s*:\s*H(\d+)", s, re.IGNORECASE)
    if m:
        return {"kind": "halloween", "year": int(m.group(1)), "h": int(m.group(2))}

    if "ronville viper" in s.lower():
        return {"kind": "hl"}

    if "three days before christmas" in s.lower():
        return {"kind": "xc_tdbc", "raw": raw}

    return {"kind": "title", "title": s, "raw": raw}


def halloween_catalog_id(year: int, h: int) -> str | None:
    if year == 2005 and 1 <= h <= 5:
        return f"HS-{h:03d}"
    if year == 2006 and 1 <= h <= 2:
        return f"HS-{5 + h:03d}"
    if year == 2010 and 1 <= h <= 4:
        return f"HS-{7 + h:03d}"
    return None


def parse_underground_label(label: str) -> dict:
    raw = unescape(re.sub(r"\s+", " ", label)).strip()
    s = re.sub(r"^Lösung\s*-\s*", "", raw, flags=re.IGNORECASE)

    if re.search(r"episode\s+66", s, re.IGNORECASE) and re.search(
        r"hoagie", s, re.IGNORECASE
    ):
        return {"kind": "te022"}

    m = re.search(r"meteorhead\s+(?:man\b.*)?(\d+)", s, re.IGNORECASE)
    if m and re.search(r"meteorhead", s, re.IGNORECASE):
        return {"kind": "mh_num", "n": int(m.group(1))}

    if re.search(r"doktor in da house iii", s, re.IGNORECASE):
        return {"kind": "fm", "n": 3}
    if re.search(r"doktor in da house ii", s, re.IGNORECASE):
        return {"kind": "fm", "n": 2}
    if re.search(r"doktor in da house", s, re.IGNORECASE):
        return {"kind": "fm", "n": 1}

    if re.search(r"5th maniac birthday", s, re.IGNORECASE):
        return {"kind": "fm", "n": 7}
    if re.search(r"kochen mit fred", s, re.IGNORECASE):
        return {"kind": "fm", "n": 3}
    if re.search(r"the new president", s, re.IGNORECASE):
        return {"kind": "fm", "n": 4}
    if re.search(r"dinner for one|silvester 2011", s, re.IGNORECASE):
        return {"kind": "fm", "n": 8}
    if re.search(r"just maniac mansion mania", s, re.IGNORECASE):
        return {"kind": "fm", "n": 6}

    return {"kind": "title", "title": s, "raw": raw}


def underground_catalog_id(hint: dict) -> str | None:
    kind = hint.get("kind")
    if kind == "te022":
        return "TE-022"
    if kind == "mh_num":
        n = hint["n"]
        if 1 <= n <= 16:
            return f"MH-{n:03d}"
    if kind == "fm":
        n = hint["n"]
        if 1 <= n <= 8:
            return f"FM-{n:03d}"
    return None


def structured_catalog_id(hint: dict) -> str | None:
    kind = hint.get("kind")
    if kind == "md":
        room = hint["room"]
        if 1 <= room <= 99:
            return f"MD-{room:03d}"
    if kind == "halloween":
        return halloween_catalog_id(hint["year"], hint["h"])
    if kind == "hl":
        return "HL-001"
    if kind == "xc_tdbc":
        return "XC-004"
    return None


def fuzzy_match_catalog_id(
    site_title: str,
    candidates: list[tuple[str, str]],
    *,
    min_ratio: float = 0.72,
) -> str | None:
    """Pick best catalog_id by normalized title similarity."""
    needle = normalize_title(site_title)
    if not needle:
        return None
    best_id = ""
    best_score = 0.0
    for cid, catalog_title in candidates:
        for hay in (catalog_title, catalog_title.split(":", 1)[-1]):
            score = SequenceMatcher(None, needle, normalize_title(hay)).ratio()
            if score > best_score:
                best_score = score
                best_id = cid
    if best_score >= min_ratio:
        return best_id
    return None
