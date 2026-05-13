#!/usr/bin/env python3
"""
Validate catalog JSON against the v1 JSON Schema, plus a duplicate catalog_id check.

Requires: python -m pip install -r requirements.txt (from the mmm-data repo root / this folder).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
except ImportError:
    print(
        "error: missing package 'jsonschema'. From this folder (repo root) run:\n"
        "  python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from None


def _data_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_schema_path() -> Path:
    return _data_repo_root() / "schema" / "mmm-catalog-entry.v1.schema.json"


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _format_schema_error(err: ValidationError, *, label: str) -> str:
    path = ".".join(str(p) for p in err.absolute_path) or "(root)"
    return f"{label}: schema error at {path}: {err.message}"


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path!s} line {lineno}: invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"{path!s} line {lineno}: expected a JSON object, got {type(obj).__name__}")
        yield lineno, obj


def iter_entry_files(directory: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    paths = sorted(directory.glob("*.json"))
    for p in paths:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{p!s}: invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"{p!s}: expected a JSON object, got {type(obj).__name__}")
        yield str(p), obj


def validate_entries(
    validator: Draft202012Validator,
    items: Iterator[tuple[str, dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    for label, obj in items:
        for err in validator.iter_errors(obj):
            errors.append(_format_schema_error(err, label=label))
        cid = obj.get("catalog_id")
        if isinstance(cid, str) and cid:
            if cid in seen_ids:
                errors.append(f"{label}: duplicate catalog_id {cid!r} (also at {seen_ids[cid]})")
            else:
                seen_ids[cid] = label
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--jsonl",
        type=Path,
        metavar="PATH",
        help="newline-delimited JSON (one catalog entry per line)",
    )
    src.add_argument(
        "--entries-dir",
        type=Path,
        metavar="DIR",
        help="directory of <catalog_id>.json files",
    )
    p.add_argument(
        "--schema",
        type=Path,
        default=_default_schema_path(),
        help=f"path to JSON Schema (default: {_default_schema_path()})",
    )
    args = p.parse_args(argv)

    if not args.schema.is_file():
        print(f"error: schema not found: {args.schema}", file=sys.stderr)
        return 1

    try:
        schema = _load_schema(args.schema)
        validator = _validator(schema)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"error: invalid schema file: {e}", file=sys.stderr)
        return 1

    try:
        if args.jsonl is not None:
            if not args.jsonl.is_file():
                print(f"error: file not found: {args.jsonl}", file=sys.stderr)
                return 1
            items = ((f"{args.jsonl} line {ln}", obj) for ln, obj in iter_jsonl(args.jsonl))
        else:
            if not args.entries_dir.is_dir():
                print(f"error: not a directory: {args.entries_dir}", file=sys.stderr)
                return 1
            items = iter_entry_files(args.entries_dir)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    errors = validate_entries(validator, items)
    if errors:
        print("validation failed:", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(f"ok: validated against {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
