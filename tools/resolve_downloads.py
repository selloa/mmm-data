"""
Resolve Joomla DOCman / doc_download links to direct file URLs.

For ``source/mmm_catalog.csv``: fills ``download_url_mmm_canonical`` when
``download_url_mmm_docman`` is set and canonical is empty.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests

from csv_to_catalog_json import CANONICAL_FIELDS

TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (resolve-script)"}

session = requests.Session()
session.headers.update(HEADERS)

cache: dict[str, str] = {}
_head_filename_cache: dict[str, str] = {}

_CD_FILENAME_RE = re.compile(
    r'filename\*=(?:UTF-8\'\')?([^;\s]+)|filename="([^"]+)"|filename=([^;\s]+)',
    re.IGNORECASE,
)
_HTML_DOWNLOAD_BASENAMES = frozenset({"file.html", "file.htm"})


def filename_from_content_disposition(value: str | None) -> str:
    """Parse filename from a Content-Disposition header value."""
    if not value:
        return ""
    m = _CD_FILENAME_RE.search(value)
    if not m:
        return ""
    name = next(g for g in m.groups() if g)
    return unquote(name.strip().strip('"'))


def filename_from_download_url(url: str) -> str:
    """
    Derive the release archive filename from a download URL.

    Uses the URL path basename, except for Joomla ``file.html`` endpoints that
    serve a zip/rar/etc. body — those need a HEAD request and Content-Disposition.
    """
    url = url.strip()
    if not url:
        return ""
    path = unquote(urlparse(url).path or "")
    basename = path.rsplit("/", 1)[-1]
    if basename.lower() not in _HTML_DOWNLOAD_BASENAMES:
        return basename
    if url in _head_filename_cache:
        return _head_filename_cache[url]
    name = ""
    try:
        r = session.head(url, allow_redirects=True, timeout=TIMEOUT)
        name = filename_from_content_disposition(r.headers.get("Content-Disposition"))
    except requests.RequestException as e:
        print(f"  ! HEAD failed for {url}: {e}", file=sys.stderr)
    _head_filename_cache[url] = name
    time.sleep(0.1)
    return name


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv_path() -> Path:
    return _repo_root() / "source" / "mmm_catalog.csv"


def _is_docman_url(url: str) -> bool:
    u = url.strip().lower()
    return bool(u) and ("docman" in u or "doc_download" in u)


def extract_doc_download(html: str, base_url: str) -> str:
    m = re.search(r'href=["\']([^"\']*doc_download[^"\']*)["\']', html, re.IGNORECASE)
    if not m:
        return ""
    href = unescape(m.group(1))
    return urljoin(base_url, href)


def fetch(url: str) -> tuple[str, str, str]:
    """GET with redirects. Returns (final_url, content_type, body_or_empty)."""
    r = session.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
    ctype = r.headers.get("Content-Type", "").lower()
    body = ""
    if "text/html" in ctype or "text/xml" in ctype:
        body = r.text
    r.close()
    return r.url, ctype, body


def try_url(url: str) -> str:
    """Fetch URL; return final URL when the response is not HTML."""
    try:
        final_url, ctype, body = fetch(url)
    except requests.RequestException as e:
        print(f"  ! request failed: {e}", file=sys.stderr)
        return ""
    if "text/html" not in ctype:
        return final_url
    doc_url = extract_doc_download(body, final_url)
    if doc_url:
        try:
            doc_final, doc_ctype, _ = fetch(doc_url)
            if "text/html" not in doc_ctype:
                return doc_final
        except requests.RequestException as e:
            print(f"  ! doc fetch failed: {e}", file=sys.stderr)
    return ""


def resolve(url: str, *, quiet: bool = False) -> str:
    url = url.strip()
    if not url:
        return ""
    if url in cache:
        return cache[url]

    if not quiet:
        print(f"-> {url}")
    final = try_url(url)

    if not final and url.endswith(".html") and "/file.html" not in url:
        alt = url[: -len(".html")] + "/file.html"
        if not quiet:
            print(f"   fallback: {alt}")
        final = try_url(alt)

    if final and "doc_download" in final:
        final = ""

    cache[url] = final
    if not quiet:
        print(f"   => {final or '(unresolved)'}")
    time.sleep(0.3)
    return final


def read_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing header")
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in reader]


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def resolve_catalog(csv_path: Path, *, save_every: int = 10) -> tuple[int, int, list[str]]:
    """Resolve missing canonical URLs. Returns (resolved_count, failed_count, failed_ids)."""
    rows = read_catalog(csv_path)
    pending = [
        r
        for r in rows
        if _is_docman_url(r.get("download_url_mmm_docman", ""))
        and not r.get("download_url_mmm_canonical", "").strip()
    ]
    total = len(pending)
    resolved = 0
    failed: list[str] = []

    for i, row in enumerate(pending, start=1):
        cid = row["catalog_id"]
        docman = row["download_url_mmm_docman"].strip()
        print(f"[{i}/{total}] {cid} {row['title'][:60]}")
        canonical = resolve(docman)
        if canonical:
            row["download_url_mmm_canonical"] = canonical
            resolved += 1
        else:
            failed.append(cid)

        if save_every and i % save_every == 0:
            write_catalog(csv_path, rows)
            print(f"--- saved progress ({i}/{total}) ---")

    write_catalog(csv_path, rows)
    return resolved, len(failed), failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve DOCman links in mmm_catalog.csv")
    parser.add_argument(
        "--csv",
        type=Path,
        default=_default_csv_path(),
        help="Catalog CSV path (default: source/mmm_catalog.csv)",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Write CSV after this many resolutions (0 = only at end)",
    )
    args = parser.parse_args()
    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    resolved, failed_count, failed_ids = resolve_catalog(args.csv, save_every=args.save_every)
    print(f"Done: {resolved} resolved, {failed_count} failed.")
    if failed_ids:
        print("Failed:", ", ".join(failed_ids), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
