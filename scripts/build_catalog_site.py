#!/usr/bin/env python3
"""Build a static HTML catalog page from mmm_catalog.csv."""

import csv
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from site_chrome import (
    header_nav_css,
    render_header_nav,
    theme_toggle_css,
    theme_toggle_html,
    theme_toggle_script,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_CSV = SCRIPT_DIR.parent / "source" / "mmm_catalog.csv"
FAVICON_SRC = SCRIPT_DIR.parent / "assets" / "favicon-catalog.png"
OUTPUT_DIR = SCRIPT_DIR.parent / "site"
OUTPUT_HTML = OUTPUT_DIR / "index.html"
BIRTHDAYS_HTML = OUTPUT_DIR / "birthdays.html"
BIRTHDAYS_JSON = OUTPUT_DIR / "birthdays-catalog.json"

CATEGORY_ORDER = [
    "MMM Remastered",
    "Collections",
    "MMM Origins",
    "MMM Episoden",
    "Mini Masterpieces",
    "Halloween Specials",
    "Christmas Specials",
    "Easter Specials",
    "Hollywood Special",
    "Edgar Award Shows",
    "Maniac Dungeon",
    "Meteorhead Series",
    "Trash Episoden",
    "Fan Games",
    "Fan-Games",
    "Fan Movies",
    "Trailer & Demos",
]

EPISODES_PER_SEASON = 10

CATEGORY_LABELS = {
    "MMM Remastered": "MMM Remastered",
    "Collections": "Sammlungen",
    "MMM Origins": "MMM Origins",
    "MMM Episoden": "MMM Episoden",
    "Halloween Specials": "Halloween Specials",
    "Christmas Specials": "Weihnachts-Specials",
    "Easter Specials": "Oster-Specials",
    "Edgar Award Shows": "Edgar Award Shows",
    "Mini Masterpieces": "Mini Masterpieces",
    "Hollywood Special": "Hollywood Special",
    "Maniac Dungeon": "Maniac Dungeon",
    "Meteorhead Series": "Meteorhead Series",
    "Trash Episoden": "Trash-Episoden",
    "Fan Games": "Fan-Games",
    "Fan-Games": "Fan-Games",
    "Fan Movies": "Fan-Filme",
    "Trailer & Demos": "Trailer & Demos",
}

CATEGORY_MERGE = {"Fan-Games": "Fan Games"}
EXCLUDED_BIRTHDAY_CATEGORIES = {"Fan Games", "Fan Movies", "Trailer & Demos"}
UNVERIFIED_PREFIX = re.compile(r"^\(unverified\)\s*", re.IGNORECASE)
DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
DATE_YEAR = re.compile(r"^(\d{4})")

CATEGORY_ANCHOR = {
    "MMM Remastered": "mmm-remastered",
    "Collections": "sammlungen",
    "MMM Origins": "origins",
    "MMM Episoden": "episoden",
    "Halloween Specials": "halloween",
    "Christmas Specials": "weihnachten",
    "Easter Specials": "ostern",
    "Edgar Award Shows": "edgar",
    "Mini Masterpieces": "mini",
    "Hollywood Special": "hollywood",
    "Maniac Dungeon": "dungeon",
    "Meteorhead Series": "meteorhead",
    "Trash Episoden": "trash",
    "Fan Games": "fangames",
    "Fan Movies": "fanfilme",
    "Trailer & Demos": "trailer",
}


def load_catalog():
    rows = []
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("catalog_id", "").strip():
                continue
            cat = row["category"].strip()
            cat = CATEGORY_MERGE.get(cat, cat)
            row["category"] = cat
            rows.append(row)
    return rows


def group_by_category(rows):
    groups = {}
    for row in rows:
        cat = row["category"]
        groups.setdefault(cat, []).append(row)
    ordered = []
    seen = set()
    for cat in CATEGORY_ORDER:
        key = CATEGORY_MERGE.get(cat, cat)
        if key in seen:
            continue
        seen.add(key)
        if key in groups:
            ordered.append((key, groups[key]))
    for cat, items in groups.items():
        if cat not in seen:
            ordered.append((cat, items))
    return ordered


def esc(text):
    return html.escape(text or "", quote=True)


def truncate(text, length=100):
    text = (text or "").strip()
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "\u2026"


def extra_text_languages(raw: str) -> str | None:
    """Return comma-separated non-German codes, or None if nothing to show."""
    codes = [c.strip() for c in (raw or "").split(",") if c.strip()]
    extra = [c for c in codes if c.upper() != "GER"]
    return ", ".join(extra) if extra else None


def build_link_slots(row):
    """Return a list of 5 HTML strings (one per slot), empty string if no link."""
    slots = []

    _t = ' target="_blank" rel="noopener"'

    wiki = row.get("wiki_url_mmm", "").strip()
    slots.append(f'<a href="{esc(wiki)}" title="Wiki" class="icon-link"{_t}>Wiki</a>' if wiki else "")

    yt = row.get("youtube_longplay_url", "").strip()
    dur = row.get("youtube_longplay_duration", "").strip()
    if yt:
        label = f"YouTube ({dur})" if dur else "YouTube"
        if dur:
            inner = f'YouTube <span class="yt-duration">({esc(dur)})</span>'
        else:
            inner = "YouTube"
        slots.append(f'<a href="{esc(yt)}" title="{esc(label)}" class="icon-link icon-yt"{_t}>{inner}</a>')
    else:
        slots.append("")

    wt = row.get("walkthrough_url_mmm", "").strip()
    slots.append(f'<a href="{esc(wt)}" title="Komplettlösung" class="icon-link"{_t}>Lösung</a>' if wt else "")

    forum = row.get("forum_thread_url_mmm", "").strip()
    slots.append(f'<a href="{esc(forum)}" title="Forum-Thread" class="icon-link"{_t}>Forum</a>' if forum else "")

    dl = row.get("download_url_mmm_docman", "").strip()
    if not dl:
        dl = row.get("download_url_mmm_canonical", "").strip()
    slots.append(f'<a href="{esc(dl)}" title="Download" class="icon-link icon-dl" target="_blank" rel="noopener">Download</a>' if dl else "")

    return slots


def render_entry_row(row):
    title = esc(row.get("title", ""))
    wiki = row.get("wiki_url_mmm", "").strip()
    date = esc(row.get("release_date", "").strip())
    authors = esc(row.get("authors", "").strip())
    desc = truncate(row.get("mmm_description", ""))

    title_html = f'<a href="{esc(wiki)}" target="_blank" rel="noopener">{title}</a>' if wiki else title

    if row.get("has_talkie", "").strip().lower() == "yes":
        title_html += ' <span class="talkie-badge" title="Sprachausgabe">Talkie</span>'

    extra = extra_text_languages(row.get("text_languages_mmm", ""))
    if extra:
        tip = esc(f"Textsprachen: {extra}")
        title_html += f' <span class="lang-hint" title="{tip}" aria-label="{tip}">i18n</span>'

    slots = build_link_slots(row)
    slot_cells = "".join(
        f'<span class="link-slot">{s}</span>' for s in slots
    )
    links_html = f'<span class="link-grid">{slot_cells}</span>'

    desc_html = f'<span class="entry-desc">{esc(desc)}</span>' if desc else ""

    parts = []
    parts.append('<tr class="entry-row">')
    parts.append(f'<td class="col-title">{title_html}')
    if desc_html:
        parts.append(f'<br>{desc_html}')
    parts.append("</td>")
    parts.append(f'<td class="col-author">{authors}</td>')
    parts.append(f'<td class="col-date">{date}</td>')
    parts.append(f'<td class="col-links">{links_html}</td>')
    parts.append("</tr>")
    return "\n".join(parts)


def render_table(items):
    rows_html = "\n".join(render_entry_row(r) for r in items)
    return f"""<table class="cat-table">
    <thead>
      <tr>
        <th>Titel</th>
        <th>Autor(en)</th>
        <th>Datum</th>
        <th>Links</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>"""


def episode_number(row):
    cid = row.get("catalog_id", "")
    if cid.startswith("EP-"):
        try:
            return int(cid[3:])
        except ValueError:
            pass
    return 0


def group_into_seasons(items):
    seasons = {}
    for row in items:
        ep = episode_number(row)
        if ep > 0:
            s = ((ep - 1) // EPISODES_PER_SEASON) + 1
        else:
            s = 0
        seasons.setdefault(s, []).append(row)
    return sorted(seasons.items(), reverse=True)


def render_season_details(season_num, items, open_by_default=False):
    label = f"Staffel {season_num}"
    count = len(items)
    open_attr = " open" if open_by_default else ""

    table_html = render_table(items)
    return f"""  <details class="sub-details"{open_attr}>
  <summary>{esc(label)} <span>({count})</span></summary>
{table_html}
  </details>"""


def render_episoden_section(items):
    anchor = CATEGORY_ANCHOR["MMM Episoden"]
    count = len(items)
    seasons = group_into_seasons(items)

    season_blocks = []
    for season_num, season_items in seasons:
        if season_num == 0:
            continue
        is_first = season_num == 1
        season_blocks.append(render_season_details(season_num, season_items, open_by_default=False))

    inner = "\n".join(season_blocks)

    return f"""<section class="category" id="{esc(anchor)}">
  <details open>
  <summary>MMM Episoden <span>({count})</span></summary>
{inner}
  </details>
</section>"""


def render_category_section(cat, items, open_by_default=False):
    if cat == "MMM Episoden":
        return render_episoden_section(items)

    label = CATEGORY_LABELS.get(cat, cat)
    anchor = CATEGORY_ANCHOR.get(cat, cat.lower().replace(" ", "-"))
    count = len(items)
    open_attr = " open" if open_by_default else ""

    table_html = render_table(items)

    return f"""<section class="category" id="{esc(anchor)}">
  <details{open_attr}>
  <summary>{esc(label)} <span>({count})</span></summary>
{table_html}
  </details>
</section>"""


def render_toc(groups):
    items = []
    for cat, entries in groups:
        label = CATEGORY_LABELS.get(cat, cat)
        anchor = CATEGORY_ANCHOR.get(cat, cat.lower().replace(" ", "-"))
        count = len(entries)
        items.append(f'    <li><a href="#{esc(anchor)}">{esc(label)}</a> <span class="count">({count})</span></li>')
    return "\n".join(items)


def parse_release_date(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text or text.lower() in ("null", "none", "n/a"):
        return None
    unverified = False
    if UNVERIFIED_PREFIX.match(text):
        unverified = True
        text = UNVERIFIED_PREFIX.sub("", text).strip()
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    m = DATE_ISO.match(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return {"year": year, "month": month, "day": day, "precision": "day", "unverified": unverified}
    m = DATE_YEAR.match(text)
    if m:
        return {"year": int(m.group(1)), "precision": "year", "unverified": unverified}
    return None


def build_birthday_catalog(rows):
    result = []
    for row in rows:
        cat = row.get("category", "")
        if cat in EXCLUDED_BIRTHDAY_CATEGORIES:
            continue
        parsed = parse_release_date(row.get("release_date", ""))
        if not parsed:
            continue
        download = (row.get("download_url_mmm_docman", "") or "").strip()
        if not download:
            download = (row.get("download_url_mmm_canonical", "") or "").strip()
        result.append(
            {
                "catalog_id": row.get("catalog_id", "").strip(),
                "category": cat,
                "title": row.get("title", "").strip(),
                "release_date": row.get("release_date", "").strip(),
                "authors": row.get("authors", "").strip() or None,
                "parsed": parsed,
                "wiki_url_mmm": (row.get("wiki_url_mmm", "") or "").strip() or None,
                "download_url": download or None,
                "has_talkie": (row.get("has_talkie", "") or "").strip().lower() == "yes",
            }
        )
    return result


def build_html(groups):
    total = sum(len(items) for _, items in groups)
    toc_html = render_toc(groups)

    sections = []
    for i, (cat, items) in enumerate(groups):
        open_default = cat in ("Sammlungen", "MMM Episoden")
        sections.append(render_category_section(cat, items, open_by_default=open_default))

    sections_html = "\n\n".join(sections)

    site_nav = render_header_nav("catalog")

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="favicon.png">
<title>Maniac Mansion Mania \u2013 Katalog</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&family=Cabin+Sketch:wght@700&family=Roboto+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #f2f3ee;
    --card: #fff;
    --card-border: rgba(96, 147, 76, 0.25);
    --accent: #4a7a3a;
    --accent-dim: rgba(96, 147, 76, 0.18);
    --highlight: #4a7a3a;
    --text: #3a3a3a;
    --text-bright: #1a1a1a;
    --muted: #808080;
    --link: #3d6e30;
    --link-hover: #2a5520;
    --border-subtle: rgba(0,0,0,.07);
    --icon-bg: rgba(96, 147, 76, 0.06);
    --icon-border: rgba(96, 147, 76, 0.2);
  }}
  html.dark {{
    --bg: #374037;
    --card: rgba(34, 32, 30, 0.9);
    --card-border: rgba(96, 147, 76, 0.15);
    --accent: #60934c;
    --accent-dim: rgba(96, 147, 76, 0.3);
    --highlight: #60934c;
    --text: rgba(255, 255, 255, 0.7);
    --text-bright: #fff;
    --muted: rgba(255, 255, 255, 0.4);
    --link: #60934c;
    --link-hover: #8cbf72;
    --border-subtle: rgba(255,255,255,.04);
    --icon-bg: rgba(255,255,255,0.05);
    --icon-border: rgba(255,255,255,0.08);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Roboto Mono', monospace;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem 1rem;
    font-size: 14px;
  }}
  h1 {{
    text-align: center;
    font-family: 'Cabin Sketch', cursive;
    font-size: 2.2rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: .2rem;
    color: var(--text-bright);
    letter-spacing: 1px;
  }}
  .subtitle {{
    text-align: center;
    font-family: 'Amatic SC', cursive;
    color: var(--muted);
    margin-bottom: 2rem;
    font-size: 1.4rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
  }}
  .page-header {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
  }}
  .header-nav {{
    text-align: center;
    margin-bottom: .6rem;
    font-size: .72rem;
  }}
  .header-nav a {{
    color: var(--muted);
    text-decoration: none;
    letter-spacing: .3px;
  }}
  .header-nav a:hover {{
    color: var(--text);
    text-decoration: underline;
  }}
  .header-nav .nav-sep {{
    color: var(--muted);
    margin: 0 .35rem;
  }}
{header_nav_css()}
  .intro {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
    padding: 0 .2rem;
    font-size: .8rem;
    color: var(--muted);
    line-height: 1.7;
    text-align: center;
  }}
  .search-wrap {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
  }}
  #search {{
    width: 100%;
    padding: .6rem 1rem;
    font-family: 'Roboto Mono', monospace;
    font-size: .85rem;
    border: 1px solid var(--accent-dim);
    border-radius: 4px;
    background: var(--card);
    color: var(--text);
    outline: none;
    transition: border-color .2s;
  }}
  #search:focus {{ border-color: var(--accent); }}
  #search::placeholder {{ color: var(--muted); }}
  .search-hint {{
    margin-top: .45rem;
    font-size: .72rem;
    color: var(--muted);
    text-align: center;
    line-height: 1.5;
  }}
  .toc {{
    display: none; /* TODO: temporarily hidden */
    max-width: 1100px;
    margin: 0 auto 2.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: 1.2rem 1.5rem;
  }}
  .toc h2 {{
    font-family: 'Cabin Sketch', cursive;
    font-size: 1.1rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: .6rem;
    color: var(--text-bright);
  }}
  .toc ul {{ list-style: none; columns: 2; gap: 1rem; }}
  .toc li {{ margin-bottom: .35rem; }}
  .toc a {{ color: var(--link); text-decoration: none; font-size: .85rem; }}
  .toc a:hover {{ color: var(--link-hover); text-decoration: underline; }}
  .toc .count {{ color: var(--muted); font-size: .75rem; margin-left: .3rem; }}
  .category {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: 1.2rem 1.5rem;
  }}
  details summary {{
    cursor: pointer;
    font-family: 'Cabin Sketch', cursive;
    font-size: 1.15rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-bright);
    border-bottom: 1px solid var(--accent-dim);
    padding-bottom: .4rem;
    margin-bottom: .8rem;
    list-style: none;
  }}
  details summary::-webkit-details-marker {{ display: none; }}
  details summary::before {{
    content: '\\25B6';
    display: inline-block;
    margin-right: .5rem;
    font-size: .65rem;
    color: var(--accent);
    transition: transform .2s;
  }}
  details[open] > summary::before {{ transform: rotate(90deg); }}
  details summary span {{
    font-family: 'Roboto Mono', monospace;
    font-size: .75rem;
    color: var(--muted);
    font-weight: normal;
    text-transform: none;
  }}
  .sub-details {{
    margin-top: .6rem;
    border-top: 1px solid var(--border-subtle);
    padding-top: .5rem;
  }}
  .sub-details summary {{
    font-size: .95rem;
    color: var(--muted);
    border-bottom: none;
    padding-bottom: 0;
    margin-bottom: .5rem;
  }}
  .sub-details summary::before {{
    font-size: .55rem;
  }}
  .sub-details[open] > summary {{
    color: var(--text-bright);
  }}
  .cat-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .82rem;
  }}
  .cat-table thead th {{
    text-align: left;
    font-size: .7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .5px;
    padding: .3rem .4rem;
    border-bottom: 1px solid var(--accent-dim);
    font-weight: 500;
    white-space: nowrap;
  }}
  .cat-table tbody tr {{
    border-bottom: 1px solid var(--border-subtle);
  }}
  .cat-table tbody tr:last-child {{ border-bottom: none; }}
  .cat-table td {{
    padding: .45rem .4rem;
    vertical-align: top;
  }}
  .col-title {{ width: 40%; }}
  .col-title a {{
    color: var(--link);
    text-decoration: none;
  }}
  .col-title a:hover {{ color: var(--link-hover); text-decoration: underline; }}
  .talkie-badge {{
    display: inline-block;
    margin-left: .35rem;
    padding: .05rem .35rem;
    font-size: .58rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: .3px;
    vertical-align: middle;
    color: var(--accent);
    background: rgba(96, 147, 76, 0.15);
    border: 1px solid var(--accent-dim);
    border-radius: 3px;
    line-height: 1.4;
  }}
  .lang-hint {{
    display: inline-block;
    margin-left: .35rem;
    font-size: .58rem;
    font-weight: 500;
    letter-spacing: .2px;
    vertical-align: middle;
    color: var(--muted);
    cursor: help;
    user-select: none;
    line-height: 1.4;
  }}
  .entry-desc {{
    display: block;
    font-size: .72rem;
    color: var(--muted);
    line-height: 1.5;
    margin-top: .15rem;
  }}
  .col-author {{
    color: var(--text);
    font-size: .72rem;
    max-width: 9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .col-date {{
    color: var(--muted);
    font-size: .72rem;
    white-space: nowrap;
  }}
  .col-links {{
    white-space: nowrap;
    font-size: 0;
    vertical-align: middle;
  }}
  .link-grid {{
    display: inline-grid;
    grid-template-columns: 3.2rem 7.75rem 3.8rem 3.6rem 5.2rem;
    gap: .2rem;
    align-items: center;
  }}
  .link-slot {{
    display: flex;
    justify-content: center;
    min-height: 1.2rem;
  }}
  .link-slot:nth-child(2) {{
    justify-content: stretch;
  }}
  .icon-link {{
    display: inline-block;
    font-size: .6rem;
    padding: .15rem .35rem;
    border-radius: 3px;
    margin-right: .25rem;
    margin-bottom: .15rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: .3px;
    text-decoration: none;
    background: var(--icon-bg);
    color: var(--muted);
    border: 1px solid var(--icon-border);
    transition: color .15s, border-color .15s;
  }}
  .icon-link:hover {{
    color: var(--link-hover);
    border-color: var(--accent-dim);
  }}
  .icon-yt {{
    display: inline-flex;
    justify-content: center;
    align-items: center;
    gap: .15rem;
    width: 100%;
    box-sizing: border-box;
    white-space: nowrap;
    background: rgba(96, 147, 76, 0.12);
    color: var(--accent);
    border-color: var(--accent-dim);
  }}
  .yt-duration {{
    display: inline-block;
    min-width: 3.6em;
    font-family: 'Roboto Mono', monospace;
    font-variant-numeric: tabular-nums;
    text-transform: none;
    letter-spacing: 0;
  }}
  .icon-dl {{
    background: rgba(96, 147, 76, 0.2);
    color: var(--accent);
    border-color: var(--accent-dim);
  }}
  .back-top {{
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    background: var(--accent);
    color: #fff;
    padding: .5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-family: 'Roboto Mono', monospace;
    font-size: .75rem;
    font-weight: 500;
    opacity: 0;
    pointer-events: none;
    transition: opacity .3s;
    z-index: 100;
  }}
  .back-top.visible {{ opacity: 1; pointer-events: auto; }}
  .back-top:hover {{ background: var(--link-hover); }}
{theme_toggle_css()}
  footer {{
    max-width: 1100px;
    margin: 3rem auto 1rem;
    padding: 1.2rem 1.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    color: var(--muted);
    font-size: .75rem;
    line-height: 1.7;
  }}
  footer strong {{ color: var(--text-bright); }}
  footer a {{ color: var(--link); }}
  footer a:hover {{ color: var(--link-hover); }}
  .stats {{
    max-width: 1100px;
    margin: 0 auto .8rem;
    font-size: .72rem;
    color: var(--muted);
    text-align: center;
  }}
  @media (max-width: 700px) {{
    .toc ul {{ columns: 1; }}
    body {{ padding: 1rem .5rem; }}
    h1 {{ font-size: 1.6rem; }}
    .subtitle {{ font-size: 1.1rem; }}
    .cat-table {{ font-size: .75rem; }}
    .col-author, .col-date {{ display: none; }}
    .col-title {{ width: 70%; }}
  }}
  #google_translate_element select {{
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: .3rem .5rem;
    font-family: 'Roboto Mono', monospace;
    font-size: .8rem;
  }}
  .goog-te-gadget {{ font-size: 0 !important; color: transparent !important; }}
  .goog-te-gadget select {{ font-size: .8rem !important; }}
  .goog-te-gadget a {{ display: none !important; }}
</style>
<script>
(function(){{var s=localStorage.getItem('theme');if(s==='dark')document.documentElement.classList.add('dark');}})();
</script>
</head>
<body>

{theme_toggle_html()}

<div id="google_translate_element" style="margin-bottom:.5rem; opacity:.6; font-size:.75rem;"></div>

<header class="page-header">
  {site_nav}
  <h1>Katalog</h1>
  <p class="subtitle">Alle Episoden und Specials auf einen Blick</p>
</header>

<p class="intro">
  Der komplette Katalog aller Maniac Mansion Mania Episoden, Specials, Fan-Games und mehr \u2013
  mit Links zu Wiki, Komplettl\u00f6sungen, YouTube-Longplays und Downloads.
</p>

<p class="stats">{total} Eintr\u00e4ge in {len(groups)} Kategorien</p>

<div class="search-wrap">
  <input type="text" id="search" autofocus aria-label="Katalog live filtern" placeholder="Sofort filtern \u2013 z.B. \u2026">
  <p class="search-hint">Filtert sofort alle {total} Eintr\u00e4ge \u2013 Titel, Autor, Datum und mehr. Kein Seitenwechsel.</p>
</div>

<nav class="toc">
  <h2>Kategorien</h2>
  <ul>
{toc_html}
  </ul>
</nav>

{sections_html}

<footer>
  <p><strong>Quellen</strong></p>
  <ul style="list-style:none;margin:.4rem 0 .8rem;">
    <li>MMM Webseite \u2013 Spiele (<a href="https://www.maniac-mansion-mania.com/index.php/de/spiele.html">Link</a>)</li>
    <li>MMM Wiki (<a href="http://wiki.maniac-mansion-mania.de">Link</a>)</li>
    <li>MMM Forum (<a href="https://www.maniac-mansion-mania.de/forum/">Link</a>)</li>
  </ul>
  <p>
    <a href="https://www.maniac-mansion-mania.com">maniac-mansion-mania.com</a>
  </p>
  <p style="margin-top:.6rem;">selloa \u2013 2026</p>
</footer>

<a href="#" class="back-top" id="backTop">&#9650; Nach oben</a>

{theme_toggle_script()}
<script>
(function() {{
  var search = document.getElementById('search');
  var sections = document.querySelectorAll('.category');

  var placeholderExamples = ['LucasFan', 'Halloween', 'Episode 042', 'Geschwisterliebe', 'Bernard', 'Fan-Games'];
  var placeholderPrefix = 'Sofort filtern \u2013 z.B. ';
  var placeholderFocused = 'Sofort filtern\u2026';
  var placeholderIndex = 0;
  var placeholderTimer = null;

  function setRotatingPlaceholder() {{
    search.placeholder = placeholderPrefix + placeholderExamples[placeholderIndex];
    placeholderIndex = (placeholderIndex + 1) % placeholderExamples.length;
  }}

  function startPlaceholderRotation() {{
    if (placeholderTimer) return;
    setRotatingPlaceholder();
    placeholderTimer = setInterval(setRotatingPlaceholder, 3000);
  }}

  function stopPlaceholderRotation() {{
    if (placeholderTimer) {{
      clearInterval(placeholderTimer);
      placeholderTimer = null;
    }}
  }}

  search.addEventListener('focus', function() {{
    stopPlaceholderRotation();
    if (!this.value) this.placeholder = placeholderFocused;
  }});

  search.addEventListener('blur', function() {{
    if (!this.value) startPlaceholderRotation();
  }});

  if (document.activeElement === search) {{
    if (!search.value) search.placeholder = placeholderFocused;
  }} else if (!search.value) {{
    startPlaceholderRotation();
  }}

  search.addEventListener('input', function() {{
    var q = this.value.toLowerCase().trim();
    sections.forEach(function(sec) {{
      var rows = sec.querySelectorAll('.entry-row');
      var anyVisible = false;
      rows.forEach(function(tr) {{
        var match = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
        tr.style.display = match ? '' : 'none';
        if (match) anyVisible = true;
      }});
      sec.querySelectorAll('.sub-details').forEach(function(sd) {{
        var subRows = sd.querySelectorAll('.entry-row');
        var subVisible = false;
        subRows.forEach(function(tr) {{
          if (tr.style.display !== 'none') subVisible = true;
        }});
        sd.style.display = subVisible || !q ? '' : 'none';
        if (q && subVisible) sd.open = true;
      }});
      sec.style.display = anyVisible || !q ? '' : 'none';
      if (q && anyVisible) {{
        sec.querySelector('details').open = true;
      }}
    }});
  }});

  var btn = document.getElementById('backTop');
  window.addEventListener('scroll', function() {{
    btn.classList.toggle('visible', window.scrollY > 400);
  }});
}})();
</script>

<script>
function googleTranslateElementInit() {{
  new google.translate.TranslateElement(
    {{ pageLanguage: 'de', includedLanguages: 'en,fr,it,de,es', layout: google.translate.TranslateElement.InlineLayout.HORIZONTAL }},
    'google_translate_element'
  );
}}
</script>
<script src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>

</body>
</html>"""


def build_birthdays_html():
    labels_json = json.dumps(
        {k: v for k, v in CATEGORY_LABELS.items() if k not in EXCLUDED_BIRTHDAY_CATEGORIES},
        ensure_ascii=False,
    )
    site_nav = render_header_nav("birthdays")
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="favicon.png">
<title>MMM Geburtstage</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&family=Cabin+Sketch:wght@700&family=Roboto+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #f2f3ee;
    --card: #fff;
    --card-border: rgba(96, 147, 76, 0.25);
    --accent: #4a7a3a;
    --accent-dim: rgba(96, 147, 76, 0.18);
    --text: #3a3a3a;
    --text-bright: #1a1a1a;
    --muted: #808080;
    --link: #3d6e30;
    --link-hover: #2a5520;
    --border-subtle: rgba(0,0,0,.07);
    --round5: #5a8f4a;
    --round10: #c9a227;
    --round10-bg: rgba(201, 162, 39, 0.15);
  }}
  html.dark {{
    --bg: #374037;
    --card: rgba(34, 32, 30, 0.9);
    --card-border: rgba(96, 147, 76, 0.15);
    --accent: #60934c;
    --accent-dim: rgba(96, 147, 76, 0.3);
    --text: rgba(255, 255, 255, 0.7);
    --text-bright: #fff;
    --muted: rgba(255, 255, 255, 0.4);
    --link: #60934c;
    --link-hover: #8cbf72;
    --border-subtle: rgba(255,255,255,.04);
    --round5: #8cbf72;
    --round10: #e8c547;
    --round10-bg: rgba(232, 197, 71, 0.18);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Roboto Mono', monospace; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem 1rem 3rem; font-size: 14px; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  .page-header {{ margin-bottom: 1.5rem; }}
  .header-nav {{
    text-align: center;
    margin-bottom: .6rem;
    font-size: .72rem;
  }}
  .header-nav a {{
    color: var(--muted);
    text-decoration: none;
    letter-spacing: .3px;
  }}
  .header-nav a:hover {{
    color: var(--text);
    text-decoration: underline;
  }}
{header_nav_css()}
  h1 {{ text-align: center; font-family: 'Cabin Sketch', cursive; font-size: 2.2rem; font-weight: 700; text-transform: uppercase; color: var(--text-bright); letter-spacing: 1px; }}
  .subtitle {{ text-align: center; font-family: 'Amatic SC', cursive; color: var(--muted); margin: .3rem 0 1rem; font-size: 1.4rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }}
  .header-meta {{ text-align: center; font-size: .8rem; color: var(--muted); margin-bottom: 1.5rem; }}
{theme_toggle_css()}
  .section {{ background: var(--card); border: 1px solid var(--card-border); border-radius: 4px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem; }}
  .section h2 {{ font-family: 'Cabin Sketch', cursive; font-size: 1.15rem; font-weight: 700; text-transform: uppercase; color: var(--text-bright); border-bottom: 1px solid var(--accent-dim); padding-bottom: .4rem; margin-bottom: 1rem; }}
  .section-empty {{ color: var(--muted); font-size: .85rem; font-style: italic; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
  .card {{ border: 1px solid var(--border-subtle); border-radius: 4px; padding: 1rem; background: var(--bg); }}
  .card.round5 {{ border-color: var(--round5); }}
  .card.round10 {{ border-color: var(--round10); background: var(--round10-bg); }}
  .card-title {{ font-weight: 500; color: var(--text-bright); margin-bottom: .35rem; font-size: .9rem; }}
  .card-title a {{ color: var(--link); text-decoration: none; }}
  .card-title a:hover {{ color: var(--link-hover); text-decoration: underline; }}
  .card-meta {{ font-size: .75rem; color: var(--muted); margin-bottom: .5rem; }}
  .badge-row {{ display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .5rem; }}
  .badge {{ display: inline-block; font-size: .7rem; padding: .15rem .45rem; border-radius: 3px; background: var(--accent-dim); color: var(--accent); font-weight: 500; }}
  .badge.round5 {{ background: rgba(90, 143, 74, 0.2); color: var(--round5); }}
  .badge.round10 {{ background: var(--round10-bg); color: var(--round10); font-weight: 700; }}
  .badge.unverified {{ background: rgba(128,128,128,.15); color: var(--muted); }}
  .badge.talkie {{ background: rgba(96,147,76,.12); color: var(--accent); }}
  .card-links a {{ color: var(--link); text-decoration: none; margin-right: .8rem; font-size: .75rem; }}
  .card-links a:hover {{ color: var(--link-hover); text-decoration: underline; }}
  .list-item {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem 1rem; padding: .65rem 0; border-bottom: 1px solid var(--border-subtle); font-size: .82rem; }}
  .list-item:last-child {{ border-bottom: none; }}
  .list-date {{ min-width: 5.5rem; color: var(--muted); font-size: .75rem; }}
  .list-countdown {{ min-width: 6rem; color: var(--accent); font-size: .75rem; }}
  .list-title {{ flex: 1; color: var(--text-bright); }}
  .list-title a {{ color: var(--link); text-decoration: none; }}
  .list-title a:hover {{ text-decoration: underline; }}
  .list-meta {{ color: var(--muted); font-size: .75rem; }}
  .footer-note {{ text-align: center; font-size: .72rem; color: var(--muted); margin-top: 2rem; line-height: 1.7; }}
  .loading {{ text-align: center; color: var(--muted); padding: 3rem; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
{theme_toggle_html()}
<div class="wrap">
  <header class="page-header">
    {site_nav}
    <h1>MMM Geburtstage</h1>
    <p class="subtitle">Release-Jubil&auml;en</p>
    <p class="header-meta"><span id="currentDate"></span></p>
  </header>
  <div id="loading" class="loading">Katalog wird geladen&hellip;</div>
  <div id="content" class="hidden">
    <section class="section"><h2>Heute</h2><div id="today-content"></div></section>
    <section class="section"><h2>Demn&auml;chst (30 Tage)</h2><div id="upcoming-content"></div></section>
    <section class="section"><h2>Dieser Monat</h2><div id="month-content"></div></section>
    <section class="section" id="sec-year-only"><h2>Jubil&auml;umsjahr (genauer Tag unbekannt)</h2><div id="year-only-content"></div></section>
  </div>
  <p class="footer-note">Release-Daten stammen aus dem MMM-Katalog und werden laufend korrigiert.<br>Neu bauen mit <code>python scripts/build_catalog_site.py</code></p>
</div>
{theme_toggle_script()}
<script>
(function() {{
  var CATEGORY_LABELS = {labels_json};
  function startOfDay(d) {{ return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }}
  function daysBetween(a, b) {{ return Math.round((startOfDay(b) - startOfDay(a)) / 86400000); }}
  function formatDateDE(d) {{ return d.toLocaleDateString('de-DE', {{ weekday:'long', day:'numeric', month:'long', year:'numeric' }}); }}
  function formatShortDE(d) {{ return d.toLocaleDateString('de-DE', {{ day:'2-digit', month:'2-digit' }}); }}
  function computeAge(parsed, ref) {{ var age = ref.getFullYear() - parsed.year; if (parsed.precision === 'day') {{ var b = new Date(ref.getFullYear(), parsed.month - 1, parsed.day); if (startOfDay(ref) < startOfDay(b)) age--; }} return age; }}
  function nextOccurrence(parsed, from) {{ var y = from.getFullYear(); var o = new Date(y, parsed.month - 1, parsed.day); if (startOfDay(o) < startOfDay(from)) o = new Date(y + 1, parsed.month - 1, parsed.day); return o; }}
  function sortKey(e) {{ var p=e.parsed; var ep=0; if(e.catalog_id.indexOf('EP-')===0) ep=parseInt(e.catalog_id.slice(3),10)||0; return [p.month||0,p.day||0,e.category,ep,e.title]; }}
  function compareEntries(a,b) {{ var ka=sortKey(a), kb=sortKey(b); for(var i=0;i<ka.length;i++){{ if(ka[i]<kb[i]) return -1; if(ka[i]>kb[i]) return 1; }} return 0; }}
  function ageLabel(age) {{ return age === 1 ? '1 Jahr' : age + ' Jahre'; }}
  function roundFlags(age) {{ return {{ round5: age > 0 && age % 5 === 0, round10: age > 0 && age % 10 === 0 }}; }}
  function esc(s) {{ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }}
  function formatCardMeta(item) {{ var parts=[CATEGORY_LABELS[item.category]||item.category]; if(item.authors) parts.push(item.authors); parts.push('Release: '+item.release_date); return esc(parts.join(' \\u00b7 ')); }}
  function formatListMeta(item) {{ var parts=[CATEGORY_LABELS[item.category]||item.category]; if(item.authors) parts.push(item.authors); return esc(parts.join(' \\u00b7 ')); }}
  function renderBadges(item) {{ var f=roundFlags(item.age); var out='<div class="badge-row"><span class="badge">'+esc(ageLabel(item.age))+'</span>'; if(f.round10) out += '<span class="badge round10">Runder Geburtstag!</span>'; else if(f.round5) out += '<span class="badge round5">5er-Jubil&auml;um</span>'; if(item.parsed.unverified) out += '<span class="badge unverified">unverified</span>'; if(item.has_talkie) out += '<span class="badge talkie">Talkie</span>'; return out + '</div>'; }}
  function renderLinks(entry) {{ var parts=[]; if(entry.wiki_url_mmm) parts.push('<a href=\"'+esc(entry.wiki_url_mmm)+'\" target=\"_blank\" rel=\"noopener\">Wiki</a>'); if(entry.download_url) parts.push('<a href=\"'+esc(entry.download_url)+'\" target=\"_blank\" rel=\"noopener\">Download</a>'); return parts.length ? '<div class=\"card-links\">'+parts.join('')+'</div>' : ''; }}
  function renderCard(item) {{ var f=roundFlags(item.age); var cls='card'; if(f.round10) cls+=' round10'; else if(f.round5) cls+=' round5'; var title=esc(item.title); if(item.wiki_url_mmm) title='<a href=\"'+esc(item.wiki_url_mmm)+'\" target=\"_blank\" rel=\"noopener\">'+title+'</a>'; return '<div class=\"'+cls+'\"><div class=\"card-title\">'+title+'</div><div class=\"card-meta\">'+formatCardMeta(item)+'</div>'+renderBadges(item)+renderLinks(item)+'</div>'; }}
  function renderListItem(item, showCountdown) {{ var f=roundFlags(item.age); var title=esc(item.title); if(item.wiki_url_mmm) title='<a href=\"'+esc(item.wiki_url_mmm)+'\" target=\"_blank\" rel=\"noopener\">'+title+'</a>'; var dateStr=item.occurrence?formatShortDE(item.occurrence):''; var countdown=''; if(showCountdown&&item.daysUntil!=null) countdown=item.daysUntil===1?'morgen':'in '+item.daysUntil+' Tagen'; var badges='<span class=\"badge\">'+esc(ageLabel(item.age))+'</span>'; if(f.round10) badges+=' <span class=\"badge round10\">10er</span>'; else if(f.round5) badges+=' <span class=\"badge round5\">5er</span>'; return '<div class=\"list-item\">'+(dateStr?'<span class=\"list-date\">'+dateStr+'</span>':'')+(countdown?'<span class=\"list-countdown\">'+esc(countdown)+'</span>':'')+'<span class=\"list-title\">'+title+'</span><span class=\"list-meta\">'+formatListMeta(item)+'</span>'+badges+'</div>'; }}
  function renderSection(el, items, mode) {{ if(!items.length){{ el.innerHTML='<p class=\"section-empty\">Keine Eintr&auml;ge.</p>'; return; }} if(mode==='cards') el.innerHTML='<div class=\"cards\">'+items.map(renderCard).join('')+'</div>'; else el.innerHTML=items.map(function(i){{ return renderListItem(i, mode==='upcoming'); }}).join(''); }}
  function processCatalog(catalog) {{
    var today=startOfDay(new Date()); document.getElementById('currentDate').textContent=formatDateDE(today);
    var todayItems=[], upcomingItems=[], monthItems=[], yearOnlyItems=[];
    catalog.forEach(function(entry) {{
      var p=entry.parsed;
      if(p.precision==='year') {{ var ay=computeAge(p,today); if(ay>=1) yearOnlyItems.push(Object.assign({{}}, entry, {{ age: ay }})); return; }}
      var ageToday=computeAge(p,today); var isToday=today.getMonth()===p.month-1 && today.getDate()===p.day;
      if(isToday&&ageToday>=1) todayItems.push(Object.assign({{}}, entry, {{ age: ageToday }}));
      var occ=nextOccurrence(p,today); var days=daysBetween(today,occ);
      if(days>0&&days<=30) {{ var aa=computeAge(p,occ); if(aa>=1) upcomingItems.push(Object.assign({{}}, entry, {{ age: aa, occurrence: occ, daysUntil: days }})); }}
      if(today.getMonth()===p.month-1&&ageToday>=1) monthItems.push(Object.assign({{}}, entry, {{ age: ageToday, occurrence: new Date(today.getFullYear(), p.month-1, p.day) }}));
    }});
    todayItems.sort(compareEntries); upcomingItems.sort(function(a,b){{ return a.daysUntil-b.daysUntil || compareEntries(a,b); }}); monthItems.sort(function(a,b){{ return (a.parsed.day||0)-(b.parsed.day||0)||compareEntries(a,b); }}); yearOnlyItems.sort(compareEntries);
    var todayEl=document.getElementById('today-content');
    if(todayItems.length) renderSection(todayEl, todayItems, 'cards'); else {{ var next=upcomingItems[0]; todayEl.innerHTML='<p class=\"section-empty\">'+(next ? 'Heute keine Geburtstage &mdash; n&auml;chster am '+formatShortDE(next.occurrence)+': '+esc(next.title) : 'Heute keine Geburtstage.')+'</p>'; }}
    renderSection(document.getElementById('upcoming-content'), upcomingItems, 'upcoming');
    renderSection(document.getElementById('month-content'), monthItems, 'list');
    var yearEl=document.getElementById('year-only-content');
    if(yearOnlyItems.length) renderSection(yearEl, yearOnlyItems, 'cards'); else {{ yearEl.innerHTML='<p class=\"section-empty\">Keine Eintr&auml;ge mit nur Jahresangabe.</p>'; document.getElementById('sec-year-only').classList.add('hidden'); }}
    document.getElementById('loading').classList.add('hidden'); document.getElementById('content').classList.remove('hidden');
  }}
  fetch('birthdays-catalog.json').then(function(r){{ if(!r.ok) throw new Error('birthdays-catalog.json nicht gefunden'); return r.json(); }}).then(processCatalog).catch(function(err){{ document.getElementById('loading').textContent='Fehler beim Laden: '+err.message; }});
}})();
</script>
</body>
</html>"""


def main():
    rows = load_catalog()
    groups = group_by_category(rows)
    birthday_catalog = build_birthday_catalog(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    page = build_html(groups)
    OUTPUT_HTML.write_text(page, encoding="utf-8")
    BIRTHDAYS_HTML.write_text(build_birthdays_html(), encoding="utf-8")
    BIRTHDAYS_JSON.write_text(json.dumps(birthday_catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if FAVICON_SRC.exists():
        shutil.copy2(FAVICON_SRC, OUTPUT_DIR / "favicon.png")

    from build_quiz_site import build_quiz

    build_quiz(OUTPUT_DIR)

    total = sum(len(items) for _, items in groups)
    print(f"Wrote {OUTPUT_HTML} ({total} entries, {len(groups)} categories)")
    print(f"Wrote {BIRTHDAYS_HTML} ({len(birthday_catalog)} birthday entries)")
    print(f"Wrote {BIRTHDAYS_JSON}")


if __name__ == "__main__":
    main()
