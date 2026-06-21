#!/usr/bin/env python3
"""Set has_talkie=yes from wiki Sprachausgabe + staffel talkie audit (union)."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from csv_to_catalog_json import CANONICAL_FIELDS

WIKI_API = "http://wiki.maniac-mansion-mania.de/api.php"
WIKI_CATEGORY = "Kategorie:Sprachausgabe"
# Wiki category slugs that do not match catalog wiki_url_mmm
WIKI_SLUG_TO_CATALOG: dict[str, str] = {
    "ronmastered_collection": "CO-001",
    "(r)ausgefallen": "MD-023",
}
STAFFEL_SECTION_RE = re.compile(r"^### ([A-Z]{2,3}-\d{3}) \|")
TIMEOUT = 30


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def default_staffel_audit() -> Path:
    return repo_root() / "source" / "talkie_links_staffel_audit.txt"


def normalize_wiki_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    p = urlparse(url)
    path = p.path or ""
    while "%" in path:
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    path = path.rstrip("/")
    if "/wiki/" in path:
        path = path[path.index("/wiki/") :]
    return path.lower()


def parse_staffel_audit_talkie_ids(path: Path) -> set[str]:
    return set(parse_staffel_audit_talkie_links(path))


def parse_staffel_audit_talkie_links(path: Path) -> dict[str, str]:
    """Map catalog_id -> preferred talkie download URL from staffel audit."""
    if not path.is_file():
        return {}
    links: dict[str, str] = {}
    current_id: str | None = None
    talkie_docman = ""
    original_docman = ""
    has_talkie = False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = STAFFEL_SECTION_RE.match(line)
        if m:
            if current_id and has_talkie:
                url = talkie_docman if talkie_docman and talkie_docman != "(none)" else original_docman
                if url and url != "(none)":
                    links[current_id] = url
            current_id = m.group(1)
            talkie_docman = ""
            original_docman = ""
            has_talkie = False
            continue
        if not current_id:
            continue
        stripped = line.strip()
        if stripped == "has_talkie_on_site: yes":
            has_talkie = True
        elif stripped.startswith("talkie_docman:"):
            talkie_docman = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("original_docman:"):
            original_docman = stripped.split(":", 1)[1].strip()
    if current_id and has_talkie:
        url = talkie_docman if talkie_docman and talkie_docman != "(none)" else original_docman
        if url and url != "(none)":
            links[current_id] = url
    return links


def wiki_slug(path: str) -> str:
    if "/wiki/" not in path:
        return path.lower()
    return path.rsplit("/wiki/", 1)[-1].lower()


def fetch_sprachausgabe_page_paths() -> set[str]:
    paths: set[str] = set()
    cmcontinue: str | None = None
    while True:
        params: dict[str, str] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": WIKI_CATEGORY,
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        r = requests.get(WIKI_API, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for member in data.get("query", {}).get("categorymembers", []):
            title = member.get("title", "")
            if title:
                paths.add(normalize_wiki_url(f"/wiki/{title.replace(' ', '_')}"))
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    return paths


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


def collect_talkie_ids(
    rows: list[dict[str, str]],
    wiki_paths: set[str],
    staffel_ids: set[str],
) -> dict[str, list[str]]:
    """Union of staffel scrape talkies and wiki Sprachausgabe category members."""
    reasons: dict[str, list[str]] = {cid: [] for cid in staffel_ids}
    for cid in staffel_ids:
        reasons[cid].append("staffel:audit")

    wiki_ids: set[str] = set()
    for row in rows:
        wiki = row.get("wiki_url_mmm", "").strip()
        if wiki and normalize_wiki_url(wiki) in wiki_paths:
            wiki_ids.add(row["catalog_id"])

    for path in wiki_paths:
        slug = wiki_slug(path)
        if slug in WIKI_SLUG_TO_CATALOG:
            wiki_ids.add(WIKI_SLUG_TO_CATALOG[slug])

    for cid in wiki_ids:
        reasons.setdefault(cid, []).append("wiki:Sprachausgabe")

    return reasons


def apply_talkie_tags(
    rows: list[dict[str, str]], reasons: dict[str, list[str]]
) -> None:
    talkie_ids = set(reasons)
    for row in rows:
        cid = row["catalog_id"]
        if cid in talkie_ids:
            row["has_talkie"] = "yes"
        else:
            row["has_talkie"] = ""


def tag_rows(
    rows: list[dict[str, str]], staffel_audit: Path
) -> tuple[dict[str, list[str]], int, int]:
    wiki_paths = fetch_sprachausgabe_page_paths()
    staffel_ids = parse_staffel_audit_talkie_ids(staffel_audit)
    reasons = collect_talkie_ids(rows, wiki_paths, staffel_ids)
    apply_talkie_tags(rows, reasons)
    return reasons, len(wiki_paths), len(staffel_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument(
        "--staffel-audit",
        type=Path,
        default=default_staffel_audit(),
        help="talkie_links_staffel_audit.txt from scrape_staffel_talkie_links.py",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="print matches only")
    group.add_argument("--apply", action="store_true", help="write CSV")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    rows = read_catalog(args.csv)
    reasons, wiki_count, staffel_count = tag_rows(rows, args.staffel_audit)

    print(f"Wiki category members: {wiki_count}")
    print(f"Staffel audit talkies: {staffel_count}")
    print(f"Tagged {len(reasons)} row(s) with has_talkie=yes:")
    for cid in sorted(reasons):
        print(f"  {cid}: {', '.join(reasons[cid])}")

    if args.apply:
        write_catalog(args.csv, rows)
        print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
