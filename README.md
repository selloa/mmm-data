# mmm-data

**Canonical, versioned metadata** for the [Maniac Mansion Mania](https://www.maniac-mansion-mania.de/) (MMM) fan project: episode and related catalog rows, distribution links, and engine hints. The machine-readable catalog is **`data/entries/<catalog_id>.json`** (one file per row, generated from `source/mmm_catalog.csv`).

**Planning:** lives in [mmm-system-design](https://github.com/selloa/mmm-system-design).

**Public read API (hosted):** https://mmm-api-production-7f5a.up.railway.app — OpenAPI at `/docs`, browse index at `/v1/entries`, full row at `/v1/entries/{catalog_id}` ([mmm-api](https://github.com/selloa/mmm-api) repo; deployment tracks the git ref in its `build/catalog-data-ref.txt`, currently **`v0.2.0`** of this repo). **Example UI:** [mmm-api-viewer](https://github.com/selloa/mmm-api-viewer) (GitHub Pages MMM API Viewer).

**Katalog-Webseite:** https://selloa.github.io/mmm-data/ — static browse UI built from `source/mmm_catalog.csv` ([Deploy Site](.github/workflows/deploy-site.yml) on push to `main`).

**Purpose:** a **versioned canonical catalog** of MMM works (episodes, collections, fan games, and related rows). Later you can add more datasets and schemas beside the catalog without changing this core idea.

**What belongs here (v1):** `schema/` (JSON Schema), `source/` (authoring CSV), `data/entries/` (generated JSON, one object per file), `tools/` (encode + validate), `requirements.txt`, and `docs/` (human semantics). **Not** required on day one: a public website or mirror automation—**read access** is also available via the **public API** above in addition to raw GitHub files.

**Build:** from this directory, after a one-time `python -m pip install -r requirements.txt`, run `python tools/build_catalog.py`. That encodes `source/mmm_catalog.csv` into `data/entries/*.json` and validates every file against `schema/mmm-catalog-entry.v1.schema.json`. Exit code `0` means the export matches the v1 contract.

**CI:** on every push and pull request to `main`, [GitHub Actions](.github/workflows/catalog-ci.yml) runs the same `build_catalog.py` step on Ubuntu and fails the job if the working tree would change (for example CSV updated but regenerated `data/entries/` not committed).

**Consuming:** each **`data/entries/<catalog_id>.json`** file is one catalog entry (v1 schema). Example raw URL (branch `main`):  
[https://raw.githubusercontent.com/selloa/mmm-data/main/data/entries/EP-001.json](https://raw.githubusercontent.com/selloa/mmm-data/main/data/entries/EP-001.json)  

Browse all entry files: [data/entries on `main`](https://github.com/selloa/mmm-data/tree/main/data/entries). For stable links, pin a **commit** or **tag** instead of `main` in the URL. The current release version is also recorded in [`VERSION`](VERSION) (matches git tags like `v0.2.2`).

Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md).

Field meanings and validation in plain language: `docs/CATALOG_ENTRY_v1.md`.

**License:** [MIT](LICENSE) (see file for full text).
