#!/usr/bin/env python3
"""Export walkthrough_mmm_body rows from mmm_catalog.csv to a structured markdown file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scrape_walkthrough_content import read_catalog
from walkthrough_md_format import ENTRIES_BEGIN, format_entry_block

HEADER = f"""# MMM walkthrough bodies

Machine-readable sections for rows that have `walkthrough_mmm_body` in the catalog.

Delimiter lines (do not edit): `---entry---`, `---walkthrough_mmm_body---`, `---end-entry---`.
Machine metadata (required for import): `catalog_id:`, `category:`, `title:` lines.
Walkthrough text may use cosmetic line breaks; import collapses them back to one line for the CSV.

Re-import with: `python tools/import_walkthrough_bodies_md.py`

{ENTRIES_BEGIN}

"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _repo_root() / "source" / "mmm_catalog.csv"


def _default_md() -> Path:
    return _repo_root() / "source" / "walkthrough_mmm_bodies.md"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=_default_csv())
    p.add_argument("--out", type=Path, default=_default_md())
    args = p.parse_args(argv)

    if not args.csv.is_file():
        print(f"error: not found: {args.csv}", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    with_body = [
        r
        for r in rows
        if (r.get("walkthrough_mmm_body") or "").strip()
    ]
    with_body.sort(key=lambda r: r["catalog_id"])

    parts = [HEADER]
    for row in with_body:
        parts.append(
            format_entry_block(
                catalog_id=row["catalog_id"],
                category=row.get("category") or "",
                title=row.get("title") or "",
                walkthrough_mmm_body=row["walkthrough_mmm_body"],
            )
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(parts), encoding="utf-8", newline="\n")
    print(f"ok: {len(with_body)} entries -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
