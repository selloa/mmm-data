#!/usr/bin/env python3
"""Scrape author, date, and body from MMM Komplettlösung pages into mmm_catalog.csv."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

from csv_to_catalog_json import CANONICAL_FIELDS

TIMEOUT = 60
HEADERS = {"User-Agent": "mmm-data-scrape-walkthrough-content/1.0"}
BODY_END = '<ul class="uk-list">'
AUTHOR_META_RE = re.compile(
    r'<meta\s+property="author"[^>]*content="([^"]*)"',
    re.IGNORECASE,
)
AUTHOR_TEXT_RE = re.compile(r"Geschrieben von\s+([^.<]+)", re.IGNORECASE)
DATE_TIME_RE = re.compile(
    r'Erstellt am\s*<time\s+datetime="([^"]+)"',
    re.IGNORECASE,
)
DATE_PUBLISHED_RE = re.compile(
    r'<meta\s+property="datePublished"\s+content="([^"]*)"',
    re.IGNORECASE,
)
BODY_START_RE = re.compile(r'property="text"\s*>', re.IGNORECASE)

session = requests.Session()
session.headers.update(HEADERS)
cache: dict[str, tuple[str, str, str]] = {}


def _html_fragment_to_text(fragment: str) -> str:
    text = re.sub(r"(<br\s*/?>\s*){2,}", "\n\n", fragment, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    paragraphs = [" ".join(ln.strip() for ln in p.splitlines() if ln.strip()) for p in text.split("\n\n")]
    return "\n\n".join(p for p in paragraphs if p).strip()


def _normalize_date(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return raw


def parse_walkthrough_page(html: str) -> tuple[str, str, str]:
    author = ""
    m = AUTHOR_META_RE.search(html)
    if m:
        author = m.group(1).strip()
    if not author:
        m = AUTHOR_TEXT_RE.search(html)
        if m:
            author = m.group(1).strip().rstrip(".")

    date = ""
    m = DATE_TIME_RE.search(html)
    if m:
        date = _normalize_date(m.group(1))
    if not date:
        m = DATE_PUBLISHED_RE.search(html)
        if m:
            date = _normalize_date(m.group(1))

    body = ""
    start_m = BODY_START_RE.search(html)
    if start_m:
        start = start_m.end()
        end = html.find(BODY_END, start)
        if end == -1:
            end = html.find("</article>", start)
        if end != -1:
            body = _html_fragment_to_text(html[start:end])

    return author, date, body


def fetch_parsed(url: str) -> tuple[str, str, str]:
    if url in cache:
        return cache[url]
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    parsed = parse_walkthrough_page(resp.text)
    cache[url] = parsed
    time.sleep(0.25)
    return parsed


def read_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in csv.DictReader(f)]


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CANONICAL_FIELDS,
            lineterminator="\r\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)


def scrape_catalog(
    csv_path: Path,
    *,
    save_every: int = 10,
    only_empty: bool = True,
) -> tuple[int, int, list[str]]:
    rows = read_catalog(csv_path)
    pending = [
        r
        for r in rows
        if (r.get("walkthrough_url_mmm") or "").strip()
        and (
            not only_empty
            or not (r.get("walkthrough_mmm_body") or "").strip()
        )
    ]
    total = len(pending)
    ok = 0
    failed: list[str] = []

    for i, row in enumerate(pending, start=1):
        cid = row["catalog_id"]
        url = row["walkthrough_url_mmm"].strip()
        print(f"[{i}/{total}] {cid}")
        try:
            author, date, body = fetch_parsed(url)
        except requests.RequestException as exc:
            print(f"  ! {exc}", file=sys.stderr)
            failed.append(cid)
            continue
        if not body:
            print("  ! no body parsed", file=sys.stderr)
            failed.append(cid)
            continue
        row["walkthrough_mmm_author"] = author
        row["walkthrough_mmm_date"] = date
        row["walkthrough_mmm_body"] = body
        ok += 1
        print(f"  author={author!r} date={date!r} body_len={len(body)}")

        if save_every and i % save_every == 0:
            write_catalog(csv_path, rows)
            print(f"--- saved ({i}/{total}) ---")

    write_catalog(csv_path, rows)
    return ok, len(failed), failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv",
    )
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape even when walkthrough_mmm_body is already set",
    )
    args = parser.parse_args()

    ok, n_fail, failed = scrape_catalog(
        args.csv,
        save_every=args.save_every,
        only_empty=not args.force,
    )
    print(f"Done: {ok} scraped, {n_fail} failed.")
    if failed:
        print("Failed:", ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
