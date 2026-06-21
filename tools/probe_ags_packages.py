#!/usr/bin/env python3
"""Probe release archives for AGS layout/version without full extraction."""

from __future__ import annotations

import csv
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SEVEN_Z = Path(r"C:\Program Files\7-Zip\7z.exe")
MIRROR = Path(r"C:\mmm\mmm-local\mmm-mirror-poc-7k3xq-zips")
CSV_PATH = Path(__file__).resolve().parents[1] / "source" / "mmm_catalog.csv"

# Catalog rows we filled in the recent mirror download batch (+ FS-001 test).
NEW_IDS = {
    "FS-001",
    "FS-002",
    "FS-003",
    "MH-001",
    "MH-002",
    "MH-003",
    "MH-004",
    "MH-005",
    "MH-006",
    "MH-007",
    "MH-008",
    "MH-009",
    "MH-010",
    "MH-011",
    "MH-013",
    "MH-014",
    "MH-015",
    "MH-016",
    "FG-001",
    "EP-000",
    "FG-002",
    "FG-003",
    "FG-004",
    "FG-005",
    "FG-006",
    "FG-007",
    "FG-008",
    "FG-009",
    "FG-010",
    "FG-011",
    "FG-012",
    "FM-001",
    "FM-002",
    "FM-003",
    "FM-004",
    "FM-005",
    "FM-006",
    "FM-007",
    "FM-008",
    "EA-001",
    "EA-002",
    "EA-003",
    "EA-004",
    "EA-005",
    "EA-006",
    "EA-007",
    "EA-008",
    "EA-009",
    "EA-010",
    "TE-001",
    "TE-002",
    "TE-003",
    "TE-004",
    "TE-005",
    "TE-006",
    "TE-007",
    "TE-008",
    "TE-009",
    "TE-010",
    "TE-011",
    "TE-012",
    "TE-013",
    "TE-014",
    "TE-015",
    "TE-016",
    "TE-017",
    "TE-018",
    "TE-019",
    "TE-020",
    "TE-021",
    "TE-023",
    "TE-024",
    "TD-001",
    "TD-002",
    "TD-003",
    "TD-004",
    "TD-005",
    "TD-006",
    "TD-007",
    "TD-008",
    "TD-009",
    "TD-010",
    "TD-011",
    "TD-012",
    "TD-013",
    "TD-014",
}

AGS_MARKERS = frozenset(
    {
        "acsetup.cfg",
        "ac2game.dat",
        "acgame.dat",
        "game.ags",
        "ags.inf",
    }
)
AGS_EXE_HINTS = re.compile(r"(?:^|/)(?:game|acwin|ags\d+|ags)\.exe$", re.I)
# AGS embeds runtime version strings far into the main game exe (often >2 MiB).
EXE_PROBE_MAX_BYTES = 12_000_000
VERSION_PATTERNS = [
    re.compile(rb"ACI version (\d+\.\d+\.\d+(?:\.\d+)?)", re.I),
    re.compile(
        rb"(?:AGS\s+v?|Adventure Game Studio v?|Compiled with AGS v?)(\d+\.\d+\.\d+(?:\.\d+)?)",
        re.I,
    ),
]
# Runtime version embedded without the "ACI version" prefix (older/custom exe names).
LEGACY_RUNTIME_VERSION_RE = re.compile(
    rb"\b(2\.(?:5\d|6\d|7\d|80|81|82|70)\.\d{3,4}|3\.\d{1,2}\.\d{4}(?:\.\d+)?)\b"
)
FOUR_PART_RUNTIME_VERSION_RE = re.compile(rb"\b([23]\.\d{1,2}\.\d{1,2}\.\d{1,4})\b")
_FALSE_VERSIONS = frozenset({"1.0.0.0", "6.6.6.6", "9.9.9.9", "0.0.0.0"})


@dataclass
class ProbeResult:
    catalog_id: str
    filename: str
    is_ags: bool | None  # None = could not inspect
    ags_version: str | None
    layout: str  # root | subfolder:<path> | nested | n/a | unknown
    notes: str


def norm_arc_path(name: str) -> str:
    return name.replace("\\", "/")


def list_archive(archive: Path) -> list[str]:
    suffix = archive.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            return [norm_arc_path(n) for n in zf.namelist() if not n.endswith("/")]
    if suffix in {".rar", ".7z"}:
        proc = subprocess.run(
            [str(SEVEN_Z), "l", "-slt", str(archive)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"7z list failed: {archive.name}")
        paths: list[str] = []
        current = ""
        for line in proc.stdout.splitlines():
            if line.startswith("Path = "):
                current = norm_arc_path(line[7:])
            elif line == "" and current:
                if not current.endswith("/"):
                    paths.append(current)
                current = ""
        if current and not current.endswith("/"):
            paths.append(current)
        return paths
    if suffix == ".exe":
        return [archive.name]
    return []


def read_member(archive: Path, member: str, max_bytes: int = 2_000_000) -> bytes:
    suffix = archive.suffix.lower()
    member = norm_arc_path(member)
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(archive) as zf:
                with zf.open(member) as f:
                    return f.read(max_bytes)
        except (NotImplementedError, OSError, zipfile.BadZipFile):
            pass
    proc = subprocess.run(
        [str(SEVEN_Z), "e", "-so", str(archive), member],
        capture_output=True,
        check=False,
    )
    # 7z e -so does not support a byte limit; trim after read.
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:200])
    return proc.stdout[:max_bytes]


def find_version_in_blob(data: bytes) -> str | None:
    for pat in VERSION_PATTERNS:
        for m in pat.finditer(data):
            ver = m.group(1).decode("ascii", "ignore")
            if ver not in _FALSE_VERSIONS:
                return ver
    m = LEGACY_RUNTIME_VERSION_RE.search(data)
    if m:
        ver = m.group(1).decode("ascii", "ignore")
        if ver not in _FALSE_VERSIONS:
            return ver
    m = FOUR_PART_RUNTIME_VERSION_RE.search(data)
    if m:
        ver = m.group(1).decode("ascii", "ignore")
        if ver not in _FALSE_VERSIONS:
            return ver
    return None


def game_homes(paths: list[str]) -> list[str]:
    """Return posix directory paths that look like an AGS game root."""
    homes: set[str] = set()
    for p in paths:
        base = PurePosixPath(p).name.lower()
        if base not in AGS_MARKERS:
            continue
        parent = str(PurePosixPath(p).parent)
        homes.add("" if parent == "." else parent)
    for p in paths:
        if AGS_EXE_HINTS.search(p):
            parent = str(PurePosixPath(p).parent)
            # exe alone is weak; require a marker sibling in same dir
            prefix = "" if parent == "." else parent + "/"
            if any(
                PurePosixPath(x).name.lower() in AGS_MARKERS
                and (str(PurePosixPath(x).parent) == parent or (parent == "" and "/" not in x))
                for x in paths
            ):
                homes.add("" if parent == "." else parent)
    return sorted(homes, key=lambda h: (h.count("/"), len(h)))


def classify_layout(homes: list[str]) -> str:
    if not homes:
        return "unknown"
    if len(homes) > 1:
        return f"nested ({len(homes)} candidates)"
    home = homes[0]
    return "root" if home == "" else f"subfolder:{home}"


def probe_archive(catalog_id: str, archive: Path) -> ProbeResult:
    fn = archive.name
    try:
        paths = list_archive(archive)
    except Exception as e:
        return ProbeResult(catalog_id, fn, None, None, "unknown", f"list failed: {e}")

    if archive.suffix.lower() == ".exe":
        try:
            data = archive.read_bytes()[:4_000_000]
        except OSError as e:
            return ProbeResult(catalog_id, fn, None, None, "n/a", str(e))
        ver = find_version_in_blob(data)
        is_ags = bool(ver) or b"acsetup.cfg" in data or b"ac2game.dat" in data
        layout = "root (standalone exe)" if is_ags else "n/a"
        return ProbeResult(
            catalog_id,
            fn,
            is_ags,
            ver,
            layout,
            "standalone executable",
        )

    homes = game_homes(paths)
    if not homes:
        from collections import Counter

        exts = Counter(PurePosixPath(p).suffix.lower() for p in paths[:200])
        top = ", ".join(f"{k}:{v}" for k, v in exts.most_common(4))
        return ProbeResult(catalog_id, fn, False, None, "n/a", f"no AGS markers ({top})")

    layout = classify_layout(homes)
    home = homes[0]
    prefix = "" if home == "" else home + "/"

    version: str | None = None
    notes: list[str] = []

    # Prefer small text/binary probes inside the detected game home.
    candidates: list[str] = []
    for p in paths:
        rel = p[len(prefix) :] if prefix and p.startswith(prefix) else (p if not prefix else "")
        if prefix and not p.startswith(prefix):
            continue
        name = PurePosixPath(p).name.lower()
        if name in ("acsetup.cfg", "ags.inf"):
            candidates.append(p)
        elif name in ("ac2game.dat", "game.ags", "acgame.dat"):
            candidates.append(p)
        elif AGS_EXE_HINTS.search(p) and "winsetup.exe" not in p.lower():
            candidates.append(p)

    for member in candidates:
        try:
            blob = read_member(archive, member, max_bytes=1_500_000)
        except Exception:
            continue
        ver = find_version_in_blob(blob)
        if not ver and member.lower().endswith((".dat", ".ags")):
            # Legacy ac2game.dat: int32 little-endian data version sometimes near start
            ver = find_version_in_blob(blob[:4096])
        if ver:
            version = ver
            notes.append(f"from {PurePosixPath(member).name}")
            break

    if not version:
        # Scan any exe under home (skip launcher stubs)
        exe_members = [
            p
            for p in paths
            if p.startswith(prefix)
            and p.lower().endswith(".exe")
            and "winsetup.exe" not in p.lower()
        ]
        for member in exe_members:
            try:
                blob = read_member(archive, member, max_bytes=EXE_PROBE_MAX_BYTES)
            except Exception:
                continue
            ver = find_version_in_blob(blob)
            if ver:
                version = ver
                notes.append(f"from {PurePosixPath(member).name}")
                break

    return ProbeResult(
        catalog_id,
        fn,
        True,
        version,
        layout,
        "; ".join(notes) if notes else "AGS markers found, version not in scanned files",
    )


def layout_to_subpath(layout: str) -> str:
    if layout.startswith("subfolder:"):
        return layout.split(":", 1)[1]
    return ""


def probe_rows(rows: list[dict[str, str]]) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    for row in rows:
        fn = row["release_package_filename"].strip()
        archive = MIRROR / fn
        if not archive.is_file():
            results.append(
                ProbeResult(row["catalog_id"], fn, None, None, "unknown", "file missing")
            )
            continue
        results.append(probe_archive(row["catalog_id"], archive))
    return results


def apply_probe_to_catalog(
    catalog_path: Path, results: list[ProbeResult], *, ids: set[str]
) -> int:
    from csv_to_catalog_json import CANONICAL_FIELDS

    by_id = {r.catalog_id: r for r in results}
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError(f"{catalog_path}: empty catalog")

    updated = 0
    for row in rows:
        cid = row.get("catalog_id", "")
        if cid not in ids or cid not in by_id:
            continue
        probe = by_id[cid]
        if probe.is_ags is False:
            row["engine"] = "unknown"
            row["engine_version"] = ""
            row["game_files_subpath"] = ""
            updated += 1
            continue
        if probe.is_ags is not True:
            continue
        row["engine"] = "AGS"
        if probe.ags_version:
            row["engine_version"] = probe.ags_version
        row["game_files_subpath"] = layout_to_subpath(probe.layout)
        updated += 1

    with catalog_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in CANONICAL_FIELDS} for row in rows)

    return updated


def rows_missing_engine_version(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if (row.get("engine") or "").strip() != "AGS":
            continue
        if (row.get("engine_version") or "").strip():
            continue
        fn = (row.get("release_package_filename") or "").strip()
        if not fn:
            continue
        out.append(row)
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply-csv",
        action="store_true",
        help="Write engine, engine_version, game_files_subpath for probed rows",
    )
    parser.add_argument(
        "--missing-versions",
        action="store_true",
        help="probe catalog rows with engine=AGS and empty engine_version",
    )
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    args = parser.parse_args()

    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))

    if args.missing_versions:
        target_rows = rows_missing_engine_version(all_rows)
        target_ids = {r["catalog_id"] for r in target_rows}
    else:
        target_rows = [r for r in all_rows if r["catalog_id"] in NEW_IDS]
        target_ids = NEW_IDS

    target_rows.sort(key=lambda r: r["catalog_id"])
    results = probe_rows(target_rows)

    if args.apply_csv:
        n = apply_probe_to_catalog(args.csv, results, ids=target_ids)
        filled = sum(1 for r in results if r.ags_version)
        print(f"Updated {n} catalog row(s); {filled} with engine_version in {args.csv}")
        return 0

    ags = [r for r in results if r.is_ags is True]
    non = [r for r in results if r.is_ags is False]
    unk = [r for r in results if r.is_ags is None]

    print(f"Probed {len(results)} new packages")
    print(f"AGS: {len(ags)} | Not AGS: {len(non)} | Uninspectable: {len(unk)}")
    print()
    print("catalog_id\tags\tversion\tlayout\tnotes")
    for r in results:
        ags_s = "?" if r.is_ags is None else ("yes" if r.is_ags else "no")
        print(
            f"{r.catalog_id}\t{ags_s}\t{r.ags_version or '-'}\t{r.layout}\t{r.notes}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
