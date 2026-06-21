#!/usr/bin/env python3
"""Fill release_package_size_bytes from files in the local mirror folder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from download_mirror_packages import DEFAULT_MIRROR, read_catalog
from resolve_downloads import write_catalog


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def fill_sizes(
    rows: list[dict[str, str]], mirror_dir: Path, *, only_missing: bool
) -> tuple[int, int, int]:
    updated = missing_file = skipped = 0
    for row in rows:
        fn = (row.get("release_package_filename") or "").strip()
        if not fn:
            continue
        if only_missing and (row.get("release_package_size_bytes") or "").strip():
            skipped += 1
            continue
        path = mirror_dir / fn
        if not path.is_file():
            missing_file += 1
            continue
        size = path.stat().st_size
        row["release_package_size_bytes"] = str(size)
        updated += 1
    return updated, missing_file, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="skip rows that already have release_package_size_bytes",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    updated, missing_file, skipped = fill_sizes(
        rows, args.mirror_dir, only_missing=args.only_missing
    )
    print(f"Mirror: {args.mirror_dir}")
    print(f"Updated: {updated}, file not in mirror: {missing_file}, skipped: {skipped}")

    if args.dry_run:
        return 0

    write_catalog(args.csv, rows)
    print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
