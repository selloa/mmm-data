# Contributing to mmm-data

## What to change

- **Catalog facts** (titles, URLs, authors, and so on) go in **`source/mmm_catalog.csv`**. Do not hand-edit files under **`data/entries/`**; they are generated.

## Before you open a PR

1. Install tooling once (per machine or venv):

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Regenerate and validate the bundle:

   ```bash
   python tools/build_catalog.py
   ```

   Exit code **0** means the JSON matches **`schema/mmm-catalog-entry.v1.schema.json`** and `catalog_id` values are unique.

3. Commit **`source/mmm_catalog.csv`** and the updated files under **`data/entries/`** when the CSV changed, so `main` always reflects a passing build.

## Pull requests

- Describe what you fixed or added (sources, mirrors, spelling, new row, and so on).
- If you are unsure about a field, say so in the PR text; maintainers can help align with `docs/CATALOG_ENTRY_v1.md`.

## Schema or tooling changes

- Changing **`schema/`** or **`tools/`** is a bigger contract change. Prefer a dedicated PR and mention any impact on consumers of the JSON under **`data/entries/`**.
