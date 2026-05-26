"""Fetch YouTube video durations via yt-dlp and add as a column to mmm_catalog.csv."""

import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "source" / "mmm_catalog.csv"
WORKERS = 15
INSERT_AFTER = "youtube_longplay_url"
NEW_COL = "youtube_longplay_duration"


def get_duration(url: str) -> str:
    """Return duration string (e.g. '20:44') for a YouTube URL, or '' on failure."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-download", "--print", "duration_string", url],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def main():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    if NEW_COL in fieldnames:
        print(f"Column '{NEW_COL}' already exists — aborting.")
        sys.exit(1)

    idx = fieldnames.index(INSERT_AFTER) + 1
    fieldnames.insert(idx, NEW_COL)

    url_to_rows: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        url = row.get(INSERT_AFTER, "").strip()
        if url:
            url_to_rows.setdefault(url, []).append(i)

    unique_urls = list(url_to_rows.keys())
    print(f"Fetching durations for {len(unique_urls)} unique URLs ({WORKERS} workers)…")

    durations: dict[str, str] = {}
    done = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(get_duration, url): url for url in unique_urls}
        for future in as_completed(futures):
            url = futures[future]
            dur = future.result()
            durations[url] = dur
            done += 1
            if not dur:
                failed += 1
            if done % 20 == 0 or done == len(unique_urls):
                print(f"  {done}/{len(unique_urls)} done ({failed} failed)")

    for row in rows:
        url = row.get(INSERT_AFTER, "").strip()
        row[NEW_COL] = durations.get(url, "") if url else ""

    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Wrote {len(rows)} rows with '{NEW_COL}' column.")
    if failed:
        print(f"Warning: {failed} URL(s) returned no duration.")


if __name__ == "__main__":
    main()
