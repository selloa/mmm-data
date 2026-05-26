#!/usr/bin/env python3
"""Merge walkthrough_mmm_body from walkthrough_mmm_bodies.md back into mmm_catalog.csv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scrape_walkthrough_content import read_catalog, write_catalog
from walkthrough_md_format import normalize_body_for_storage, parse_entries

ENTRY_START = "---entry---"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _repo_root() / "source" / "mmm_catalog.csv"


def _default_md() -> Path:
    return _repo_root() / "source" / "walkthrough_mmm_bodies.md"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=_default_csv())
    p.add_argument("--input", type=Path, default=_default_md())
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="report changes only (default without --apply)",
    )
    p.add_argument("--apply", action="store_true", help="write updated CSV")
    args = p.parse_args(argv)

    if not args.input.is_file():
        print(f"error: not found: {args.input}", file=sys.stderr)
        return 1
    if not args.csv.is_file():
        print(f"error: not found: {args.csv}", file=sys.stderr)
        return 1

    try:
        imported = parse_entries(args.input.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    by_id = {e["catalog_id"]: e for e in imported}
    if len(by_id) != len(imported):
        print("error: duplicate catalog_id in markdown file", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    index = {r["catalog_id"]: r for r in rows}

    unknown = sorted(set(by_id) - set(index))
    if unknown:
        print(f"error: catalog_id(s) not in CSV: {unknown}", file=sys.stderr)
        return 1

    changed: list[str] = []
    for cid, entry in sorted(by_id.items()):
        row = index[cid]
        new_body = normalize_body_for_storage(entry["walkthrough_mmm_body"])
        old_body = normalize_body_for_storage(row.get("walkthrough_mmm_body") or "")
        if new_body != old_body:
            changed.append(cid)
            if args.apply:
                row["walkthrough_mmm_body"] = new_body

    if args.apply:
        write_catalog(args.csv, rows)
        print(f"ok: updated {len(changed)} walkthrough(s) in {args.csv}")
    else:
        for cid in changed:
            print(cid)
        print(f"dry-run: {len(changed)} row(s) would change (use --apply to write)")
    print(f"parsed {len(imported)} entries from {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
