#!/usr/bin/env python3
"""Shared helpers for MMM weekly quiz build and suggestion tools."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUNDS_DIR = REPO_ROOT / "quiz" / "rounds"
SOURCE_CSV = REPO_ROOT / "source" / "mmm_catalog.csv"
SUGGESTIONS_DIR = REPO_ROOT / "quiz" / "suggestions"

CATEGORY_MERGE = {"Fan-Games": "Fan Games"}
EPISODES_PER_SEASON = 10

UNVERIFIED_PREFIX = re.compile(r"^\(unverified\)\s*", re.IGNORECASE)
DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
DATE_YEAR = re.compile(r"^(\d{4})")
WEEK_ID = re.compile(r"^\d{4}-W\d{2}$")

QUIZ_BASE_URL = "https://selloa.github.io/mmm-data/quiz/"
CATALOG_BASE_URL = "https://selloa.github.io/mmm-data/"


def parse_release_date(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text or text.lower() in ("null", "none", "n/a"):
        return None

    unverified = False
    if UNVERIFIED_PREFIX.match(text):
        unverified = True
        text = UNVERIFIED_PREFIX.sub("", text).strip()

    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()

    m = DATE_ISO.match(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return {
            "year": year,
            "month": month,
            "day": day,
            "precision": "day",
            "unverified": unverified,
            "raw": raw.strip(),
        }

    m = DATE_YEAR.match(text)
    if m:
        return {
            "year": int(m.group(1)),
            "precision": "year",
            "unverified": unverified,
            "raw": raw.strip(),
        }

    return None


def episode_number(catalog_id: str) -> int:
    if catalog_id.startswith("EP-"):
        try:
            return int(catalog_id[3:])
        except ValueError:
            return 0
    return 0


def staffel_from_episode(ep: int) -> int:
    if ep <= 0:
        return 0
    return ((ep - 1) // EPISODES_PER_SEASON) + 1


def load_catalog() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = (row.get("catalog_id") or "").strip()
            if not cid:
                continue
            cat = row.get("category", "").strip()
            row["category"] = CATEGORY_MERGE.get(cat, cat)
            rows.append(row)
    return rows


def catalog_ids(catalog: list[dict[str, str]] | None = None) -> set[str]:
    catalog = catalog if catalog is not None else load_catalog()
    return {r["catalog_id"] for r in catalog}


def load_round_files(rounds_dir: Path | None = None) -> list[dict]:
    rounds_dir = rounds_dir or ROUNDS_DIR
    if not rounds_dir.is_dir():
        return []

    all_rounds: list[dict] = []
    for path in sorted(rounds_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        file_rounds = data.get("rounds")
        if not isinstance(file_rounds, list):
            raise ValueError(f"{path}: expected top-level 'rounds' array")
        for r in file_rounds:
            r["_source_file"] = path.name
        all_rounds.extend(file_rounds)
    return all_rounds


def validate_rounds(
    rounds: list[dict],
    catalog: list[dict[str, str]] | None = None,
) -> None:
    ids = catalog_ids(catalog)
    seen_weeks: set[str] = set()
    errors: list[str] = []

    for i, r in enumerate(rounds):
        label = r.get("week") or f"round[{i}]"
        src = r.get("_source_file", "?")

        week = r.get("week")
        if not week or not WEEK_ID.match(week):
            errors.append(f"{src} {label}: invalid or missing week (expected YYYY-Wnn)")
            continue
        if week in seen_weeks:
            errors.append(f"{src} {week}: duplicate week")
        seen_weeks.add(week)

        question = (r.get("question") or "").strip()
        if not question:
            errors.append(f"{src} {week}: missing question")

        options = r.get("options")
        if not isinstance(options, list) or len(options) != 4:
            errors.append(f"{src} {week}: options must be an array of exactly 4 strings")
        elif any(not isinstance(o, str) or not o.strip() for o in options):
            errors.append(f"{src} {week}: all options must be non-empty strings")

        ci = r.get("correct_index")
        if not isinstance(ci, int) or ci < 0 or ci > 3:
            errors.append(f"{src} {week}: correct_index must be 0–3")

        if not (r.get("category_label") or r.get("category")):
            errors.append(f"{src} {week}: missing category or category_label")

        links = r.get("links") or {}
        cid = links.get("catalog_id")
        if cid and cid not in ids:
            errors.append(f"{src} {week}: unknown catalog_id {cid!r}")

    if errors:
        for e in errors:
            print(f"quiz validate error: {e}", file=sys.stderr)
        raise SystemExit(1)


def build_schedule(rounds: list[dict]) -> dict:
    """Public schedule keyed by ISO week (strips dev-only fields)."""
    by_week: dict[str, dict] = {}
    week_order: list[str] = []

    for r in sorted(rounds, key=lambda x: x.get("week", "")):
        week = r["week"]
        week_order.append(week)
        links = dict(r.get("links") or {})
        by_week[week] = {
            "week": week,
            "theme": r.get("theme"),
            "category": r.get("category"),
            "category_label": r.get("category_label") or r.get("category"),
            "question": r["question"],
            "options": r["options"],
            "correct_index": r["correct_index"],
            "explanation": r.get("explanation", ""),
            "links": links,
        }

    return {
        "base_url": QUIZ_BASE_URL,
        "catalog_url": CATALOG_BASE_URL,
        "week_order": week_order,
        "rounds": by_week,
    }
