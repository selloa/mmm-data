#!/usr/bin/env python3
"""Scrape talkie vs original download links from MMM staffel listing pages."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from scrape_walkthrough_content import read_catalog
from tag_talkies import fetch_sprachausgabe_page_paths, normalize_wiki_url

BASE = "https://www.maniac-mansion-mania.com/index.php/de/spiele/episoden/"
SITE_ROOT = "https://www.maniac-mansion-mania.com"
HEADERS = {"User-Agent": "mmm-data-scrape-staffel-talkie-links/1.0"}
ARTICLE_RE = re.compile(
    r'<article[^>]*class="uk-article"[^>]*>.*?</article>',
    re.DOTALL | re.IGNORECASE,
)
NAME_RE = re.compile(r'property="name" content="([^"]+)"', re.IGNORECASE)
EP_NUM_RE = re.compile(r"Episode\s+(\d+)\s*:", re.IGNORECASE)
DOWNLOAD_A_RE = re.compile(
    r'<a\b([^>]*?)href=["\']([^"\']*(?:doc_download|/file\.html)[^"\']*)["\']([^>]*?)>'
    r"(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
TALKIE_TAG_RE = re.compile(r"#Talkie\b", re.IGNORECASE)


@dataclass
class EpisodeLinks:
    catalog_id: str
    title: str
    staffel: int
    staffel_page: str
    original_docman: str = ""
    talkie_docman: str = ""
    original_canonical: str = ""
    talkie_canonical: str = ""
    original_filename: str = ""
    talkie_filename: str = ""
    has_talkie_tag: bool = False
    talkie_link_type: str = "none"  # separate | in_place_only | none
    catalog_docman: str = ""
    wiki_sprachausgabe: bool = False

    @property
    def has_talkie_on_site(self) -> bool:
        return bool(self.talkie_docman) or self.has_talkie_tag

    @property
    def catalog_matches_talkie(self) -> str:
        if not self.has_talkie_on_site:
            return "n/a"
        if self.talkie_docman:
            return "yes" if _urls_match(self.catalog_docman, self.talkie_docman) else "no"
        # in_place_only: catalog should point at the single on-site download
        target = self.original_docman
        return "yes" if _urls_match(self.catalog_docman, target) else "no"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_csv() -> Path:
    return repo_root() / "source" / "mmm_catalog.csv"


def default_out() -> Path:
    return repo_root() / "source" / "talkie_links_staffel_audit.txt"


def abs_url(href: str) -> str:
    href = unescape((href or "").strip()).replace("&amp;", "&")
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return SITE_ROOT + href


def _urls_match(a: str, b: str) -> bool:
    a, b = a.strip(), b.strip()
    if not a or not b:
        return False
    pa, pb = urlparse(a), urlparse(b)
    if (pa.hostname or "").lower() != (pb.hostname or "").lower():
        return False
    # Compare gid= for docman links when present
    ga = re.search(r"gid=(\d+)", a, re.I)
    gb = re.search(r"gid=(\d+)", b, re.I)
    if ga and gb:
        return ga.group(1) == gb.group(1)
    return a.rstrip("/").lower() == b.rstrip("/").lower()


def _link_label(inner_html: str) -> str:
    text = re.sub(r"<img[^>]*>", " ", inner_html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def extract_download_links(article_html: str) -> tuple[str, str]:
    original = ""
    talkie = ""
    for _pre, href, _post, inner in DOWNLOAD_A_RE.findall(article_html):
        url = abs_url(href)
        if not url:
            continue
        label = _link_label(inner)
        if re.search(r"talkie", label, re.I):
            if not talkie:
                talkie = url
        elif re.search(r"download", label, re.I) or not label:
            if not original:
                original = url
        elif not original:
            original = url
    return original, talkie


def article_has_talkie_tag(article_html: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", article_html)
    text = unescape(text)
    return bool(TALKIE_TAG_RE.search(text))


def classify_talkie_type(talkie_docman: str, has_tag: bool) -> str:
    if talkie_docman:
        return "separate"
    if has_tag:
        return "in_place_only"
    return "none"


def scrape_staffel(
    staffel: int,
    *,
    resolve: bool = False,
) -> dict[str, EpisodeLinks]:
    url = urljoin(BASE, f"staffel-{staffel}.html")
    resp = requests.get(url, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    html = resp.content.decode("utf-8")

    out: dict[str, EpisodeLinks] = {}
    for article in ARTICLE_RE.findall(html):
        name_m = NAME_RE.search(article)
        if not name_m:
            continue
        title = unescape(name_m.group(1)).strip()
        ep_m = EP_NUM_RE.search(title)
        if not ep_m:
            continue
        cid = f"EP-{int(ep_m.group(1)):03d}"
        original, talkie = extract_download_links(article)
        has_tag = article_has_talkie_tag(article)
        row = EpisodeLinks(
            catalog_id=cid,
            title=title,
            staffel=staffel,
            staffel_page=url,
            original_docman=original,
            talkie_docman=talkie,
            has_talkie_tag=has_tag,
            talkie_link_type=classify_talkie_type(talkie, has_tag),
        )
        if resolve:
            _resolve_row(row)
        out[cid] = row
    return out


def _resolve_row(row: EpisodeLinks) -> None:
    from resolve_downloads import filename_from_download_url, resolve

    if row.original_docman:
        row.original_canonical = resolve(row.original_docman, quiet=True)
        if row.original_canonical:
            row.original_filename = filename_from_download_url(row.original_canonical)
    if row.talkie_docman:
        row.talkie_canonical = resolve(row.talkie_docman, quiet=True)
        if row.talkie_canonical:
            row.talkie_filename = filename_from_download_url(row.talkie_canonical)


def load_catalog_episodes(csv_path: Path) -> dict[str, dict[str, str]]:
    rows = read_catalog(csv_path)
    return {r["catalog_id"]: r for r in rows if r["catalog_id"].startswith("EP-")}


def wiki_sprachausgabe_by_catalog(
    catalog_eps: dict[str, dict[str, str]],
) -> set[str]:
    wiki_paths = fetch_sprachausgabe_page_paths()
    matched: set[str] = set()
    for cid, row in catalog_eps.items():
        wiki = row.get("wiki_url_mmm", "").strip()
        if wiki and normalize_wiki_url(wiki) in wiki_paths:
            matched.add(cid)
    return matched


def enrich_from_catalog(
    episodes: dict[str, EpisodeLinks],
    catalog_eps: dict[str, dict[str, str]],
    wiki_eps: set[str],
) -> None:
    for cid, ep in episodes.items():
        row = catalog_eps.get(cid)
        if row:
            ep.catalog_docman = (row.get("download_url_mmm_docman") or "").strip()
        ep.wiki_sprachausgabe = cid in wiki_eps


def render_episode(ep: EpisodeLinks) -> str:
    lines = [
        f"### {ep.catalog_id} | {ep.title}",
        f"staffel_page: {ep.staffel_page}",
        f"has_talkie_on_site: {'yes' if ep.has_talkie_on_site else 'no'}",
        f"has_talkie_tag: {'yes' if ep.has_talkie_tag else 'no'}",
        f"talkie_link_type: {ep.talkie_link_type}",
        f"original_docman: {ep.original_docman or '(none)'}",
        f"talkie_docman: {ep.talkie_docman or '(none)'}",
    ]
    if ep.original_canonical or ep.talkie_canonical:
        lines.append(f"original_canonical: {ep.original_canonical or '(none)'}")
        lines.append(f"talkie_canonical: {ep.talkie_canonical or '(none)'}")
        lines.append(f"original_filename: {ep.original_filename or '(none)'}")
        lines.append(f"talkie_filename: {ep.talkie_filename or '(none)'}")
    lines.extend(
        [
            f"catalog_docman: {ep.catalog_docman or '(none)'}",
            f"catalog_matches_talkie: {ep.catalog_matches_talkie}",
            f"wiki_sprachausgabe: {'yes' if ep.wiki_sprachausgabe else 'no'}",
            "",
        ]
    )
    return "\n".join(lines)


def render_summaries(episodes: dict[str, EpisodeLinks]) -> str:
    by_id = dict(sorted(episodes.items()))
    talkies = [ep for ep in by_id.values() if ep.has_talkie_on_site]
    mismatches = [ep for ep in by_id.values() if ep.catalog_matches_talkie == "no"]
    wiki_only = [
        ep
        for ep in by_id.values()
        if ep.wiki_sprachausgabe and not ep.has_talkie_on_site
    ]
    site_only = [
        ep
        for ep in by_id.values()
        if ep.has_talkie_on_site and not ep.wiki_sprachausgabe
    ]

    def bullet_list(eps: list[EpisodeLinks]) -> str:
        if not eps:
            return "  (none)\n"
        return "".join(
            f"  - {ep.catalog_id}: {ep.title} [{ep.talkie_link_type}]\n" for ep in eps
        )

    return (
        "\n"
        + "=" * 72
        + "\n\n"
        + "# SUMMARY\n\n"
        + f"## Talkies on staffel pages ({len(talkies)})\n"
        + bullet_list(talkies)
        + f"\n## Catalog mismatches — catalog_docman != talkie link ({len(mismatches)})\n"
        + bullet_list(mismatches)
        + f"\n## Wiki Sprachausgabe but no talkie on staffel page ({len(wiki_only)})\n"
        + bullet_list(wiki_only)
        + f"\n## Talkie on staffel page but not in Wiki Sprachausgabe ({len(site_only)})\n"
        + bullet_list(site_only)
        + "\n"
    )


def render_audit(
    episodes: dict[str, EpisodeLinks],
    staffeln: list[int],
) -> str:
    by_staffel: dict[int, list[EpisodeLinks]] = {n: [] for n in staffeln}
    for ep in episodes.values():
        by_staffel.setdefault(ep.staffel, []).append(ep)
    for lst in by_staffel.values():
        lst.sort(key=lambda e: e.catalog_id)

    header = (
        "# Talkie links from MMM staffel overview pages\n"
        f"# Generated: {date.today().isoformat()}\n"
        f"# Source: {BASE}staffel-{{N}}.html (staffeln {staffeln[0]}–{staffeln[-1]})\n"
        "\n"
    )
    body_parts: list[str] = []
    for n in staffeln:
        body_parts.append(f"## Staffel {n}\n")
        eps = by_staffel.get(n, [])
        if not eps:
            body_parts.append("(no episodes parsed)\n")
        else:
            for ep in eps:
                body_parts.append(render_episode(ep))
        body_parts.append("")
    return header + "\n".join(body_parts) + render_summaries(episodes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=default_csv())
    parser.add_argument("--out", type=Path, default=default_out())
    parser.add_argument("--from", type=int, dest="staffel_from", default=1, metavar="N")
    parser.add_argument("--to", type=int, dest="staffel_to", default=11, metavar="N")
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="resolve docman URLs to canonical/filename (HTTP, slow)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print audit to stdout instead of writing --out",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    staffeln = list(range(args.staffel_from, args.staffel_to + 1))
    episodes: dict[str, EpisodeLinks] = {}
    for n in staffeln:
        batch = scrape_staffel(n, resolve=args.resolve)
        print(f"staffel {n}: {len(batch)} episodes", file=sys.stderr)
        for cid, ep in batch.items():
            if cid in episodes:
                print(f"  warning: duplicate {cid} on staffel {n}", file=sys.stderr)
                continue
            episodes[cid] = ep

    catalog_eps = load_catalog_episodes(args.csv)
    wiki_eps = wiki_sprachausgabe_by_catalog(catalog_eps)
    enrich_from_catalog(episodes, catalog_eps, wiki_eps)

    text = render_audit(episodes, staffeln)
    if args.dry_run:
        print(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {args.out} ({len(episodes)} episodes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
