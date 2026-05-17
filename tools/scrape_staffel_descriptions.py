#!/usr/bin/env python3
"""Scrape episode synopsis text from MMM staffel listing pages into mmm_description."""

from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests

from scrape_walkthrough_content import read_catalog, write_catalog

BASE = "https://www.maniac-mansion-mania.com/index.php/de/spiele/episoden/"
HEADERS = {"User-Agent": "mmm-data-scrape-staffel-descriptions/1.0"}
ARTICLE_RE = re.compile(
    r'<article[^>]*class="uk-article"[^>]*>.*?</article>',
    re.DOTALL | re.IGNORECASE,
)
NAME_RE = re.compile(r'property="name" content="([^"]+)"', re.IGNORECASE)
EP_NUM_RE = re.compile(r"Episode\s+(\d+)\s*:", re.IGNORECASE)
# Trailing download / walkthrough links in listing blurbs
TAIL_RE = re.compile(
    r"\s*Komplettl(?:ö|oe)sung\s*[-–—].*$",
    re.IGNORECASE | re.DOTALL,
)
DOWNLOAD_TAIL_RE = re.compile(
    r"\s*(?:Archive\s*)?(?:DOWNLOAD|Download)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
LOESUNG_TAIL_RE = re.compile(
    r"\s*L(?:ö|oe)sung\s*[-–—].*$",
    re.IGNORECASE | re.DOTALL,
)
FORUM_TAIL_RE = re.compile(r"\s*FORUM\s*.*$", re.IGNORECASE | re.DOTALL)
TAGS_TAIL_RE = re.compile(r"\s*#\w[\w, #]*\s*$", re.DOTALL)


def html_to_synopsis(html_fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html_fragment, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()
    text = TAIL_RE.sub("", text).strip()
    text = LOESUNG_TAIL_RE.sub("", text).strip()
    text = DOWNLOAD_TAIL_RE.sub("", text).strip()
    text = FORUM_TAIL_RE.sub("", text).strip()
    text = TAGS_TAIL_RE.sub("", text).strip()
    return text


def extract_text_block(article_html: str) -> str:
    m = re.search(r'property="text">(.*)', article_html, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    chunk = m.group(1)
    # Stop before Joomla article footer / readmore area
    chunk = re.split(
        r'<p class="uk-margin[^"]*readmore|</article>',
        chunk,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return html_to_synopsis(chunk)


def scrape_staffel(staffel: int) -> dict[str, str]:
    url = urljoin(BASE, f"staffel-{staffel}.html")
    resp = requests.get(url, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    html = resp.content.decode("utf-8")

    out: dict[str, str] = {}
    for article in ARTICLE_RE.findall(html):
        name_m = NAME_RE.search(article)
        if not name_m:
            continue
        ep_m = EP_NUM_RE.search(name_m.group(1))
        if not ep_m:
            continue
        n = int(ep_m.group(1))
        cid = f"EP-{n:03d}"
        body = extract_text_block(article)
        if body:
            out[cid] = body
    return out


def apply_descriptions(
    csv_path: Path,
    descriptions: dict[str, str],
    *,
    only_empty: bool = True,
) -> int:
    rows = read_catalog(csv_path)
    updated = 0
    for row in rows:
        cid = row["catalog_id"]
        desc = descriptions.get(cid, "")
        if not desc:
            continue
        if only_empty and (row.get("mmm_description") or "").strip():
            continue
        if row.get("mmm_description", "").strip() != desc:
            row["mmm_description"] = desc
            updated += 1
    write_catalog(csv_path, rows)
    return updated


def scrape_staffeln(staffeln: list[int]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for n in staffeln:
        batch = scrape_staffel(n)
        print(f"staffel {n}: {len(batch)} descriptions")
        for cid, desc in batch.items():
            if cid in merged and merged[cid] != desc:
                print(
                    f"  warning: {cid} duplicate on staffel {n}, keeping first",
                    file=sys.stderr,
                )
                continue
            merged[cid] = desc
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv",
    )
    parser.add_argument(
        "--staffel",
        type=int,
        action="append",
        dest="staffeln",
        help="season number (repeatable)",
    )
    parser.add_argument(
        "--from",
        type=int,
        dest="staffel_from",
        default=1,
        metavar="N",
        help="first staffel when using --to (default: 1)",
    )
    parser.add_argument(
        "--to",
        type=int,
        dest="staffel_to",
        default=11,
        metavar="N",
        help="last staffel inclusive when no --staffel given (default: 11)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing mmm_description values",
    )
    args = parser.parse_args()

    if args.staffeln:
        staffeln = sorted(set(args.staffeln))
    else:
        staffeln = list(range(args.staffel_from, args.staffel_to + 1))

    descriptions = scrape_staffeln(staffeln)
    print(f"total scraped: {len(descriptions)} episode descriptions")

    updated = apply_descriptions(
        args.csv, descriptions, only_empty=not args.force
    )
    print(f"updated mmm_description on {updated} catalog rows")

    catalog_ids = {r["catalog_id"] for r in read_catalog(args.csv)}
    ep_in_catalog = sorted(cid for cid in descriptions if cid in catalog_ids)
    not_in_catalog = sorted(set(descriptions) - catalog_ids)
    if not_in_catalog:
        print("scraped but not in catalog:", ", ".join(not_in_catalog), file=sys.stderr)

    eps_without = sorted(
        cid
        for cid in catalog_ids
        if cid.startswith("EP-") and cid not in descriptions
    )
    if eps_without:
        print(
            f"catalog EP rows still without site description ({len(eps_without)}):",
            ", ".join(eps_without),
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
