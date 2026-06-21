#!/usr/bin/env python3
"""Match catalog entries to existing wiki articles from the Episoden page."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from urllib.parse import unquote

WIKI_BASE = "http://wiki.maniac-mansion-mania.de"
REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "source" / "mmm_catalog.csv"

# Categories where wiki links should only be added for existing (blue) articles.
SKIP_RED_LINK_CATEGORIES = {"Fan-Games", "Fan-Movies"}


def parse_existing_wiki_links(content: str) -> dict[str, str]:
    """Return label/slug -> full wiki URL for blue links only (not redlinks)."""
    existing: dict[str, str] = {}

    def add(label: str, slug: str) -> None:
        slug = slug.strip()
        if not slug or "redlink=1" in slug.lower():
            return
        url = f"{WIKI_BASE}/wiki/{slug}"
        label = label.strip()
        if label:
            existing[label] = url
        existing[unquote(slug.replace("_", " "))] = url

    for match in re.finditer(
        r"\[([^\]]+)\]\(/wiki/([^)\s\"]+)(?:\s+\"[^\"]*\")?\)", content
    ):
        add(match.group(1), match.group(2))

    for match in re.finditer(
        r'<a\b[^>]*\bhref="(?:https?://wiki\.maniac-mansion-mania\.de)?/wiki/([^"#?]+)"[^>]*>'
        r"(?:[^<]*<[^/]|.)*?"
        r"(?:title=\"([^\"]+)\"[^>]*)?>"
        r"([^<]*)</a>",
        content,
        re.I | re.S,
    ):
        slug, title_attr, link_text = match.group(1), match.group(2), match.group(3)
        label = (title_attr or link_text or "").strip()
        if label:
            add(label, slug)

    # Simpler fallback for typical MediaWiki anchors without nested tags.
    for match in re.finditer(
        r'<a\b[^>]*\bhref="(?:https?://wiki\.maniac-mansion-mania\.de)?/wiki/([^"#?]+)"'
        r'[^>]*\btitle="([^"]+)"',
        content,
        re.I,
    ):
        add(match.group(2), match.group(1))

    for match in re.finditer(
        r'<a\b[^>]*\bhref="(?:https?://wiki\.maniac-mansion-mania\.de)?/wiki/([^"#?]+)"'
        r'[^>]*>([^<]+)</a>',
        content,
        re.I,
    ):
        add(match.group(2), match.group(1))

    return existing


def title_candidates(title: str) -> list[str]:
    normalized = re.sub(r"\[UNRELEASED\]\s*", "", title, flags=re.I).strip()
    candidates = [title.strip(), normalized]
    if ": " in normalized:
        candidates.append(normalized.split(": ", 1)[-1].strip())
    if " - " in normalized:
        candidates.append(normalized.split(" - ", 1)[-1].strip())
    # Strip common catalog prefixes like "Episode 051: ", "#12: "
    for pattern in (
        r"^Episode\s+\d+:\s*(.+)$",
        r"^Raum\s+\d+:\s*(.+)$",
        r"^MMMMM\s+\d+:\s*(.+)$",
        r"^Halloween\s+[\d-]+:\s*(.+)$",
        r"^#\d+:\s*(.+)$",
    ):
        m = re.match(pattern, normalized, re.I)
        if m:
            candidates.append(m.group(1).strip())
    # Wiki often appends "(unreleased)" to unreleased Meteorhead entries.
    for candidate in list(candidates):
        candidates.append(f"{candidate} (unreleased)")
    return list(dict.fromkeys(candidates))


def find_wiki_url(title: str, existing: dict[str, str]) -> str | None:
    for candidate in title_candidates(title):
        if candidate in existing:
            return existing[candidate]
        cn = candidate.lower()
        for key, url in existing.items():
            if key.lower() == cn:
                return url
    return None


def main() -> int:
    dry_run = "--apply" not in sys.argv

    wiki_md_path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    if wiki_md_path is None:
        import urllib.request

        with urllib.request.urlopen(f"{WIKI_BASE}/wiki/Episoden") as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Convert rough HTML links to markdown-like patterns for parser
        markdown = html
    else:
        markdown = wiki_md_path.read_text(encoding="utf-8")

    existing = parse_existing_wiki_links(markdown)

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [fn for fn in reader.fieldnames if fn]
        rows = list(reader)

    updates: list[tuple[str, str, str, str]] = []
    still_missing: list[tuple[str, str, str]] = []

    for row in rows:
        wiki = row.get("wiki_url_mmm", "").strip()
        if wiki:
            continue

        cid = row["catalog_id"]
        cat = row["category"]
        title = row["title"]
        url = find_wiki_url(title, existing)

        if url:
            updates.append((cid, cat, title, url))
            row["wiki_url_mmm"] = url
        else:
            still_missing.append((cid, cat, title))

    print(f"Existing wiki articles parsed: {len(existing)}")
    print(f"Catalog rows: {len(rows)}")
    print(f"Updates to apply: {len(updates)}")
    print(f"Still missing (no existing article): {len(still_missing)}")
    print()

    if updates:
        print("=== UPDATES ===")
        for cid, cat, title, url in updates:
            print(f"{cid}\t{cat}\t{title}")
            print(f"  -> {url}")

    if still_missing:
        print("\n=== STILL MISSING (correctly left empty) ===")
        for cid, cat, title in still_missing:
            print(f"{cid}\t{cat}\t{title}")

    if not dry_run and updates:
        fieldnames = [fn for fn in fieldnames if fn]
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        print(f"\nWrote {len(updates)} updates to {CSV_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
