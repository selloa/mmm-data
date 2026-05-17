#!/usr/bin/env python3
"""Scrape MMM episode Komplettlösung URLs into source/mmm_catalog.csv (walkthrough_url_mmm)."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

from csv_to_catalog_json import CANONICAL_FIELDS

LIST_PAGES = [
    "https://www.maniac-mansion-mania.com/index.php/de/spiele/komplettloesungen/episoden/",
    "https://www.maniac-mansion-mania.com/index.php/de/spiele/komplettloesungen/episoden/?limitstart=50",
]
SKIP_SLUGS = ("1100-loesung-1-100",)
EP_RE = re.compile(r"Episode\s+(\d+)\b", re.IGNORECASE)
LINK_RE = re.compile(
    r'href=["\']([^"\']*komplettloesungen/episoden/([^"\']+\.html))["\'][^>]*>([^<]+)',
    re.IGNORECASE,
)


def scrape_walkthroughs() -> dict[int, str]:
    session = requests.Session()
    session.headers["User-Agent"] = "mmm-data-scrape-walkthroughs/1.0"
    by_ep: dict[int, str] = {}

    for page_url in LIST_PAGES:
        resp = session.get(page_url, timeout=60)
        resp.raise_for_status()
        for href, slug, label in LINK_RE.findall(resp.text):
            if any(skip in slug for skip in SKIP_SLUGS):
                continue
            if "alle l" in label.lower() and "1 bis 100" in label.lower():
                continue
            m = EP_RE.search(label)
            if not m:
                continue
            ep_num = int(m.group(1))
            url = urljoin(page_url, href)
            by_ep[ep_num] = url

    return by_ep


def update_catalog(csv_path: Path, by_ep: dict[int, str], *, dry_run: bool) -> tuple[int, list[int]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = [{k: (r.get(k) or "") for k in CANONICAL_FIELDS} for r in csv.DictReader(f)]

    updated = 0
    missing_on_site: list[int] = []

    catalog_eps = sorted(
        int(r["catalog_id"].split("-")[1])
        for r in rows
        if r["category"] == "MMM-Episoden" and r["catalog_id"].startswith("EP-")
    )

    for row in rows:
        if row["category"] != "MMM-Episoden" or not row["catalog_id"].startswith("EP-"):
            continue
        ep_num = int(row["catalog_id"].split("-")[1])
        url = by_ep.get(ep_num, "")
        if not url:
            missing_on_site.append(ep_num)
            continue
        if row["walkthrough_url_mmm"].strip() != url:
            row["walkthrough_url_mmm"] = url
            updated += 1

    if not dry_run:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS, lineterminator="\r\n")
            w.writeheader()
            w.writerows(rows)

    site_only = sorted(set(by_ep) - set(catalog_eps))
    if site_only:
        print("on site, not in catalog:", site_only, file=sys.stderr)

    return updated, missing_on_site


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    by_ep = scrape_walkthroughs()
    print(f"scraped {len(by_ep)} episode walkthrough links from site")
    updated, missing = update_catalog(args.csv, by_ep, dry_run=args.dry_run)
    print(f"{'would update' if args.dry_run else 'updated'} {updated} catalog rows")
    if missing:
        print(f"no site link for catalog episodes: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
