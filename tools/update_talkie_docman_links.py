#!/usr/bin/env python3
"""Point has_talkie=yes catalog rows at staffel-audit talkie download URLs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from csv_to_catalog_json import CANONICAL_FIELDS
from resolve_downloads import read_catalog, write_catalog
from tag_talkies import default_staffel_audit, parse_staffel_audit_talkie_links

DERIVED_CLEAR_FIELDS = (
    "download_url_mmm_canonical",
    "release_package_filename",
    "release_package_stemname",
    "release_package_size_bytes",
    "game_files_subpath",
    "engine",
    "engine_version",
    "mirror_url_github_private",
    "mirror_url_dropbox_public",
)

_GID_RE = re.compile(r"gid=(\d+)", re.I)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def docman_gid(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    m = _GID_RE.search(url)
    if m:
        return m.group(1)
    path = urlparse(url).path or ""
    m = re.search(r"/(\d+)-", path)
    return m.group(1) if m else ""


def docman_urls_match(a: str, b: str) -> bool:
    a, b = a.strip(), b.strip()
    if not a or not b:
        return False
    ga, gb = docman_gid(a), docman_gid(b)
    if ga and gb:
        return ga == gb
    return a.rstrip("/").lower() == b.rstrip("/").lower()


def clear_derived(row: dict[str, str]) -> None:
    for field in DERIVED_CLEAR_FIELDS:
        row[field] = ""


def apply_talkie_docman(
    rows: list[dict[str, str]], talkie_links: dict[str, str]
) -> tuple[list[str], list[str], list[str]]:
    updated: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    for row in rows:
        if row.get("has_talkie", "").strip().lower() != "yes":
            continue
        cid = row["catalog_id"]
        talkie_url = talkie_links.get(cid, "")
        if not talkie_url:
            missing.append(cid)
            continue
        current = row.get("download_url_mmm_docman", "").strip()
        if docman_urls_match(current, talkie_url):
            skipped.append(cid)
            continue
        row["download_url_mmm_docman"] = talkie_url
        clear_derived(row)
        updated.append(cid)

    return updated, skipped, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument("--staffel-audit", type=Path, default=default_staffel_audit())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    talkie_links = parse_staffel_audit_talkie_links(args.staffel_audit)
    rows = read_catalog(args.csv)
    updated, skipped, missing = apply_talkie_docman(rows, talkie_links)

    print(f"Staffel audit talkie URLs: {len(talkie_links)}")
    print(f"Updated {len(updated)}:")
    for cid in sorted(updated):
        print(f"  {cid}: -> {talkie_links[cid]}")
    if skipped:
        print(f"Already correct ({len(skipped)}): {', '.join(sorted(skipped))}")
    if missing:
        print(f"No staffel talkie URL ({len(missing)}): {', '.join(sorted(missing))}")

    if args.apply:
        write_catalog(args.csv, rows)
        print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
