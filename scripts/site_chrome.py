#!/usr/bin/env python3
"""Shared header navigation and theme toggle for mmm-data static pages."""

from __future__ import annotations

from typing import Literal

ActivePage = Literal["catalog", "list", "birthdays", "quiz"]

_NAV_TARGETS = ("catalog", "list", "birthdays", "quiz")
_NAV_LABELS = {
    "catalog": "Katalog",
    "list": "Tabelle",
    "birthdays": "Geburtstage",
    "quiz": "Quiz",
}
_NAV_HREFS: dict[ActivePage, dict[str, str | None]] = {
    "catalog": {
        "catalog": None,
        "list": "list.html",
        "birthdays": "birthdays.html",
        "quiz": "quiz/",
    },
    "list": {
        "catalog": "index.html",
        "list": None,
        "birthdays": "birthdays.html",
        "quiz": "quiz/",
    },
    "birthdays": {
        "catalog": "index.html",
        "list": "list.html",
        "birthdays": None,
        "quiz": "quiz/",
    },
    "quiz": {
        "catalog": "../index.html",
        "list": "../list.html",
        "birthdays": "../birthdays.html",
        "quiz": None,
    },
}


def render_header_nav(active: ActivePage) -> str:
    hrefs = _NAV_HREFS[active]
    items: list[tuple[str, str | None, bool]] = [
        (_NAV_LABELS[target], hrefs[target], target == active) for target in _NAV_TARGETS
    ]

    parts: list[str] = []
    for i, (label, href, is_current) in enumerate(items):
        if i > 0:
            parts.append('<span class="nav-sep">&middot;</span>')
        if is_current:
            parts.append(f'<span class="nav-current">{label}</span>')
        else:
            parts.append(f'<a href="{href}">{label}</a>')

    inner = "".join(parts)
    return f'<nav class="header-nav" aria-label="Seitennavigation">{inner}</nav>'


def site_footer_css() -> str:
    return """
  footer {
    max-width: 1100px;
    margin: 3rem auto 1rem;
    padding: 1.2rem 1.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    color: var(--muted);
    font-size: .75rem;
    line-height: 1.7;
  }
  footer strong { color: var(--text-bright); }
  footer a { color: var(--link); }
  footer a:hover { color: var(--link-hover); }"""


def render_site_footer() -> str:
    return """<footer>
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
</footer>"""


def header_nav_css() -> str:
    return """
  .header-nav .nav-sep {
    color: var(--muted);
    margin: 0 .35rem;
  }
  .header-nav .nav-current {
    color: var(--muted);
    letter-spacing: .3px;
  }"""


def theme_toggle_css() -> str:
    return """
  .theme-toggle {
    position: fixed;
    top: 1rem;
    right: 1rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: .4rem .7rem;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    color: var(--text);
    z-index: 200;
    transition: background .2s;
  }
  .theme-toggle:hover { background: var(--accent-dim); }"""


def theme_toggle_html() -> str:
    return (
        '<button class="theme-toggle" id="themeToggle" '
        'title="Dark / Light Mode" aria-label="Dark / Light Mode">&#9790;</button>'
    )


def theme_toggle_script() -> str:
    return """
<script>
(function() {
  var html = document.documentElement;
  var toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  if (localStorage.getItem('theme') === 'dark') html.classList.add('dark');
  function updateIcon() {
    toggle.textContent = html.classList.contains('dark') ? '\\u2600' : '\\u263E';
  }
  updateIcon();
  toggle.addEventListener('click', function() {
    html.classList.toggle('dark');
    localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
    updateIcon();
  });
})();
</script>"""


def subpage_chrome_css() -> str:
    """Layout chrome shared by birthdays and quiz subpages."""
    return (
        header_nav_css()
        + theme_toggle_css()
        + """
  body { font-family: 'Roboto Mono', monospace; background: var(--bg); color: var(--text);
    line-height: 1.6; padding: 2rem 1rem 3rem; font-size: 14px; }
  .wrap { max-width: 1100px; margin: 0 auto; }
  .page-header { margin-bottom: 1.5rem; }
  .header-nav {
    text-align: center;
    margin-bottom: .6rem;
    font-size: .72rem;
  }
  .header-nav a {
    color: var(--muted);
    text-decoration: none;
    letter-spacing: .3px;
  }
  .header-nav a:hover {
    color: var(--text);
    text-decoration: underline;
  }
  h1 {
    text-align: center;
    font-family: 'Cabin Sketch', cursive;
    font-size: 2.2rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-bright);
    letter-spacing: 1px;
  }
  .subtitle {
    text-align: center;
    font-family: 'Amatic SC', cursive;
    color: var(--muted);
    margin: .3rem 0 1rem;
    font-size: 1.4rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
  }
  .header-meta {
    text-align: center;
    font-size: .8rem;
    color: var(--muted);
    margin-bottom: 1.5rem;
  }
  .section {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 4px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.5rem;
  }
  .quiz-section { max-width: 42rem; margin-left: auto; margin-right: auto; }
  .footer-note {
    text-align: center;
    font-size: .72rem;
    color: var(--muted);
    margin-top: 1rem;
  }
  .footer-note a { color: var(--link); text-decoration: none; }
  .footer-note a:hover { text-decoration: underline; }"""
    )
