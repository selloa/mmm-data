#!/usr/bin/env python3
"""Build static weekly quiz page under site/quiz/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from quiz_lib import (
    build_schedule,
    load_round_files,
    load_catalog,
    validate_rounds,
)
from site_chrome import (
    render_header_nav,
    subpage_chrome_css,
    theme_toggle_html,
    theme_toggle_script,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SITE_DIR = SCRIPT_DIR.parent / "site"


def build_quiz_html() -> str:
    site_nav = render_header_nav("quiz")
    chrome_css = subpage_chrome_css()
    theme_btn = theme_toggle_html()
    theme_script = theme_toggle_script()

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="../favicon.png">
<title>MMM Quiz</title>
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
    --ok: #2d6a2d;
    --bad: #a04040;
    --border-subtle: rgba(0,0,0,.07);
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
    --ok: #8cbf72;
    --bad: #e08080;
    --border-subtle: rgba(255,255,255,.04);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
{chrome_css}
  .round-meta {{
    font-size: .75rem;
    color: var(--muted);
    margin-bottom: .75rem;
  }}
  .round-meta strong {{ color: var(--accent); }}
  .round-theme {{ font-size: .8rem; color: var(--muted); margin-bottom: .5rem; }}
  .fallback-banner {{
    font-size: .78rem;
    color: var(--muted);
    margin-bottom: .75rem;
    padding: .5rem .65rem;
    border-radius: 4px;
    border: 1px dashed var(--card-border);
    background: var(--bg);
  }}
  .question {{
    font-size: 1rem;
    color: var(--text-bright);
    margin-bottom: 1rem;
  }}
  .options {{ display: flex; flex-direction: column; gap: .5rem; }}
  .opt {{
    font-family: inherit;
    font-size: .9rem;
    text-align: left;
    padding: .65rem .85rem;
    border: 1px solid var(--card-border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text);
    cursor: pointer;
    transition: border-color .15s, background .15s;
  }}
  .opt:hover:not(:disabled) {{
    border-color: var(--accent);
    background: var(--accent-dim);
  }}
  .opt:disabled {{ cursor: default; opacity: .85; }}
  .opt.correct {{ border-color: var(--ok); background: rgba(45,106,45,.12); }}
  .opt.wrong {{ border-color: var(--bad); background: rgba(160,64,64,.1); }}
  .opt.dim {{ opacity: .55; }}
  .result {{
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-subtle);
  }}
  .result-msg {{ font-size: .95rem; margin-bottom: .75rem; }}
  .result-msg.ok {{ color: var(--ok); }}
  .result-msg.bad {{ color: var(--bad); }}
  .explanation {{ font-size: .85rem; color: var(--muted); margin-bottom: 1rem; }}
  .links {{ font-size: .8rem; margin-bottom: 1rem; }}
  .links a {{ color: var(--link); margin-right: 1rem; }}
  .forum-box {{
    background: var(--bg);
    border: 1px dashed var(--card-border);
    border-radius: 4px;
    padding: .75rem;
    font-size: .8rem;
    white-space: pre-wrap;
    margin-bottom: .5rem;
  }}
  .btn-row {{ display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }}
  button.copy {{
    font-family: inherit;
    font-size: .8rem;
    padding: .45rem .75rem;
    border: 1px solid var(--accent);
    border-radius: 4px;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
  }}
  button.copy:hover {{ filter: brightness(1.08); }}
  label.feedback {{
    font-size: .75rem;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: .35rem;
    cursor: pointer;
  }}
  .empty {{ text-align: center; color: var(--muted); padding: 1rem 0; }}
  .hidden {{ display: none !important; }}
  #loading {{ text-align: center; color: var(--muted); padding: 2rem; }}
</style>
</head>
<body>
{theme_btn}
<div class="wrap">
  <header class="page-header">
    {site_nav}
    <h1>MMM Quiz</h1>
    <p class="subtitle">Eine Frage pro Woche</p>
    <p class="header-meta" id="headerMeta"></p>
  </header>

  <div id="loading">Quiz wird geladen&hellip;</div>
  <section class="section quiz-section empty hidden" id="empty"></section>
  <section class="section quiz-section hidden" id="quiz">
    <div class="fallback-banner hidden" id="fallbackBanner"></div>
    <div class="round-meta">Woche <strong id="weekLabel"></strong> &middot; <span id="catLabel"></span></div>
    <div class="round-theme" id="roundTheme"></div>
    <p class="question" id="questionText"></p>
    <div class="options" id="options"></div>
    <div id="result" class="result hidden">
      <p class="result-msg" id="resultMsg"></p>
      <p class="explanation" id="explanation"></p>
      <div class="links" id="resourceLinks"></div>
      <p style="font-size:.75rem;color:var(--muted);margin-bottom:.35rem;">F&uuml;rs Forum kopieren (ohne Spoiler):</p>
      <div class="forum-box" id="forumText"></div>
      <div class="btn-row">
        <button type="button" class="copy" id="copyBtn">In Zwischenablage kopieren</button>
        <label class="feedback"><input type="checkbox" id="catalogFeedback"> Hinweis: Katalog-Korrektur n&ouml;tig</label>
      </div>
      <p id="copyStatus" style="font-size:.7rem;color:var(--muted);margin-top:.35rem;"></p>
    </div>
  </section>

  <p class="footer-note">W&ouml;chentlich kuratiert &middot; Daten aus dem <a href="../index.html">MMM-Katalog</a></p>
</div>
{theme_script}
<script>
(function() {{
  var state = {{ round: null, attempts: 0, solved: false, schedule: null, week: '' }};

  function isoWeek(d) {{
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    var yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    var week = Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
    return t.getUTCFullYear() + '-W' + String(week).padStart(2, '0');
  }}

  function weekFromQuery() {{
    var m = /[?&]week=(\\d{{4}}-W\\d{{2}})/.exec(location.search);
    return m ? m[1] : null;
  }}

  function parseIsoWeek(w) {{
    var m = /^(\\d{{4}})-W(\\d{{2}})$/.exec(w);
    if (!m) return null;
    return {{ year: parseInt(m[1], 10), week: parseInt(m[2], 10) }};
  }}

  function compareIsoWeek(a, b) {{
    var pa = parseIsoWeek(a), pb = parseIsoWeek(b);
    if (!pa || !pb) return 0;
    if (pa.year !== pb.year) return pa.year - pb.year;
    return pa.week - pb.week;
  }}

  function findFallbackRound(week, schedule) {{
    var order = schedule.week_order || [];
    var best = null;
    for (var i = 0; i < order.length; i++) {{
      var w = order[i];
      if (compareIsoWeek(w, week) <= 0) best = w;
    }}
    if (!best || !schedule.rounds) return null;
    return schedule.rounds[best] || null;
  }}

  function updateHeaderMeta(week) {{
    var d = new Date();
    var dateStr = d.toLocaleDateString('de-DE', {{
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    }});
    document.getElementById('headerMeta').textContent =
      'Kalenderwoche ' + week + ' \\u00b7 ' + dateStr;
  }}

  function storageKey(week) {{ return 'mmm-quiz-' + week; }}

  function loadProgress(week) {{
    try {{
      var raw = sessionStorage.getItem(storageKey(week));
      return raw ? JSON.parse(raw) : {{ attempts: 0, solved: false }};
    }} catch (e) {{ return {{ attempts: 0, solved: false }}; }}
  }}

  function saveProgress() {{
    sessionStorage.setItem(storageKey(state.week), JSON.stringify({{
      attempts: state.attempts,
      solved: state.solved
    }}));
  }}

  function esc(s) {{
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }}

  function attemptLabel(n) {{
    if (n === 1) return 'Erster Versuch';
    return n + '. Versuch';
  }}

  function buildForumText() {{
    var r = state.round;
    var base = state.schedule.base_url || (location.href.split('?')[0]);
    var cat = r.category_label || r.category;
    var lines = ['\\uD83E\\uDDE0 MMM Quiz #' + state.week + ' \\u2014 ' + cat];
    if (state.solved) {{
      lines.push('\\u2705 ' + attemptLabel(state.attempts) + '!');
    }} else {{
      lines.push('\\u274C Noch nicht gel\\u00f6st nach ' + state.attempts + ' Versuch' + (state.attempts === 1 ? '' : 'en') + '.');
    }}
    if (document.getElementById('catalogFeedback').checked) {{
      lines.push('Ich glaube, das stimmt nicht \\u2014 der Katalog braucht hier eine Korrektur.');
    }}
    lines.push(base);
    return lines.join('\\n');
  }}

  function updateForumBox() {{
    document.getElementById('forumText').textContent = buildForumText();
  }}

  function showResult(won) {{
    var result = document.getElementById('result');
    if (!won) {{
      result.classList.remove('hidden');
      var msg = document.getElementById('resultMsg');
      msg.textContent = 'Noch nicht richtig \\u2014 versuch es noch einmal!';
      msg.className = 'result-msg bad';
      document.getElementById('explanation').classList.add('hidden');
      document.getElementById('resourceLinks').innerHTML =
        '<span style="color:var(--muted)">Tipp: Katalog &amp; Wiki nutzen</span>';
      return;
    }}
    result.classList.remove('hidden');
    var msg = document.getElementById('resultMsg');
    msg.textContent = 'Richtig! (' + attemptLabel(state.attempts) + ')';
    msg.className = 'result-msg ok';
    document.getElementById('explanation').textContent = state.round.explanation || '';
    document.getElementById('explanation').classList.remove('hidden');

    var links = document.getElementById('resourceLinks');
    var parts = [];
    var cid = state.round.links && state.round.links.catalog_id;
    if (cid) {{
      parts.push('<a href="../index.html" target="_blank" rel="noopener">Katalog: ' + esc(cid) + '</a>');
    }}
    if (state.round.links && state.round.links.wiki) {{
      parts.push('<a href="' + esc(state.round.links.wiki) + '" target="_blank" rel="noopener">MMM-Wiki</a>');
    }}
    links.innerHTML = parts.join('');

    updateForumBox();
  }}

  function renderRound(round, opts) {{
    opts = opts || {{}};
    state.round = round;
    var prog = loadProgress(state.week);
    state.attempts = prog.attempts || 0;
    state.solved = prog.solved || false;

    document.getElementById('loading').classList.add('hidden');
    document.getElementById('empty').classList.add('hidden');
    document.getElementById('quiz').classList.remove('hidden');
    document.getElementById('weekLabel').textContent = state.week;
    var banner = document.getElementById('fallbackBanner');
    if (opts.fallbackFrom) {{
      banner.textContent =
        'Keine neue Frage f\\u00fcr diese Woche \\u2014 Wiederholung aus ' + opts.fallbackFrom + '.';
      banner.classList.remove('hidden');
    }} else {{
      banner.textContent = '';
      banner.classList.add('hidden');
    }}
    document.getElementById('catLabel').textContent = round.category_label || round.category;
    var roundTheme = document.getElementById('roundTheme');
    roundTheme.textContent = round.theme ? 'Thema: ' + round.theme : '';
    roundTheme.classList.toggle('hidden', !round.theme);
    document.getElementById('questionText').textContent = round.question;

    var container = document.getElementById('options');
    container.innerHTML = '';
    round.options.forEach(function(opt, idx) {{
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'opt';
      btn.textContent = opt;
      btn.addEventListener('click', function() {{ onAnswer(idx, btn); }});
      container.appendChild(btn);
    }});

    if (state.solved) {{
      container.querySelectorAll('.opt').forEach(function(b, i) {{
        b.disabled = true;
        if (i === round.correct_index) b.classList.add('correct');
      }});
      showResult(true);
    }}
  }}

  function onAnswer(idx, btn) {{
    if (state.solved) return;
    state.attempts += 1;
    var correct = idx === state.round.correct_index;
    if (correct) {{
      state.solved = true;
      btn.classList.add('correct');
      document.querySelectorAll('.opt').forEach(function(b, i) {{
        b.disabled = true;
        if (i !== idx && i !== state.round.correct_index) b.classList.add('dim');
        if (i === state.round.correct_index && i !== idx) b.classList.add('correct');
      }});
      saveProgress();
      showResult(true);
    }} else {{
      btn.classList.add('wrong');
      btn.disabled = true;
      saveProgress();
      showResult(false);
      setTimeout(function() {{
        document.getElementById('result').classList.add('hidden');
        btn.classList.add('dim');
      }}, 1200);
    }}
  }}

  function showEmpty(week, schedule) {{
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('quiz').classList.add('hidden');
    var el = document.getElementById('empty');
    el.classList.remove('hidden');
    var nearest = schedule.week_order || [];
    var hint = nearest.length
      ? '<p style="margin-top:.75rem;font-size:.8rem;">Geplante Wochen: ' + esc(nearest.join(', ')) + '</p>'
      : '';
    el.innerHTML =
      '<p>F&uuml;r <strong>' + esc(week) + '</strong> ist noch keine Frage hinterlegt.</p>' + hint;
  }}

  document.getElementById('catalogFeedback').addEventListener('change', updateForumBox);

  document.getElementById('copyBtn').addEventListener('click', function() {{
    var text = buildForumText();
    navigator.clipboard.writeText(text).then(function() {{
      document.getElementById('copyStatus').textContent = 'Kopiert!';
      setTimeout(function() {{ document.getElementById('copyStatus').textContent = ''; }}, 2000);
    }}).catch(function() {{
      document.getElementById('copyStatus').textContent =
        'Kopieren fehlgeschlagen \\u2014 Text manuell markieren.';
    }});
  }});

  fetch('schedule.json')
    .then(function(r) {{
      if (!r.ok) throw new Error('schedule.json nicht gefunden');
      return r.json();
    }})
    .then(function(schedule) {{
      state.schedule = schedule;
      var week = weekFromQuery() || isoWeek(new Date());
      state.week = week;
      updateHeaderMeta(week);
      var round = schedule.rounds && schedule.rounds[week];
      if (round) {{
        renderRound(round);
      }} else {{
        var fallback = findFallbackRound(week, schedule);
        if (fallback) {{
          renderRound(fallback, {{ fallbackFrom: fallback.week }});
        }} else {{
          showEmpty(week, schedule);
        }}
      }}
    }})
    .catch(function(err) {{
      document.getElementById('loading').textContent = 'Fehler: ' + err.message;
    }});
}})();
</script>
</body>
</html>"""


def build_quiz(site_dir: Path | None = None) -> int:
    site_dir = site_dir or DEFAULT_SITE_DIR
    quiz_dir = site_dir / "quiz"
    quiz_dir.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog()
    rounds = load_round_files()
    validate_rounds(rounds, catalog)
    schedule = build_schedule(rounds)

    (quiz_dir / "schedule.json").write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (quiz_dir / "index.html").write_text(build_quiz_html(), encoding="utf-8")

    print(f"Wrote {quiz_dir / 'index.html'} ({len(rounds)} rounds)")
    print(f"Wrote {quiz_dir / 'schedule.json'}")
    return len(rounds)


def main() -> None:
    try:
        build_quiz()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"quiz build error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
