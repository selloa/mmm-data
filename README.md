# mmm-data

**Canonical, versioned metadata** for the [Maniac Mansion Mania](https://www.maniac-mansion-mania.de/) (MMM) fan project: episode and related catalog rows, distribution links, and engine hints. The machine-readable bundle is `data/catalog.jsonl` (generated from `source/mmm_catalog.csv`). Planning and broader ecosystem notes live in the separate [`mmm-system-design`](https://github.com/selloa/mmm-system-design) repository.

**Purpose:** a **versioned canonical catalog** of MMM works (episodes, collections, fan games, and related rows). Later you can add more datasets and schemas beside the catalog without changing this core idea.

**What belongs here (v1):** `schema/` (JSON Schema), `source/` (authoring CSV), `data/` (generated JSONL), `tools/` (encode + validate), `requirements.txt`, and `docs/` (human semantics). **Not** required on day one: a public API, website, or mirror automation—those consume this repo later.

**Build:** from this directory, after a one-time `python -m pip install -r requirements.txt`, run `python tools/build_catalog.py`. That encodes `source/mmm_catalog.csv` into `data/catalog.jsonl` and validates every line against `schema/mmm-catalog-entry.v1.schema.json`. Exit code `0` means the export matches the v1 contract.

Field meanings and validation in plain language: `docs/CATALOG_ENTRY_v1.md`.

**License:** [MIT](LICENSE) (see file for full text).
