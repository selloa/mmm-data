#!/usr/bin/env python3
"""
Validate derived download fields in mmm_catalog.csv.

Steps (run independently or together):
  1. docman  — resolve download_url_mmm_docman via HTTP; compare to download_url_mmm_canonical
  2. filename — basename of canonical URL vs release_package_filename
             (file.html Joomla endpoints: filename from Content-Disposition via HEAD)
  3. stemname — filename without extension vs release_package_stemname
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from csv_to_catalog_json import CANONICAL_FIELDS

# Reuse resolver from resolve_downloads (same HTTP behavior as fill script)
from resolve_downloads import _default_csv_path, _is_docman_url, filename_from_download_url, resolve


def read_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing header")
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in reader]


def normalize_download_url(url: str) -> str:
    """Normalize for comparison: strip, lowercase scheme/host, unquote path."""
    url = url.strip()
    if not url:
        return ""
    p = urlparse(url)
    path = unquote(p.path or "")
    host = (p.hostname or "").lower()
    scheme = (p.scheme or "https").lower()
    return f"{scheme}://{host}{path}"


def stemname_from_filename(filename: str) -> str:
    filename = filename.strip()
    if not filename:
        return ""
    if "." in filename:
        return filename.rsplit(".", 1)[0]
    return filename


def validate_filename(rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    errors: list[str] = []
    checked = 0
    for row in rows:
        canonical = row.get("download_url_mmm_canonical", "").strip()
        if not canonical:
            continue
        checked += 1
        expected = filename_from_download_url(canonical)
        actual = row.get("release_package_filename", "").strip()
        if not expected:
            errors.append(
                f"{row['catalog_id']}: could not derive filename from canonical URL "
                f"{canonical}"
            )
            continue
        if expected != actual:
            errors.append(
                f"{row['catalog_id']}: release_package_filename "
                f"expected {expected!r}, got {actual!r} "
                f"(from {canonical})"
            )
    return checked, errors


def validate_stemname(rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    errors: list[str] = []
    checked = 0
    for row in rows:
        filename = row.get("release_package_filename", "").strip()
        if not filename:
            continue
        checked += 1
        expected = stemname_from_filename(filename)
        actual = row.get("release_package_stemname", "").strip()
        if expected != actual:
            errors.append(
                f"{row['catalog_id']}: release_package_stemname "
                f"expected {expected!r}, got {actual!r} "
                f"(from filename {filename!r})"
            )
    return checked, errors


def validate_docman(
    rows: list[dict[str, str]], *, quiet_resolve: bool = False
) -> tuple[int, list[str]]:
    errors: list[str] = []
    checked = 0
    pending = [
        r
        for r in rows
        if _is_docman_url(r.get("download_url_mmm_docman", ""))
        and r.get("download_url_mmm_canonical", "").strip()
    ]
    total = len(pending)
    for i, row in enumerate(pending, start=1):
        cid = row["catalog_id"]
        docman = row["download_url_mmm_docman"].strip()
        expected_canonical = row["download_url_mmm_canonical"].strip()
        if not quiet_resolve:
            print(f"[{i}/{total}] {cid} resolving docman...", file=sys.stderr)
        resolved = resolve(docman, quiet=True)
        checked += 1
        if not resolved:
            errors.append(f"{cid}: docman URL did not resolve: {docman}")
            continue
        if normalize_download_url(resolved) != normalize_download_url(expected_canonical):
            errors.append(
                f"{cid}: canonical mismatch\n"
                f"  catalog:   {expected_canonical}\n"
                f"  resolved:  {resolved}"
            )
    return checked, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=_default_csv_path())
    steps = parser.add_argument(
        "steps",
        nargs="*",
        choices=("docman", "filename", "stemname", "all"),
        help="Which checks to run (default: all)",
    )
    parser.add_argument(
        "--quiet-resolve",
        action="store_true",
        help="Less stderr output during docman HTTP checks",
    )
    args = parser.parse_args()
    run = set(args.steps or ("all",))
    if "all" in run:
        run = {"docman", "filename", "stemname"}

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    exit_code = 0

    if "filename" in run:
        n, errs = validate_filename(rows)
        print(f"\n=== Step 2: canonical -> release_package_filename ({n} rows) ===")
        if errs:
            exit_code = 1
            print(f"FAIL: {len(errs)} mismatch(es)")
            for e in errs:
                print(f"  {e}")
        else:
            print("OK: all filenames match canonical download URLs")

    if "stemname" in run:
        n, errs = validate_stemname(rows)
        print(f"\n=== Step 3: filename -> release_package_stemname ({n} rows) ===")
        if errs:
            exit_code = 1
            print(f"FAIL: {len(errs)} mismatch(es)")
            for e in errs:
                print(f"  {e}")
        else:
            print("OK: all stemnames match filename stems")

    if "docman" in run:
        n, errs = validate_docman(rows, quiet_resolve=args.quiet_resolve)
        print(f"\n=== Step 1: docman -> download_url_mmm_canonical ({n} rows) ===")
        if errs:
            exit_code = 1
            print(f"FAIL: {len(errs)} problem(s)")
            for e in errs:
                print(f"  {e}")
        else:
            print("OK: all docman links resolve to catalog canonical URLs")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
