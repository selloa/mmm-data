# Canonical catalog entry (v1)

**v1** means: one logical record per CSV row, **every CSV column** represented in the canonical JSON (no dropped fields).

Human-edited source file in this repo layout: `source/mmm_catalog.csv`. Generated catalog: **`data/entries/<catalog_id>.json`** (one v1 object per file).

## Rules

- **Primary key:** `catalog_id` (stable; matches CSV).
- **Property names:** Same as CSV header (`snake_case`), so the CSV→JSON mapping is obvious.
- **Empty CSV cell:** Stored as JSON `null` (never omit the key in v1 — keeps shape uniform and diffs simple).
- **`authors`:** Canonical form is a **JSON array of strings**; the converter splits the CSV on `;` and trims each part. Empty / whitespace-only → `null`.

## Field table

| CSV column | JSON type | Notes |
| --- | --- | --- |
| `catalog_id` | string | Required globally unique id. |
| `category` | string | |
| `title` | string | |
| `release_date` | string \| null | Keep raw string from CSV for now (includes values like `Created on …`). |
| `authors` | array of string \| null | Normalized from `;`-separated list. |
| `forum_thread_url_mmm` | string \| null | URI string; stricter URL checks can come later. |
| `wiki_url_mmm` | string \| null | |
| `forum_thread_url_adventure_treff` | string \| null | |
| `forum_thread_url_adventure_treff_legacy` | string \| null | |
| `youtube_longplay_url` | string \| null | |
| `download_url_mmm_docman` | string \| null | |
| `download_url_mmm_canonical` | string \| null | |
| `release_package_filename` | string \| null | |
| `release_package_stemname` | string \| null | |
| `game_files_subpath` | string \| null | |
| `engine` | string \| null | |
| `engine_version` | string \| null | |
| `mirror_url_github_private` | string \| null | |
| `mirror_url_dropbox_public` | string \| null | |

## What validation means (plain language)

**JSON** is flexible: you can write objects with wrong field names, missing keys, or strings where a list was expected, and a normal text editor will not stop you.

**Validation** means: a small program reads each catalog object and answers **“does this match the contract we agreed on?”** That contract is written twice for humans and machines:

1. This markdown (field table and rules).
2. The **JSON Schema** file `schema/mmm-catalog-entry.v1.schema.json` (same rules in a precise, checkable form).

The validator loads the schema, then for each JSON file it checks things like: every required key exists, types are correct (`authors` is array or `null`, URLs are strings or `null`, and so on). If something is wrong, it prints **which file** and **what** failed. Exit code `0` means everything passed; non-zero means “do not trust this export until fixed.”

On top of the schema, our script checks **`catalog_id` is unique** across all entry files (the schema alone cannot express “no duplicates across files”).

This is not “AI checking your data.” It is a **deterministic checklist** you can run the same way every time.

## Commands (from repo root `mmm-data/`)

1. One-time: `python -m pip install -r requirements.txt`
2. Encode + validate: `python tools/build_catalog.py`
3. Manual encode only: `python tools/csv_to_catalog_json.py --out-dir data/entries` (optional `--input` override).
4. Manual validate only: `python tools/validate_catalog_json.py --entries-dir data/entries`
5. Optional single JSONL export: `python tools/build_catalog.py --jsonl path/to/catalog.jsonl`
