#!/usr/bin/env python3
"""Find original Asphalt Xtreme settings/UI resources for ReXtreme reuse.

The report is discovery-only. It does not assert that a found resource is safe
to bind. Final bindings require runtime/UI call-site verification.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from audit_presentation_capabilities import (
    find_xrefs,
    iter_ascii_strings,
    iter_utf16le_strings,
    parse_pe,
    raw_to_rva,
    sha256,
)

try:
    from xtea_assets import decode_stream, DecodeError
except ImportError:
    decode_stream = None
    DecodeError = Exception

UI_KEYWORDS = (
    "settings", "options", "graphics", "video", "display", "camera", "audio",
    "controls", "slider", "toggle", "checkbox", "button", "popup", "dialog",
    "resolution", "fullscreen", "vsync", "quality", "shadow", "texture",
    "fov", "replay", "photo", "hud", "pause", "resume", "back", "apply",
    "accept", "cancel", "restore", "default", "screen", "panel", "list",
    "tab", "label", "text", "menu", "item", "widget", "container",
)

SCAN_SUFFIXES = {
    ".exe", ".dll", ".xml", ".json", ".txt", ".ini", ".cfg", ".csv",
    ".bin", ".xtea", ".lua", ".dat",
}


def keyword_hits(text: str) -> list[str]:
    low = text.lower()
    return sorted({k for k in UI_KEYWORDS if k in low})


def scan_blob(
    blob: bytes,
    source: str,
    limit: int = 500,
    image_base: int | None = None,
    sections=None,
) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    for encoding, iterator in (
        ("ascii", iter_ascii_strings(blob, 4)),
        ("utf16le", iter_utf16le_strings(blob, 4)),
    ):
        for offset, text in iterator:
            hits = keyword_hits(text)
            if not hits:
                continue
            key = (encoding, offset, text)
            if key in seen:
                continue
            seen.add(key)
            rva = raw_to_rva(offset, sections) if sections else None
            va = image_base + rva if image_base is not None and rva is not None else None
            xref_raw = find_xrefs(blob, va, sections) if va is not None and sections else []
            xref_rvas = [
                x
                for raw in xref_raw
                if (x := raw_to_rva(raw, sections)) is not None
            ]
            rows.append({
                "source": source,
                "encoding": encoding,
                "offset": offset,
                "rva": rva,
                "va": va,
                "xref_raw_offsets": xref_raw,
                "xref_rvas": xref_rvas,
                "xref_count": len(xref_raw),
                "text": text[:260],
                "keywords": hits,
                "status": "candidate-only",
            })
            if len(rows) >= limit:
                return rows
    return rows


def scan_regular_file(path: Path, root: Path) -> list[dict]:
    rel = path.relative_to(root).as_posix()
    rows: list[dict] = []

    name_hits = keyword_hits(rel)
    if name_hits:
        rows.append({
            "source": rel,
            "encoding": "filename",
            "offset": None,
            "text": rel,
            "keywords": name_hits,
            "status": "candidate-only",
        })

    try:
        data = path.read_bytes()
    except OSError:
        return rows

    if path.suffix.lower() == ".xtea" and decode_stream is not None:
        try:
            data, meta = decode_stream(data)
            source = rel + " [decoded-xtea]"
            rows.extend(scan_blob(data, source))
            return rows
        except Exception:
            pass

    pe_info = parse_pe(data)
    if pe_info:
        image_base, sections = pe_info
        rows.extend(scan_blob(data, rel, image_base=image_base, sections=sections))
    else:
        rows.extend(scan_blob(data, rel))
    return rows


def scan_archive(path: Path, root: Path) -> list[dict]:
    rel = path.relative_to(root).as_posix()
    rows: list[dict] = []

    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                entry_source = f"{rel}::{info.filename}"
                hits = keyword_hits(info.filename)
                if hits:
                    rows.append({
                        "source": entry_source,
                        "encoding": "archive-entry-name",
                        "offset": None,
                        "text": info.filename,
                        "keywords": hits,
                        "status": "candidate-only",
                    })

                suffix = Path(info.filename).suffix.lower()
                if suffix not in SCAN_SUFFIXES:
                    continue

                try:
                    data = zf.read(info)
                except (OSError, RuntimeError, KeyError):
                    continue

                if suffix == ".xtea" and decode_stream is not None:
                    try:
                        data, _ = decode_stream(data)
                        entry_source += " [decoded-xtea]"
                    except Exception:
                        continue

                rows.extend(scan_blob(data, entry_source, limit=200))
    except (OSError, zipfile.BadZipFile):
        return rows

    return rows


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit original Asphalt Xtreme settings UI resources for exact ReXtreme reuse"
    )
    ap.add_argument("game_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("original-settings-ui-audit.json"))
    ns = ap.parse_args()

    root = ns.game_dir.resolve()
    if not root.is_dir():
        ap.error(f"not a game directory: {root}")

    rows: list[dict] = []
    files_scanned = 0
    archives_scanned = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files_scanned += 1

        try:
            if zipfile.is_zipfile(path):
                archives_scanned += 1
                rows.extend(scan_archive(path, root))
                continue
        except OSError:
            pass

        if path.suffix.lower() in SCAN_SUFFIXES:
            rows.extend(scan_regular_file(path, root))

    rows.sort(
        key=lambda x: (
            -int(x.get("xref_count", 0)),
            x["source"],
            x["offset"] if x["offset"] is not None else -1,
        )
    )

    by_keyword: dict[str, int] = {}
    with_xrefs = 0
    for row in rows:
        if row.get("xref_count", 0):
            with_xrefs += 1
        for k in row["keywords"]:
            by_keyword[k] = by_keyword.get(k, 0) + 1

    report = {
        "format": "rextreme-original-settings-ui-audit",
        "version": 1,
        "game_dir": str(root),
        "rule": (
            "All rows are discovery candidates. ReXtreme in-game settings UI must bind only "
            "resources/components verified to belong to the original Asphalt Xtreme UI."
        ),
        "verified_bindings": [],
        "summary": {
            "files_seen": files_scanned,
            "archives_scanned": archives_scanned,
            "candidate_rows": len(rows),
            "candidate_rows_with_x86_xrefs": with_xrefs,
            "by_keyword": dict(sorted(by_keyword.items())),
        },
        "candidates": rows,
    }

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {ns.out}")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
