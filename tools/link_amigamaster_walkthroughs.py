#!/usr/bin/env python3
"""Link catalog rows to AmigaMaster Simple-Game-Solutions walkthrough markdown files."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from csv_to_catalog_json import CANONICAL_FIELDS
from scrape_walkthrough_content import read_catalog, write_catalog

REPO = "AmigaMaster/Simple-Game-Solutions"
BRANCH = "master"
BLOB_BASE = f"https://github.com/{REPO}/blob/{BRANCH}"

EP_FILE_RE = re.compile(
    r"Maniac Mansion Mania Episode (\d+) - (.+)-DE\.md$", re.IGNORECASE
)
HS_FILE_RE = re.compile(
    r"Maniac Mansion Mania Halloween (\d+)-(\d+) - (.+)-DE\.md$", re.IGNORECASE
)
MH_FILE_RE = re.compile(
    r"Maniac Mansion Mania Meteorhead (\d+)(?: - .+)?-DE\.md$", re.IGNORECASE
)
TE_FILE_RE = re.compile(
    r"Maniac Mansion Mania Trash - (.+)-DE\.md$", re.IGNORECASE
)
MM_FILE_RE = re.compile(
    r"Maniac Mansion Mania Mini Masterpiece #(\d+) - .+-DE\.md$", re.IGNORECASE
)
EA_FILE_RE = re.compile(
    r"Maniac Mansion Mania Staffel (\d+) Edgar Award-DE\.md$", re.IGNORECASE
)


def _fix_repo_path_encoding(path: str) -> str:
    """Repair UTF-8 mojibake from gh CLI on Windows (e.g. ä → Ã¤)."""
    try:
        return path.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return path


def blob_url(repo_path: str) -> str:
    fixed = _fix_repo_path_encoding(repo_path)
    return f"{BLOB_BASE}/{urllib.parse.quote(fixed, safe='/')}"


def fetch_mmm_markdown_paths() -> list[str]:
    out = subprocess.check_output(
        [
            "gh",
            "api",
            f"repos/{REPO}/git/trees/{BRANCH}?recursive=1",
            "-q",
            ".tree[].path",
        ],
        text=True,
    )
    paths: list[str] = []
    for line in out.splitlines():
        p = line.strip()
        if not p.endswith(".md"):
            continue
        if "Maniac Mansion Mania" in p or "Maniac Dungeon" in p:
            paths.append(p)
    return paths


def _basename(path: str) -> str:
    return Path(path).name


class MmmIndexes:
    def __init__(self, paths: list[str]) -> None:
        self.episodes: dict[int, str] = {}
        self.episode_066_akt3: str | None = None
        self.halloween: dict[tuple[int, int], str] = {}
        self.meteorhead: dict[int, str] = {}
        self.trash: dict[str, str] = {}
        self.trash_by_te_id: dict[str, str] = {}
        self.mini: dict[int, str] = {}
        self.edgar: dict[int, str] = {}
        self.md_all_rooms: str | None = None
        self.md7: str | None = None
        self.christmas_odyssey: str | None = None
        self.three_days: str | None = None
        self.ronville_viper: str | None = None
        self.demo_experiment: str | None = None
        self.demo_textadventure: str | None = None
        self.easter: dict[int, str] = {}

        for path in paths:
            name = _basename(path)
            m = EP_FILE_RE.search(name)
            if m:
                n = int(m.group(1))
                subtitle = m.group(2)
                if n == 66 and "akt 3" in subtitle.lower():
                    self.episode_066_akt3 = path
                    continue
                if "directors cut" in subtitle.lower():
                    continue
                if subtitle.rstrip().endswith("V3"):
                    continue
                self.episodes[n] = path
                continue

            m = HS_FILE_RE.search(name)
            if m:
                self.halloween[(int(m.group(1)), int(m.group(2)))] = path
                continue

            m = MH_FILE_RE.search(name)
            if m:
                self.meteorhead[int(m.group(1))] = path
                continue

            m = TE_FILE_RE.search(name)
            if m:
                key = _ascii_fold(_norm_key(m.group(1)))
                self.trash[key] = path
                continue

            m = MM_FILE_RE.search(name)
            if m:
                self.mini[int(m.group(1))] = path
                continue

            m = EA_FILE_RE.search(name)
            if m:
                self.edgar[int(m.group(1))] = path
                continue

            if name.startswith("Maniac Dungeon - Alle") and name.endswith("ume-DE.md"):
                self.md_all_rooms = path
            elif name.startswith("Maniac Dungeon 7 -"):
                self.md7 = path
            elif "Christmas Odyssey" in name:
                self.christmas_odyssey = path
            elif "Three Days Before Christmas" in name:
                self.three_days = path
            elif name.endswith("Ronville Viper-DE.md"):
                self.ronville_viper = path
            elif "Demo - Das Experiment" in name:
                self.demo_experiment = path
            elif "Demo - Das Textadventure" in name:
                self.demo_textadventure = path
            elif "Ostereiersuche 2010" in name:
                self.easter[2010] = path
            elif "Ostereiersuche 2011" in name:
                self.easter[2011] = path
            elif "Ostereiersuche 2018" in name:
                self.easter[2018] = path

        self.trash_by_te_id = _index_trash_by_te_id(paths)


def _norm_key(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


TE_TRASH_PATH_MARKERS: dict[str, tuple[str, ...]] = {
    "TE-001": ("Trash -", "jahrsputz"),
    "TE-002": ("Trash -", "der Futanaris-DE"),
    "TE-003": ("Trash -", "Futanaris 2"),
    "TE-004": ("Trash -", "Futanaris 3"),
    "TE-005": ("Trash -", "Futanaris 4"),
    "TE-006": ("Trash -", "No GUI"),
    "TE-007": ("Trash -", "Iasons Testepisode"),
    "TE-008": ("Trash -", "F--king Vista"),
    "TE-009": ("Trash -", "Rettet Sandy"),
    "TE-010": ("Trash -", "MMM-Million", "r-DE.md"),
    "TE-011": ("Trash -", "rotes Tentakel"),
    "TE-012": ("Trash -", "Run Hoagie Run"),
    "TE-013": ("Trash -", "Bernard muss mahl-DE"),
    "TE-014": ("Trash -", "Bernard muss 2 mahl"),
    "TE-015": ("Trash -", "Vol. II"),
    "TE-016": ("Trash -", "Trash-Million"),
    "TE-017": ("Trash -", "Bloody Halloween"),
    "TE-018": ("Trash -", "Bernard muss 3 mahl"),
    "TE-019": ("Trash -", "Bernard muss 4 mahl"),
    "TE-020": ("Trash -", "Britney muss mahl"),
    "TE-024": ("Trash -", "Traumepisode"),
}


def _index_trash_by_te_id(paths: list[str]) -> dict[str, str]:
    trash_paths = [p for p in paths if " Trash - " in p]
    out: dict[str, str] = {}
    for te_id, markers in TE_TRASH_PATH_MARKERS.items():
        for path in trash_paths:
            if all(m in path for m in markers):
                out[te_id] = path
                break
    return out


def _ascii_fold(s: str) -> str:
    for a, b in (
        ("ä", "a"),
        ("ö", "o"),
        ("ü", "u"),
        ("ß", "ss"),
        ("é", "e"),
    ):
        s = s.replace(a, b)
    return s


def _hs_catalog_order() -> list[tuple[int, int]]:
    return [
        (2005, 1),
        (2005, 2),
        (2005, 3),
        (2005, 4),
        (2005, 5),
        (2006, 1),
        (2006, 2),
        (2010, 1),
        (2010, 2),
        (2010, 3),
        (2010, 4),
        (2011, 1),
    ]


def _edgar_staffel_num(catalog_id: str) -> int | None:
    n = int(catalog_id[3:])
    if n == 3:
        return None
    if n <= 2:
        return n
    return n - 1


def map_row(row: dict[str, str], idx: MmmIndexes) -> str | None:
    cid = row["catalog_id"]
    cat = row["category"]
    title = row["title"]

    if cid.startswith("EP-"):
        n = int(cid[3:])
        path = idx.episodes.get(n)
        return blob_url(path) if path else None

    if cid.startswith("HS-"):
        n = int(cid[3:])
        keys = _hs_catalog_order()
        if 1 <= n <= len(keys):
            path = idx.halloween.get(keys[n - 1])
            return blob_url(path) if path else None
        return None

    if cid.startswith("MH-"):
        n = int(cid[3:])
        path = idx.meteorhead.get(n)
        return blob_url(path) if path else None

    if cid.startswith("TE-"):
        if cid == "TE-022":
            path = idx.episode_066_akt3
            return blob_url(path) if path else None
        if cid == "TE-023":
            path = idx.md7
            return blob_url(path) if path else None
        path = idx.trash_by_te_id.get(cid)
        return blob_url(path) if path else None

    if cid.startswith("MD-"):
        path = idx.md_all_rooms
        return blob_url(path) if path else None

    if cid.startswith("EA-"):
        staffel = _edgar_staffel_num(cid)
        if staffel is None:
            return None
        path = idx.edgar.get(staffel)
        return blob_url(path) if path else None

    if cid.startswith("XS-"):
        n = int(cid[3:])
        path = idx.mini.get(n)
        return blob_url(path) if path else None

    if cid.startswith("FS-"):
        year = {"FS-001": 2010, "FS-002": 2011, "FS-003": 2018}.get(cid)
        if year:
            path = idx.easter.get(year)
            return blob_url(path) if path else None
        return None

    if cid.startswith("XC-"):
        if cid in ("XC-001", "XC-003") and idx.christmas_odyssey:
            return blob_url(idx.christmas_odyssey)
        if cid in ("XC-002", "XC-004") and idx.three_days:
            return blob_url(idx.three_days)
        return None

    if cid == "HL-001" and idx.ronville_viper:
        return blob_url(idx.ronville_viper)

    if cid == "TD-005" and idx.demo_experiment:
        return blob_url(idx.demo_experiment)
    if cid == "TD-007" and idx.demo_textadventure:
        return blob_url(idx.demo_textadventure)

    return None


def apply_links(
    csv_path: Path,
    *,
    only_empty: bool = True,
) -> tuple[int, list[str]]:
    paths = fetch_mmm_markdown_paths()
    print(f"fetched {len(paths)} MMM markdown paths from GitHub")
    idx = MmmIndexes(paths)

    rows = read_catalog(csv_path)
    updated = 0
    unmatched: list[str] = []

    for row in rows:
        cid = row["catalog_id"]
        url = map_row(row, idx)
        if not url:
            unmatched.append(cid)
            continue
        if only_empty and (row.get("walkthrough_url_amigamaster") or "").strip():
            continue
        if row.get("walkthrough_url_amigamaster", "").strip() != url:
            row["walkthrough_url_amigamaster"] = url
            updated += 1

    write_catalog(csv_path, rows)
    matched = sum(1 for r in rows if (r.get("walkthrough_url_amigamaster") or "").strip())
    print(f"set walkthrough_url_amigamaster on {updated} rows ({matched} total with URL)")
    return updated, unmatched


def add_csv_column(csv_path: Path) -> bool:
    """Insert walkthrough_url_amigamaster into CSV if missing. Returns True if changed."""
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        text = f.read()
    import csv as csv_mod

    reader = csv_mod.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ValueError("missing header")
    header = [h.strip() for h in reader.fieldnames if h]
    if "walkthrough_url_amigamaster" in header:
        return False

    rows_in = list(reader)
    rows_out: list[dict[str, str]] = []
    for raw in rows_in:
        row = {k: (raw.get(k) or "") for k in header}
        row["walkthrough_url_amigamaster"] = ""
        rows_out.append(row)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv_mod.DictWriter(
            f, fieldnames=CANONICAL_FIELDS, quoting=csv_mod.QUOTE_MINIMAL
        )
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in CANONICAL_FIELDS} for r in rows_out)
    print(f"added column walkthrough_url_amigamaster to {csv_path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing walkthrough_url_amigamaster values",
    )
    args = parser.parse_args()

    add_csv_column(args.csv)
    updated, unmatched = apply_links(args.csv, only_empty=not args.force)

    if unmatched:
        print(f"no AmigaMaster walkthrough ({len(unmatched)} rows):", file=sys.stderr)
        for cid in unmatched:
            if cid.startswith(("FM-", "FG-", "CO-", "TD-")) or cid in (
                "TE-021",
                "MH-012",
                "EA-003",
            ):
                continue
            print(f"  {cid}", file=sys.stderr)

    return 0 if updated >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
