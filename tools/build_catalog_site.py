#!/usr/bin/env python3
"""Build a static HTML catalog page from mmm_catalog.csv."""

import csv
import html
import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_CSV = SCRIPT_DIR.parent / "source" / "mmm_catalog.csv"
FAVICON_SRC = SCRIPT_DIR.parent / "assets" / "favicon-catalog.png"
OUTPUT_DIR = SCRIPT_DIR.parent / "site"
OUTPUT_HTML = OUTPUT_DIR / "index.html"

CATEGORY_ORDER = [
    "Collections",
    "MMM Origins",
    "MMM-Episoden",
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
    "Collections": "Sammlungen",
    "MMM Origins": "MMM Origins",
    "MMM-Episoden": "MMM-Episoden",
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

CATEGORY_ANCHOR = {
    "Collections": "sammlungen",
    "MMM Origins": "origins",
    "MMM-Episoden": "episoden",
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
        slots.append(f'<a href="{esc(yt)}" title="{esc(label)}" class="icon-link icon-yt"{_t}>{esc(label)}</a>')
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
    return sorted(seasons.items())


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
    anchor = CATEGORY_ANCHOR["MMM-Episoden"]
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
  <summary>MMM-Episoden <span>({count})</span></summary>
{inner}
  </details>
</section>"""


def render_category_section(cat, items, open_by_default=False):
    if cat == "MMM-Episoden":
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


def build_html(groups):
    total = sum(len(items) for _, items in groups)
    toc_html = render_toc(groups)

    sections = []
    for i, (cat, items) in enumerate(groups):
        open_default = cat in ("Sammlungen", "MMM-Episoden")
        sections.append(render_category_section(cat, items, open_by_default=open_default))

    sections_html = "\n\n".join(sections)

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
  .toc {{
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
    grid-template-columns: 3.2rem auto 3.8rem 3.6rem 5.2rem;
    gap: .2rem;
    align-items: center;
  }}
  .link-slot {{
    display: flex;
    justify-content: center;
    min-height: 1.2rem;
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
    background: rgba(96, 147, 76, 0.12);
    color: var(--accent);
    border-color: var(--accent-dim);
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
  .theme-toggle {{
    position: fixed;
    top: 1rem;
    right: 1rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: .4rem .6rem;
    cursor: pointer;
    font-size: 1.1rem;
    line-height: 1;
    z-index: 200;
    transition: background .2s;
  }}
  .theme-toggle:hover {{ background: var(--accent-dim); }}
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

<button class="theme-toggle" id="themeToggle" title="Dark / Light Mode">&#9790;</button>

<div id="google_translate_element" style="margin-bottom:.5rem; opacity:.6; font-size:.75rem;"></div>

<h1>Katalog</h1>
<p class="subtitle">Alle Episoden und Specials auf einen Blick</p>

<p class="intro">
  Der komplette Katalog aller Maniac Mansion Mania Episoden, Specials, Fan-Games und mehr \u2013
  mit Links zu Wiki, Komplettl\u00f6sungen, YouTube-Longplays und Downloads.
</p>

<p class="stats">{total} Eintr\u00e4ge in {len(groups)} Kategorien</p>

<div class="search-wrap">
  <input type="text" id="search" placeholder="Katalog durchsuchen\u2026">
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

<script>
(function() {{
  var html = document.documentElement;
  var toggle = document.getElementById('themeToggle');
  var stored = localStorage.getItem('theme');
  if (stored === 'dark') {{
    html.classList.add('dark');
  }}
  function updateIcon() {{
    toggle.textContent = html.classList.contains('dark') ? '\u2600' : '\u263E';
  }}
  updateIcon();
  toggle.addEventListener('click', function() {{
    html.classList.toggle('dark');
    localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
    updateIcon();
  }});

  var search = document.getElementById('search');
  var sections = document.querySelectorAll('.category');

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


def main():
    rows = load_catalog()
    groups = group_by_category(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    page = build_html(groups)
    OUTPUT_HTML.write_text(page, encoding="utf-8")

    if FAVICON_SRC.exists():
        shutil.copy2(FAVICON_SRC, OUTPUT_DIR / "favicon.png")

    total = sum(len(items) for _, items in groups)
    print(f"Wrote {OUTPUT_HTML} ({total} entries, {len(groups)} categories)")


if __name__ == "__main__":
    main()
