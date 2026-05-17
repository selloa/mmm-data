#!/usr/bin/env python3
"""Scrape specials Komplettlösungen and fill walkthrough_* fields by title matching."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

from csv_to_catalog_json import CANONICAL_FIELDS
from scrape_walkthrough_content import fetch_parsed, read_catalog, write_catalog
from walkthrough_match import (
    fuzzy_match_catalog_id,
    parse_specials_label,
    structured_catalog_id,
)

LIST_URL = (
    "https://www.maniac-mansion-mania.com/index.php/de/spiele/komplettloesungen/specials.html"
)
LINK_RE = re.compile(
    r'href=["\']([^"\']*komplettloesungen/specials/([^"\']+\.html))["\'][^>]*>([^<]+)',
    re.IGNORECASE,
)
SKIP_EPISODE_CATEGORIES = frozenset({"MMM-Episoden", "Trash Episoden"})


def scrape_specials_links() -> list[tuple[str, str]]:
    session = requests.Session()
    session.headers["User-Agent"] = "mmm-data-scrape-specials-walkthroughs/1.0"
    resp = session.get(LIST_URL, timeout=60)
    resp.raise_for_status()
    out: list[tuple[str, str]] = []
    for href, _slug, label in LINK_RE.findall(resp.text):
        text = re.sub(r"\s+", " ", label).strip()
        if not text or "lösung" not in text.lower():
            continue
        out.append((text, urljoin(LIST_URL, href)))
    return out


def candidate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        r
        for r in rows
        if r["category"] not in SKIP_EPISODE_CATEGORIES
        and not r["catalog_id"].startswith("EP-")
        and not r["catalog_id"].startswith("TE-")
    ]


def match_links_to_catalog(
    links: list[tuple[str, str]],
    rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[str], list[str]]:
    """Returns catalog_id -> url, unmatched site labels, unmatched catalog ids."""
    by_id = {r["catalog_id"]: r for r in rows}
    cands = candidate_rows(rows)
    cand_titles = [(r["catalog_id"], r["title"]) for r in cands]
    url_by_id: dict[str, str] = {}
    unmatched_site: list[str] = []

    for label, url in links:
        hint = parse_specials_label(label)
        cid = structured_catalog_id(hint)
        if cid and cid in by_id:
            url_by_id[cid] = url
            continue
        if hint.get("kind") == "title":
            cid = fuzzy_match_catalog_id(hint.get("title", label), cand_titles)
            if cid:
                url_by_id[cid] = url
                continue
        unmatched_site.append(label)

    matched_ids = set(url_by_id)
    unmatched_catalog = [
        r["catalog_id"]
        for r in cands
        if r["catalog_id"] not in matched_ids
        and not (r.get("walkthrough_url_mmm") or "").strip()
    ]
    return url_by_id, unmatched_site, unmatched_catalog


def apply_specials(
    csv_path: Path,
    *,
    fetch_content: bool = True,
    save_every: int = 10,
    only_empty_url: bool = True,
    only_empty_body: bool = True,
) -> None:
    rows = read_catalog(csv_path)
    links = scrape_specials_links()
    print(f"scraped {len(links)} specials walkthrough links")

    url_by_id, unmatched_site, unmatched_catalog = match_links_to_catalog(links, rows)
    print(f"matched {len(url_by_id)} catalog rows to site links")

    url_updates = 0
    for row in rows:
        cid = row["catalog_id"]
        url = url_by_id.get(cid, "")
        if not url:
            continue
        if only_empty_url and (row.get("walkthrough_url_mmm") or "").strip():
            continue
        if row["walkthrough_url_mmm"].strip() != url:
            row["walkthrough_url_mmm"] = url
            url_updates += 1
    print(f"set walkthrough_url_mmm on {url_updates} rows")

    if unmatched_site:
        print("unmatched site entries:", file=sys.stderr)
        for label in unmatched_site:
            print(f"  - {label}", file=sys.stderr)

    if unmatched_catalog:
        print("catalog specials still without URL:", ", ".join(unmatched_catalog))

    if not fetch_content:
        write_catalog(csv_path, rows)
        return

    pending = [
        r
        for r in rows
        if (r.get("walkthrough_url_mmm") or "").strip()
        and r["catalog_id"] in url_by_id
        and (
            not only_empty_body
            or not (r.get("walkthrough_mmm_body") or "").strip()
        )
    ]
    total = len(pending)
    ok = 0
    failed: list[str] = []

    for i, row in enumerate(pending, start=1):
        cid = row["catalog_id"]
        url = row["walkthrough_url_mmm"].strip()
        print(f"[{i}/{total}] {cid} {row['title'][:50]}")
        try:
            author, date, body = fetch_parsed(url)
        except requests.RequestException as exc:
            print(f"  ! {exc}", file=sys.stderr)
            failed.append(cid)
            continue
        if not body:
            print("  ! no body", file=sys.stderr)
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
    print(f"content: {ok} ok, {len(failed)} failed")
    if failed:
        print("failed:", ", ".join(failed), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv",
    )
    parser.add_argument("--urls-only", action="store_true")
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--force-url", action="store_true")
    parser.add_argument("--force-body", action="store_true")
    args = parser.parse_args()

    apply_specials(
        args.csv,
        fetch_content=not args.urls_only,
        save_every=args.save_every,
        only_empty_url=not args.force_url,
        only_empty_body=not args.force_body,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
