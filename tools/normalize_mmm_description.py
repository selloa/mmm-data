#!/usr/bin/env python3
"""Flatten mmm_description: replace all whitespace runs with a single space."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from scrape_walkthrough_content import read_catalog, write_catalog

PREVIEW_LEN = 80


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _repo_root() / "source" / "mmm_catalog.csv"


def flatten_description(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip()


def _preview(text: str) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= PREVIEW_LEN:
        return one_line
    return one_line[: PREVIEW_LEN - 3] + "..."


def process_rows(rows: list[dict[str, str]]) -> list[str]:
    """Update mmm_description in place; return catalog_ids that changed."""
    changed: list[str] = []
    for row in rows:
        raw = row.get("mmm_description") or ""
        if not raw.strip():
            continue
        flat = flatten_description(raw)
        if flat != raw.strip():
            changed.append(row["catalog_id"])
            row["mmm_description"] = flat
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=_default_csv(), help="catalog CSV path")
    p.add_argument(
        "--apply",
        action="store_true",
        help="backup CSV then write flattened descriptions (default: dry-run)",
    )
    args = p.parse_args(argv)

    if not args.csv.is_file():
        print(f"error: not found: {args.csv}", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    rows_copy = [{**r, "mmm_description": r.get("mmm_description") or ""} for r in rows]
    changed_ids = process_rows(rows)

    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.csv.with_name(f"{args.csv.name}.bak-{stamp}")
        shutil.copy2(args.csv, backup)
        write_catalog(args.csv, rows)
        print(f"backup: {backup}")
        print(f"ok: updated {len(changed_ids)} row(s) in {args.csv}")
        return 0

    for cid in changed_ids:
        before = next(r for r in rows_copy if r["catalog_id"] == cid)["mmm_description"]
        after = next(r for r in rows if r["catalog_id"] == cid)["mmm_description"]
        print(f"{cid}:")
        print(f"  before: {_preview(before)}")
        print(f"  after:  {_preview(after)}")

    print(f"dry-run: {len(changed_ids)} row(s) would change (use --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
