#!/usr/bin/env python3
"""One-off migration: FG-002 -> EP-000 (MMM Origins), renumber FG-003..FG-013."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "source" / "mmm_catalog.csv"


def main() -> int:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [fn for fn in reader.fieldnames if fn]
        rows = list(reader)

    fg002 = next((r for r in rows if r["catalog_id"] == "FG-002"), None)
    if fg002 is None:
        print("error: FG-002 not found", file=sys.stderr)
        return 1
    if any(r["catalog_id"] == "EP-000" for r in rows):
        print("error: EP-000 already exists", file=sys.stderr)
        return 1

    ep000 = {k: fg002.get(k, "") for k in fieldnames}
    ep000["catalog_id"] = "EP-000"
    ep000["category"] = "MMM Origins"
    ep000["title"] = "Maniac Mansion Deluxe"
    if not ep000.get("release_date", "").strip():
        ep000["release_date"] = "2005-03-07"
    if not ep000.get("wiki_url_mmm", "").strip():
        ep000["wiki_url_mmm"] = (
            "http://wiki.maniac-mansion-mania.de/wiki/Maniac_Mansion_Deluxe"
        )

    result: list[dict[str, str]] = []
    for row in rows:
        cid = row["catalog_id"]
        if cid == "FG-002":
            continue
        row = {k: row.get(k, "") for k in fieldnames}
        if cid == "CO-001":
            result.append(row)
            result.append(ep000)
            continue
        m = re.fullmatch(r"FG-(\d+)", cid)
        if m and int(m.group(1)) >= 3:
            row["catalog_id"] = f"FG-{int(m.group(1)) - 1:03d}"
            if row["catalog_id"] == "FG-012" and row.get("category") == "Fan-Games":
                row["category"] = "Fan Games"
        result.append(row)

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(result)

    print(f"ok: wrote {len(result)} rows to {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
