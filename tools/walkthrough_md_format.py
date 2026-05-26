#!/usr/bin/env python3
"""Shared delimiter format for walkthrough_mmm_body markdown export/import."""

from __future__ import annotations

import re

ENTRIES_BEGIN = "---entries-begin---"
ENTRY_START = "---entry---"
ENTRY_END = "---end-entry---"
BODY_START = "---walkthrough_mmm_body---"

META_KEYS = ("catalog_id", "category", "title")

# Gentle breaks before common German walkthrough step openers (after prior text).
_STEP_OPENERS = (
    "Zuerst",
    "Dann",
    "Danach",
    "Als",
    "Nun",
    "Jetzt",
    "Wenn",
    "Nachdem",
    "Später",
    "Gehe",
    "Im",
    "In der",
    "In",
    "Mit",
    "Wir",
    "Eastereggs",
    "Version",
)
_STEP_OPENER_RE = re.compile(
    r"(?<=\S)\s+(?="
    + "|".join(re.escape(s) + r"\b" for s in _STEP_OPENERS)
    + r")"
)
_SPEAKER_RE = re.compile(r"\s+([A-Z][a-zA-ZäöüÄÖÜß]+:)")


def normalize_body_for_storage(text: str) -> str:
    """Canonical single-line form for CSV (cosmetic markdown line breaks are removed)."""
    return re.sub(r"\s+", " ", text).strip()


def format_body_for_display(text: str) -> str:
    """Add light line breaks for human reading (no inserted spaces — safe for import round-trip)."""
    text = normalize_body_for_storage(text)
    if not text:
        return ""
    # One line per sentence where the source already has space after . ! ?
    text = re.sub(r"(?<=[.!?]) +(?=[A-ZÄÖÜ\"'])", "\n", text)
    # Extra paragraph gap before the next major step phrase (existing space only).
    text = _STEP_OPENER_RE.sub("\n\n", text)
    # Speaker / section labels (e.g. Hayden:, Mitch:) when preceded by whitespace.
    text = _SPEAKER_RE.sub(r"\n\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_meta_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    for key in META_KEYS:
        prefix = f"{key}:"
        if stripped.startswith(prefix):
            return key, stripped[len(prefix) :].strip()
    return None


def format_entry_block(
    *,
    catalog_id: str,
    category: str,
    title: str,
    walkthrough_mmm_body: str,
) -> str:
    display_body = format_body_for_display(walkthrough_mmm_body)
    lines = [
        ENTRY_START,
        "",
        f"## {catalog_id} — {title}",
        "",
        f"**category:** {category}",
        "",
        f"catalog_id: {catalog_id}",
        f"category: {category}",
        f"title: {title}",
        "",
        BODY_START,
        "",
        display_body,
        "",
        ENTRY_END,
        "",
    ]
    return "\n".join(lines)


def parse_entries(text: str) -> list[dict[str, str]]:
    """Split markdown file into entry dicts (catalog_id, category, title, walkthrough_mmm_body)."""
    if ENTRIES_BEGIN in text:
        text = text.split(ENTRIES_BEGIN, 1)[1]
    entries: list[dict[str, str]] = []
    blocks = text.split(ENTRY_START)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if ENTRY_END not in block:
            raise ValueError(f"block missing {ENTRY_END!r} (catalog_id may be missing)")
        main, _ = block.split(ENTRY_END, 1)
        main = main.strip()
        if BODY_START not in main:
            raise ValueError(f"block missing {BODY_START!r}")
        meta_part, body = main.split(BODY_START, 1)
        body = normalize_body_for_storage(body)
        meta: dict[str, str] = {}
        for line in meta_part.splitlines():
            parsed = parse_meta_line(line)
            if parsed:
                meta[parsed[0]] = parsed[1]
        missing = [k for k in META_KEYS if k not in meta]
        if missing:
            raise ValueError(f"block missing metadata keys: {missing}")
        entries.append(
            {
                "catalog_id": meta["catalog_id"],
                "category": meta["category"],
                "title": meta["title"],
                "walkthrough_mmm_body": body,
            }
        )
    return entries
