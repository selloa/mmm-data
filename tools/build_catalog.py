#!/usr/bin/env python3
"""
Run CSV → JSONL encode, then JSON Schema validation.

From this folder (future mmm-data root):
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


def _default_jsonl() -> Path:
    return _data_repo_root() / "data" / "catalog.jsonl"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        default=_default_csv(),
        help=f"mmm_catalog.csv (default: {_default_csv()})",
    )
    p.add_argument(
        "--jsonl",
        type=Path,
        default=_default_jsonl(),
        help=f"output JSONL path, also validated (default: {_default_jsonl()})",
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

    r1 = subprocess.run(
        [sys.executable, str(encode), "--input", str(args.input), "--jsonl", str(args.jsonl)],
        check=False,
    )
    if r1.returncode != 0:
        return r1.returncode

    if args.skip_validate:
        return 0

    r2 = subprocess.run(
        [sys.executable, str(validate), "--jsonl", str(args.jsonl)],
        check=False,
    )
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
