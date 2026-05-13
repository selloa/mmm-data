#!/usr/bin/env python3
"""
Run CSV → per-entry JSON files, then JSON Schema validation.

From this folder (mmm-data root):
  python tools/build_catalog.py

From parent mmm-system-design:
  python mmm-data-design-v2/tools/build_catalog.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _data_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_csv() -> Path:
    return _data_repo_root() / "source" / "mmm_catalog.csv"


def _default_entries_dir() -> Path:
    return _data_repo_root() / "data" / "entries"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        default=_default_csv(),
        help=f"mmm_catalog.csv (default: {_default_csv()})",
    )
    p.add_argument(
        "--entries-dir",
        type=Path,
        default=_default_entries_dir(),
        help=f"one <catalog_id>.json per row (default: {_default_entries_dir()})",
    )
    p.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        metavar="PATH",
        help="optional: write a single JSONL file instead of per-entry files (not the default layout)",
    )
    p.add_argument(
        "--skip-validate",
        action="store_true",
        help="only run the encoder (not recommended)",
    )
    args = p.parse_args(argv)

    tools = Path(__file__).resolve().parent
    encode = tools / "csv_to_catalog_json.py"
    validate = tools / "validate_catalog_json.py"

    if args.jsonl is not None:
        enc_cmd = [sys.executable, str(encode), "--input", str(args.input), "--jsonl", str(args.jsonl)]
        val_cmd = [sys.executable, str(validate), "--jsonl", str(args.jsonl)]
    else:
        enc_cmd = [sys.executable, str(encode), "--input", str(args.input), "--out-dir", str(args.entries_dir)]
        val_cmd = [sys.executable, str(validate), "--entries-dir", str(args.entries_dir)]

    r1 = subprocess.run(enc_cmd, check=False)
    if r1.returncode != 0:
        return r1.returncode

    if args.skip_validate:
        return 0

    r2 = subprocess.run(val_cmd, check=False)
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
