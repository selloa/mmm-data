#!/usr/bin/env python3
"""
Convert mmm_catalog.csv rows to canonical v1 JSON (see docs/CATALOG_ENTRY_v1.md).

Rules:
  - Every canonical field is present on each object; empty CSV cells become JSON null.
  - authors: split on ',', strip parts, drop empties -> string array or null if none.
  - catalog_id, category, title must be non-empty after strip (exit 1 otherwise).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

CANONICAL_FIELDS: list[str] = [
    "catalog_id",
    "category",
    "title",
    "has_talkie",
    "release_date",
    "authors",
    "forum_thread_url_mmm",
    "wiki_url_mmm",
    "walkthrough_url_mmm",
    "walkthrough_mmm_author",
    "walkthrough_mmm_date",
    "walkthrough_mmm_body",
    "walkthrough_url_amigamaster",
    "mmm_description",
    "forum_thread_url_adventure_treff",
    "forum_thread_url_adventure_treff_legacy",
    "youtube_longplay_url",
    "youtube_longplay_duration",
    "download_url_mmm_docman",
    "download_url_mmm_canonical",
    "release_package_filename",
    "release_package_stemname",
    "release_package_size_bytes",
    "game_files_subpath",
    "engine",
    "engine_version",
    "mirror_url_github_private",
    "mirror_url_dropbox_public",
]

STRING_OR_NULL_FIELDS = frozenset(CANONICAL_FIELDS) - frozenset(
    {"authors", "release_package_size_bytes"}
)


def _data_repo_root() -> Path:
    """Folder containing tools/, schema/, source/, data/ (this prototype or future mmm-data root)."""
    return Path(__file__).resolve().parents[1]


def _default_csv_path() -> Path:
    return _data_repo_root() / "source" / "mmm_catalog.csv"


def _cell_string(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def _cell_authors(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    parts = [p.strip().strip("'") for p in raw.split(",")]
    parts = [p for p in parts if p]
    return parts if parts else None


def _cell_integer(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    return int(s)


def csv_row_to_entry(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in CANONICAL_FIELDS:
        raw = row.get(key, "")
        if key == "authors":
            out[key] = _cell_authors(raw)
        elif key == "release_package_size_bytes":
            out[key] = _cell_integer(raw)
        elif key in STRING_OR_NULL_FIELDS:
            val = _cell_string(raw)
            out[key] = val
        else:
            raise AssertionError(f"unknown field {key!r}")
    return out


def validate_required_strings(entry: dict[str, Any], *, row_index: int) -> None:
    for k in ("catalog_id", "category", "title"):
        v = entry.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"row {row_index}: {k!r} must be a non-empty string, got {v!r}")


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing header row")
        header = [h.strip() for h in reader.fieldnames if h is not None and h.strip()]
        if set(header) != set(CANONICAL_FIELDS):
            missing = sorted(set(CANONICAL_FIELDS) - set(header))
            extra = sorted(set(header) - set(CANONICAL_FIELDS))
            msg = f"{path}: CSV columns must match canonical v1 set exactly."
            if missing:
                msg += f" Missing: {missing}."
            if extra:
                msg += f" Extra: {extra}."
            raise ValueError(msg)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({k: (row.get(k) or "") for k in CANONICAL_FIELDS})
    return header, rows


def emit_jsonl(entries: list[dict[str, Any]], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in entries]
    dest.write_text("".join(lines), encoding="utf-8", newline="\n")


def emit_one_file_per_row(entries: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for e in entries:
        cid = e["catalog_id"]
        if not isinstance(cid, str) or "/" in cid or "\\" in cid:
            raise ValueError(f"unsafe or invalid catalog_id for filename: {cid!r}")
        path = out_dir / f"{cid}.json"
        path.write_text(
            json.dumps(e, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        default=_default_csv_path(),
        help=f"path to mmm_catalog.csv (default: {_default_csv_path()})",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--jsonl",
        type=Path,
        metavar="PATH",
        help="write newline-delimited JSON (one catalog entry per line)",
    )
    mode.add_argument(
        "--out-dir",
        type=Path,
        metavar="DIR",
        help="write one pretty-printed <catalog_id>.json per row",
    )
    args = p.parse_args(argv)

    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 1

    try:
        _, rows = read_csv_rows(args.input)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    entries: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=2):
        try:
            entry = csv_row_to_entry(row)
            validate_required_strings(entry, row_index=i)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        entries.append(entry)

    try:
        if args.jsonl is not None:
            emit_jsonl(entries, args.jsonl)
        else:
            emit_one_file_per_row(entries, args.out_dir)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"ok: {len(entries)} entries from {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
