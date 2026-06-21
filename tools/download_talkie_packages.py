#!/usr/bin/env python3
"""Download missing talkie packages and fill catalog fields after each one."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from csv_to_catalog_json import CANONICAL_FIELDS
from download_mirror_packages import (
    DEFAULT_MIRROR,
    download_url_to_file,
    pick_download_url,
    resolve_if_needed,
)
from probe_ags_packages import (
    apply_probe_to_catalog,
    layout_to_subpath,
    probe_archive,
)
from resolve_downloads import filename_from_download_url, resolve


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def stemname_from_filename(filename: str) -> str:
    filename = filename.strip()
    if not filename:
        return ""
    if "." in filename:
        return filename.rsplit(".", 1)[0]
    return filename


def expected_filename(row: dict[str, str]) -> str:
    fn = (row.get("release_package_filename") or "").strip()
    if fn:
        return fn
    canonical = (row.get("download_url_mmm_canonical") or "").strip()
    if canonical:
        base = unquote(urlparse(canonical).path or "").rsplit("/", 1)[-1]
        if base and base.lower() not in {"file.html", "file.htm"}:
            return base
    docman = (row.get("download_url_mmm_docman") or "").strip()
    if docman:
        name = filename_from_download_url(docman)
        if name:
            return name
    return ""


def read_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in reader]


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def row_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r["catalog_id"]: r for r in rows}


def ensure_canonical(row: dict[str, str]) -> bool:
    if (row.get("download_url_mmm_canonical") or "").strip():
        return True
    docman = (row.get("download_url_mmm_docman") or "").strip()
    if not docman:
        return False
    canonical = resolve(docman, quiet=True)
    if not canonical:
        return False
    row["download_url_mmm_canonical"] = canonical
    return True


def fill_from_probe(row: dict[str, str], archive: Path) -> None:
    probe = probe_archive(row["catalog_id"], archive)
    fn = archive.name
    row["release_package_filename"] = fn
    row["release_package_stemname"] = stemname_from_filename(fn)
    row["release_package_size_bytes"] = str(archive.stat().st_size)
    if probe.is_ags is True:
        row["engine"] = "AGS"
        row["engine_version"] = probe.ags_version or ""
        row["game_files_subpath"] = layout_to_subpath(probe.layout)
    elif probe.is_ags is False:
        row["engine"] = "unknown"
        row["engine_version"] = ""
        row["game_files_subpath"] = ""


def process_talkie(
    row: dict[str, str],
    *,
    mirror_dir: Path,
    delay: float,
) -> tuple[str, str]:
    """Returns (status, detail) where status is ok|skip|fail."""
    cid = row["catalog_id"]
    if row.get("has_talkie", "").strip().lower() != "yes":
        return "skip", "not a talkie row"

    if not ensure_canonical(row):
        raw = pick_download_url(row)
        if not raw:
            return "skip", "no resolvable download URL"

    fn = expected_filename(row)
    if not fn:
        return "skip", "could not determine filename"

    dest = mirror_dir / fn
    if dest.is_file():
        fill_from_probe(row, dest)
        return "ok", f"already on disk ({dest.name})"

    raw_url = pick_download_url(row)
    if not raw_url:
        return "skip", "no download URL"

    try:
        url = resolve_if_needed(raw_url)
        if not url:
            return "fail", f"unresolved URL from {raw_url}"
        # file.html endpoints may still serve zip bodies
        download_url_to_file(url, dest)
        if not (row.get("download_url_mmm_canonical") or "").strip():
            row["download_url_mmm_canonical"] = url
        fill_from_probe(row, dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        if delay > 0:
            time.sleep(delay)
        return "ok", f"downloaded {size_mb:.1f} MiB <- {url}"
    except Exception as e:
        dest.unlink(missing_ok=True)
        return "fail", str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--catalog-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    only = {x.strip() for x in args.catalog_id if x.strip()}
    talkies = [
        r
        for r in rows
        if r.get("has_talkie", "").strip().lower() == "yes"
        and (not only or r["catalog_id"] in only)
    ]
    talkies.sort(key=lambda r: r["catalog_id"])

    print(f"Mirror: {args.mirror_dir}")
    print(f"Talkie rows: {len(talkies)}")

    ok = skip = fail = 0
    for i, row in enumerate(talkies, start=1):
        cid = row["catalog_id"]
        print(f"[{i}/{len(talkies)}] {cid} {row['title'][:50]}")
        if args.dry_run:
            fn = expected_filename(row)
            dest = args.mirror_dir / fn if fn else None
            exists = dest.is_file() if dest else False
            print(f"  dry-run: fn={fn or '?'} exists={exists}")
            continue

        status, detail = process_talkie(row, mirror_dir=args.mirror_dir, delay=args.delay)
        print(f"  {status}: {detail}")
        if status == "ok":
            write_catalog(args.csv, rows)
            ok += 1
        elif status == "skip":
            skip += 1
        else:
            fail += 1

    print(f"\nDone: {ok} ok, {skip} skipped, {fail} failed.")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
