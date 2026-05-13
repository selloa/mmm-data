# mmm-data (prototype layout)

This folder is a **dry run** of the future **`mmm-data`** Git repository: same layout you can copy to a new repo root when you create it. It currently lives under `mmm-system-design` only for convenience.

**Purpose:** a **versioned canonical catalog** of MMM works (episodes, collections, fan games, and related rows). The machine-readable truth is `data/catalog.jsonl` (generated). Later you can add more datasets and schemas beside the catalog without changing this core idea.

**What belongs here (v1):** `schema/` (JSON Schema), `source/` (authoring CSV), `data/` (generated JSONL), `tools/` (encode + validate), `requirements.txt`, and `docs/` (human semantics). **Not** required on day one: a public API, website, or mirror automation—those consume this repo later.

**Build:** from this directory, after a one-time `python -m pip install -r requirements.txt`, run `python tools/build_catalog.py`. That encodes `source/mmm_catalog.csv` into `data/catalog.jsonl` and validates every line against `schema/mmm-catalog-entry.v1.schema.json`. Exit code `0` means the export matches the v1 contract.

Field meanings and validation in plain language: `docs/CATALOG_ENTRY_v1.md`.
