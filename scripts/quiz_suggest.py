#!/usr/bin/env python3
"""Suggest quiz question ideas for an upcoming month (dev workflow)."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from quiz_lib import (
    EPISODES_PER_SEASON,
    SUGGESTIONS_DIR,
    episode_number,
    load_catalog,
    parse_release_date,
    staffel_from_episode,
)

MONTH_NAMES_DE = [
    "",
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]

SEASONAL_HINTS = {
    10: ("Halloween Specials", "HS-"),
    12: ("Weihnachts-Specials", "FS-"),
    4: ("Oster-Specials / Edgar Award", "EA-"),
}


def parse_month(s: str) -> tuple[int, int]:
    parts = s.strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"expected YYYY-MM, got {s!r}")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12):
        raise ValueError(f"month out of range: {month}")
    return year, month


def format_de_date(day: int, month: int, year: int) -> str:
    return f"{day}. {MONTH_NAMES_DE[month]} {year}"


def anniversary_entries(catalog: list[dict], year: int, month: int, ref_year: int) -> list[dict]:
    hits: list[dict] = []
    for row in catalog:
        parsed = parse_release_date(row.get("release_date", ""))
        if not parsed or parsed.get("precision") != "day":
            continue
        if parsed["month"] != month:
            continue
        age = ref_year - parsed["year"]
        if age < 1:
            continue
        hits.append(
            {
                "row": row,
                "parsed": parsed,
                "age": age,
                "round5": age % 5 == 0,
                "round10": age % 10 == 0,
            }
        )
    hits.sort(key=lambda h: (h["parsed"]["day"], h["row"]["title"]))
    return hits


def staffel_for_month(month: int) -> int:
    """Loose thematic hint: map calendar month to a staffel number 1–10."""
    return ((month - 1) % 10) + 1


def staffel_episodes(catalog: list[dict], staffel: int) -> list[dict]:
    out = []
    for row in catalog:
        if row.get("category") != "MMM Episoden":
            continue
        ep = episode_number(row["catalog_id"])
        if ep > 0 and staffel_from_episode(ep) == staffel:
            out.append(row)
    out.sort(key=lambda r: episode_number(r["catalog_id"]))
    return out


def pick_distractor_authors(catalog: list[dict], exclude: str, n: int = 3) -> list[str]:
    authors: set[str] = set()
    for row in catalog:
        if row.get("category") != "MMM Episoden":
            continue
        raw = (row.get("authors") or "").strip()
        for part in raw.split(","):
            a = part.strip()
            if a and a != exclude:
                authors.add(a)
    pool = sorted(authors)
    if len(pool) <= n:
        return pool
    return random.sample(pool, n)


def author_draft_struct(row: dict, catalog: list[dict]) -> dict | None:
    author = (row.get("authors") or "").split(",")[0].strip()
    if not author:
        return None
    distractors = pick_distractor_authors(catalog, author)
    options = [author] + distractors
    while len(options) < 4:
        options.append("???")
    options = options[:4]
    wiki = (row.get("wiki_url_mmm") or "").strip() or None
    return {
        "catalog_id": row["catalog_id"],
        "title": row["title"],
        "category": "autoren",
        "category_label": "Autoren",
        "question": f"Wer schrieb {row['title']}?",
        "options": options,
        "correct_index": 0,
        "explanation": f"Autor von {row['title']}: {author}.",
        "links": {"catalog_id": row["catalog_id"], "wiki": wiki},
    }


def synopsis_draft(row: dict, catalog: list[dict]) -> str | None:
    desc = (row.get("mmm_description") or "").strip()
    if len(desc) < 40:
        return None
    title = row["title"]
    author = (row.get("authors") or "").split(",")[0].strip()
    distractors = pick_distractor_authors(catalog, author)
    lines = [
        f"- **ENTWURF — Autor** (`{row['catalog_id']}`)",
        f"  - Frage: Wer schrieb *{title}*?",
        f"  - Antwort: {author}",
        f"  - Distraktoren: {', '.join(distractors)}",
        "",
    ]
    return "\n".join(lines)


def build_suggestions(
    year: int,
    month: int,
    catalog: list[dict] | None = None,
) -> dict:
    catalog = catalog if catalog is not None else load_catalog()
    ref_year = year
    staffel = staffel_for_month(month)
    eps = staffel_episodes(catalog, staffel)
    anniversaries_raw = anniversary_entries(catalog, year, month, ref_year)

    anniversaries = []
    for entry in anniversaries_raw:
        row = entry["row"]
        parsed = entry["parsed"]
        flags = []
        if entry["round10"]:
            flags.append("10er")
        elif entry["round5"]:
            flags.append("5er")
        anniversaries.append(
            {
                "catalog_id": row["catalog_id"],
                "title": row["title"],
                "release_date": format_de_date(parsed["day"], parsed["month"], parsed["year"]),
                "age": entry["age"],
                "flags": flags,
                "wiki": (row.get("wiki_url_mmm") or "").strip() or None,
                "hint": "Chronik-Frage zum Release-Datum oder Titel",
            }
        )

    author_drafts: list[dict] = []
    for row in eps:
        draft = author_draft_struct(row, catalog)
        if draft:
            author_drafts.append(draft)
        if len(author_drafts) >= 4:
            break

    seasonal_hint = None
    if month in SEASONAL_HINTS:
        cat_name, prefix = SEASONAL_HINTS[month]
        seasonal = [r for r in catalog if r["catalog_id"].startswith(prefix)]
        seasonal_hint = {
            "category": cat_name,
            "prefix": prefix,
            "count": len(seasonal),
            "samples": [
                {"catalog_id": r["catalog_id"], "title": r["title"]} for r in seasonal[:5]
            ],
        }

    return {
        "year": year,
        "month": month,
        "month_label": MONTH_NAMES_DE[month],
        "staffel": staffel,
        "staffel_episodes": [
            {"catalog_id": r["catalog_id"], "title": r["title"]} for r in eps
        ],
        "anniversaries": anniversaries,
        "author_drafts": author_drafts,
        "seasonal_hint": seasonal_hint,
    }


def chronik_draft(entry: dict, ref_year: int) -> str:
    row = entry["row"]
    parsed = entry["parsed"]
    age = entry["age"]
    when = format_de_date(parsed["day"], parsed["month"], parsed["year"])
    flags = []
    if entry["round10"]:
        flags.append("10er-Jubiläum")
    elif entry["round5"]:
        flags.append("5er-Jubiläum")
    flag_txt = f" ({', '.join(flags)})" if flags else ""
    return (
        f"- **{row['catalog_id']}** — *{row['title']}*{flag_txt}\n"
        f"  - Release: {when} → wird {age} Jahre alt (Stand {ref_year})\n"
        f"  - Idee: Chronik-Frage zum Release-Datum oder zum Titel\n"
        f"  - Wiki: {row.get('wiki_url_mmm') or '—'}\n"
    )


def build_markdown(year: int, month: int, catalog: list[dict]) -> str:
    ref_year = year
    month_name = MONTH_NAMES_DE[month]
    staffel = staffel_for_month(month)
    eps = staffel_episodes(catalog, staffel)
    anniversaries = anniversary_entries(catalog, year, month, ref_year)

    lines = [
        f"# Quiz-Vorschläge — {month_name} {year}",
        "",
        "Entwürfe zur manuellen Übernahme in `quiz/rounds/`. Nicht automatisch veröffentlichen.",
        "",
        f"Empfohlenes Monats-Motto: **Staffel {staffel}** ({len(eps)} Hauptepisoden im Katalog)",
        "",
        "## Jubiläen im Monat",
        "",
    ]

    if anniversaries:
        for entry in anniversaries:
            lines.append(chronik_draft(entry, ref_year))
    else:
        lines.append("_Keine tag-genauen Release-Daten in diesem Monat._\n")

    if month in SEASONAL_HINTS:
        cat_name, prefix = SEASONAL_HINTS[month]
        seasonal = [r for r in catalog if r["catalog_id"].startswith(prefix)]
        lines.extend(
            [
                "",
                "## Saison-Hinweis",
                "",
                f"Monat {month} → **{cat_name}** ({len(seasonal)} Einträge mit Präfix `{prefix}`)",
                "",
            ]
        )
        for row in seasonal[:5]:
            lines.append(f"- {row['catalog_id']}: {row['title']}")

    lines.extend(
        [
            "",
            "## Staffel-Thema",
            "",
            f"Staffel **{staffel}** (Episoden "
            f"{(staffel - 1) * EPISODES_PER_SEASON + 1:03d}–{staffel * EPISODES_PER_SEASON:03d}):",
            "",
        ]
    )
    for row in eps[:8]:
        lines.append(f"- {row['catalog_id']}: {row['title']}")
    if len(eps) > 8:
        lines.append(f"- … und {len(eps) - 8} weitere")

    lines.extend(["", "## Template-Entwürfe (Autor)", ""])
    drafts = 0
    for row in eps:
        block = synopsis_draft(row, catalog)
        if block:
            lines.append(block)
            drafts += 1
        if drafts >= 4:
            break
    if drafts == 0:
        lines.append("_Keine Synopsen für Template-Entwürfe in dieser Staffel._\n")

    lines.extend(
        [
            "",
            "## Nächste Schritte",
            "",
            "1. Vier Slots für ISO-Wochen des Monats wählen",
            "2. Gewünschte Entwürfe in `quiz/rounds/YYYY-MM.json` eintragen",
            "3. `python scripts/build_catalog_site.py` ausführen",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest MMM quiz questions for a month")
    parser.add_argument(
        "--month",
        required=True,
        help="Target month as YYYY-MM (e.g. 2026-07)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output markdown path (default: quiz/suggestions/YYYY-MM.md)",
    )
    args = parser.parse_args()

    year, month = parse_month(args.month)
    catalog = load_catalog()
    md = build_markdown(year, month, catalog)

    out = args.output or (SUGGESTIONS_DIR / f"{year}-{month:02d}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
