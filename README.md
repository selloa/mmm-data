# mmm-data

**Canonical, versioned metadata** for the [Maniac Mansion Mania](https://www.maniac-mansion-mania.de/) (MMM) fan project: episode and related catalog rows, distribution links, and engine hints. The machine-readable catalog is **`data/entries/<catalog_id>.json`** (one file per row, generated from `source/mmm_catalog.csv`).

**Planning:** lives in [mmm-system-design](https://github.com/selloa/mmm-system-design).

**Purpose:** a **versioned canonical catalog** of MMM works (episodes, collections, fan games, and related rows). Later you can add more datasets and schemas beside the catalog without changing this core idea.

**What belongs here (v1):** `schema/` (JSON Schema), `source/` (authoring CSV), `data/entries/` (generated JSON, one object per file), `tools/` (encode + validate), `requirements.txt`, and `docs/` (human semantics). **Not** required on day one: a public API, website, or mirror automation—those consume this repo later.

**Build:** from this directory, after a one-time `python -m pip install -r requirements.txt`, run `python tools/build_catalog.py`. That encodes `source/mmm_catalog.csv` into `data/entries/*.json` and validates every file against `schema/mmm-catalog-entry.v1.schema.json`. Exit code `0` means the export matches the v1 contract.

**CI:** on every push and pull request to `main`, [GitHub Actions](.github/workflows/catalog-ci.yml) runs the same `build_catalog.py` step on Ubuntu and fails the job if the working tree would change (for example CSV updated but regenerated `data/entries/` not committed).

**Consuming:** each **`data/entries/<catalog_id>.json`** file is one catalog entry (v1 schema). Example raw URL (branch `main`):  
[https://raw.githubusercontent.com/selloa/mmm-data/main/data/entries/EP-001.json](https://raw.githubusercontent.com/selloa/mmm-data/main/data/entries/EP-001.json)  

Browse all entry files: [data/entries on `main`](https://github.com/selloa/mmm-data/tree/main/data/entries). For stable links, pin a **commit** or **tag** instead of `main` in the URL.

Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md).

Field meanings and validation in plain language: `docs/CATALOG_ENTRY_v1.md`.

**License:** [MIT](LICENSE) (see file for full text).
