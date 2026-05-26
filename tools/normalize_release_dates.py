#!/usr/bin/env python3
"""Convert release_date values like '02 December 2009' to ISO 'YYYY-MM-DD'."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from scrape_walkthrough_content import read_catalog, write_catalog

_DAY_MONTH_YEAR = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\.?$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _repo_root() / "source" / "mmm_catalog.csv"


def to_iso_date(raw: str) -> str | None:
    """Return YYYY-MM-DD if raw matches 'DD Month YYYY', else None."""
    stripped = raw.strip()
    if not stripped or not _DAY_MONTH_YEAR.match(stripped):
        return None
    try:
        return datetime.strptime(stripped.rstrip("."), "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def process_rows(rows: list[dict[str, str]]) -> list[str]:
    changed: list[str] = []
    for row in rows:
        raw = row.get("release_date") or ""
        iso = to_iso_date(raw)
        if iso and iso != raw.strip():
            changed.append(row["catalog_id"])
            row["release_date"] = iso
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=_default_csv())
    p.add_argument("--apply", action="store_true", help="backup CSV then write changes")
    args = p.parse_args(argv)

    if not args.csv.is_file():
        print(f"error: not found: {args.csv}", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    snapshot = [{**r} for r in rows]
    changed = process_rows(rows)

    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.csv.with_name(f"{args.csv.name}.bak-{stamp}")
        shutil.copy2(args.csv, backup)
        write_catalog(args.csv, rows)
        print(f"backup: {backup}")
        print(f"ok: updated {len(changed)} release_date value(s) in {args.csv}")
        return 0

    for cid in changed:
        before = next(r for r in snapshot if r["catalog_id"] == cid)["release_date"]
        after = next(r for r in rows if r["catalog_id"] == cid)["release_date"]
        print(f"{cid}: {before!r} -> {after!r}")

    print(f"dry-run: {len(changed)} row(s) would change (use --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
