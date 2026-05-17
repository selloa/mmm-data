#!/usr/bin/env python3
"""Append rows from partial_mmm_catalog.csv to source/mmm_catalog.csv (append-only)."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from csv_to_catalog_json import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MASTER = ROOT / "source" / "mmm_catalog.csv"
DEFAULT_PARTIAL = (
    ROOT.parent
    / "mmm-local"
    / "mmm-wiki-api-access"
    / "mmm-catalog-partial"
    / "partial_mmm_catalog.csv"
)


def map_category(partial_row: dict[str, str]) -> str:
    title = partial_row.get("title", "")
    cat = partial_row.get("category", "").strip()
    if "Ostereiersuche" in title:
        return "Ostern"
    return cat


def partial_to_master_row(partial_row: dict[str, str]) -> dict[str, str]:
    out = {k: "" for k in CANONICAL_FIELDS}
    out["catalog_id"] = (partial_row.get("catalog_id") or "").strip()
    out["category"] = map_category(partial_row)
    out["title"] = (partial_row.get("title") or "").strip()
    out["release_date"] = (partial_row.get("release_date") or "").strip()
    out["authors"] = (partial_row.get("author") or partial_row.get("authors") or "").strip()
    out["download_url_mmm_docman"] = (partial_row.get("download_url") or "").strip()
    out["walkthrough_url"] = (partial_row.get("walkthrough_url") or "").strip()
    out["mmm_description"] = (
        partial_row.get("mmm_description") or partial_row.get("description") or ""
    ).strip()
    return out


def read_master(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if set(reader.fieldnames or []) != set(CANONICAL_FIELDS):
            raise ValueError(f"{path}: header must match canonical v1 columns")
        return [{k: (row.get(k) or "") for k in CANONICAL_FIELDS} for row in reader]


def append_partial(
    master_path: Path,
    partial_path: Path,
    *,
    catalog_id_prefix: str = "",
) -> int:
    master_rows = read_master(master_path)
    existing_ids = {r["catalog_id"] for r in master_rows}
    with partial_path.open(encoding="utf-8-sig", newline="") as f:
        partial_rows = list(csv.DictReader(f))

    if catalog_id_prefix:
        partial_rows = [
            r
            for r in partial_rows
            if (r.get("catalog_id") or "").startswith(catalog_id_prefix)
        ]

    new_rows = [partial_to_master_row(r) for r in partial_rows]
    new_rows = [r for r in new_rows if r["catalog_id"] not in existing_ids]
    for i, row in enumerate(new_rows, start=1):
        if not row["catalog_id"] or not row["category"] or not row["title"]:
            raise ValueError(f"partial row {i}: catalog_id, category, title required")

    combined = master_rows + new_rows
    with master_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS)
        w.writeheader()
        w.writerows(combined)

    return len(new_rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    p.add_argument("--partial", type=Path, default=DEFAULT_PARTIAL)
    p.add_argument(
        "--catalog-id-prefix",
        default="",
        help="only append partial rows whose catalog_id starts with this prefix",
    )
    args = p.parse_args()
    if not args.partial.is_file():
        print(f"partial not found: {args.partial}", file=sys.stderr)
        return 1
    n = append_partial(
        args.master,
        args.partial,
        catalog_id_prefix=args.catalog_id_prefix,
    )
    print(f"Appended {n} rows to {args.master} (total now {len(read_master(args.master))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
