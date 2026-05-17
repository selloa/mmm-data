#!/usr/bin/env python3
"""Download missing release packages from the catalog into a local mirror folder."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from csv_to_catalog_json import CANONICAL_FIELDS
from resolve_downloads import (
    HEADERS,
    TIMEOUT,
    filename_from_content_disposition,
    resolve,
    session,
)

DEFAULT_MIRROR = Path(r"C:\mmm\mmm-local\mmm-mirror-poc-7k3xq-zips")
SKIP_BASENAMES = frozenset({"readme.md", "origin.txt"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def read_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing header")
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in reader]


def mirror_index(mirror_dir: Path) -> set[str]:
    names: set[str] = set()
    if not mirror_dir.is_dir():
        return names
    for path in mirror_dir.rglob("*"):
        if path.is_file() and path.name.lower() not in SKIP_BASENAMES:
            names.add(path.name.lower())
    return names


def pick_download_url(row: dict[str, str]) -> str:
    for key in (
        "download_url_mmm_canonical",
        "mirror_url_dropbox_public",
        "download_url_mmm_docman",
    ):
        url = (row.get(key) or "").strip()
        if url:
            return url
    return ""


def download_url_to_file(url: str, dest: Path, *, retries: int = 3) -> None:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True) as r:
                r.raise_for_status()
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "text/html" in ctype:
                    raise ValueError(f"unexpected HTML response from {url}")
                cd_name = filename_from_content_disposition(
                    r.headers.get("Content-Disposition")
                )
                if cd_name and cd_name.lower() != dest.name.lower():
                    # Keep catalog filename; log mismatch only on stderr.
                    print(
                        f"  note: Content-Disposition filename {cd_name!r} "
                        f"!= {dest.name!r}",
                        file=sys.stderr,
                    )
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as out:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            out.write(chunk)
                if tmp.stat().st_size == 0:
                    tmp.unlink(missing_ok=True)
                    raise ValueError("downloaded file is empty")
                tmp.replace(dest)
                return
        except (requests.RequestException, OSError, ValueError) as e:
            last_err = e
            dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(1.5 * attempt)
    assert last_err is not None
    raise last_err


def resolve_if_needed(url: str) -> str:
    path = unquote(urlparse(url).path or "")
    basename = path.rsplit("/", 1)[-1].lower()
    if basename in {"file.html", "file.htm"} or "doc_download" in url.lower():
        resolved = resolve(url, quiet=True)
        if resolved:
            return resolved
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Seconds between downloads (default: 0.4)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max downloads this run (0 = all missing)",
    )
    parser.add_argument(
        "--catalog-id",
        action="append",
        default=[],
        help="Only download these catalog_id values (repeatable)",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    on_disk = mirror_index(args.mirror_dir)
    only_ids = {x.strip() for x in args.catalog_id if x.strip()}

    pending: list[dict[str, str]] = []
    for row in rows:
        fn = (row.get("release_package_filename") or "").strip()
        if not fn:
            continue
        if only_ids and row["catalog_id"] not in only_ids:
            continue
        if fn.lower() in on_disk:
            continue
        pending.append(row)

    if args.limit > 0:
        pending = pending[: args.limit]

    total = len(pending)
    if total == 0:
        print("Nothing to download.")
        return 0

    print(f"Mirror: {args.mirror_dir}")
    print(f"Pending downloads: {total}")
    ok = 0
    failed: list[str] = []

    for i, row in enumerate(pending, start=1):
        cid = row["catalog_id"]
        fn = row["release_package_filename"].strip()
        dest = args.mirror_dir / fn
        raw_url = pick_download_url(row)
        print(f"[{i}/{total}] {cid} {fn}")
        if not raw_url:
            print("  ! no download URL in catalog", file=sys.stderr)
            failed.append(cid)
            continue
        try:
            url = resolve_if_needed(raw_url)
            download_url_to_file(url, dest)
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  ok ({size_mb:.1f} MiB) <- {url}")
            ok += 1
            on_disk.add(fn.lower())
        except Exception as e:
            print(f"  ! failed: {e}", file=sys.stderr)
            failed.append(cid)
        if i < total and args.delay > 0:
            time.sleep(args.delay)

    print(f"\nDone: {ok} downloaded, {len(failed)} failed.")
    if failed:
        print("Failed:", ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
