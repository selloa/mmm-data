"""Retry fetching missing YouTube durations one at a time with strict timeouts."""

import csv
import subprocess
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "source" / "mmm_catalog.csv"
URL_COL = "youtube_longplay_url"
DUR_COL = "youtube_longplay_duration"
BATCH_SAVE = 10


def get_duration(url: str) -> str:
    try:
        result = subprocess.run(
            [
                "yt-dlp", "--no-download", "--print", "duration_string",
                "--socket-timeout", "15", "--retries", "0",
                "--no-playlist", url,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def save(rows, fieldnames):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    missing = [
        (i, rows[i][URL_COL].strip())
        for i in range(len(rows))
        if rows[i].get(URL_COL, "").strip() and not rows[i].get(DUR_COL, "").strip()
    ]
    total = len(missing)
    print(f"{total} URLs still need durations.", flush=True)
    if not total:
        return

    filled = 0
    failed = 0
    for n, (i, url) in enumerate(missing, 1):
        dur = get_duration(url)
        if dur:
            rows[i][DUR_COL] = dur
            filled += 1
        else:
            failed += 1
        print(f"  [{n}/{total}] {rows[i].get('catalog_id','?')}: {dur or 'FAILED'}", flush=True)
        if n % BATCH_SAVE == 0:
            save(rows, fieldnames)

    save(rows, fieldnames)
    print(f"Done. Filled {filled}, failed {failed}.", flush=True)


if __name__ == "__main__":
    main()
