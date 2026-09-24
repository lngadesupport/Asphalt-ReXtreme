#!/usr/bin/env python3
"""Audit Asphalt Xtreme presentation capabilities without inventing features.

This tool is intentionally evidence-first. A string such as "motion_blur" is
reported only as a candidate. It is NOT promoted to a supported ReXtreme option
until a caller/config path and runtime behavior are verified.

It scans PE binaries for ASCII/UTF-16 strings and x86 absolute references to
those strings, and scans text/config files for matching keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

KEYWORDS: dict[str, tuple[str, ...]] = {
    "display": (
        "resolution", "fullscreen", "full screen", "borderless", "windowed",
        "refresh rate", "refresh_rate", "vsync", "vertical sync", "frame rate",
        "framerate", "fps limit", "fps_limit",
    ),
    "quality": (
        "texture quality", "texture_quality", "shadow quality", "shadow_quality",
        "reflection", "particle", "terrain", "vegetation", "draw distance",
        "draw_distance", "lod", "anisotropic", "anisotropy", "anti-alias",
        "antialias", "msaa", "fxaa", "bloom", "motion blur", "motion_blur",
        "depth of field", "depth_of_field", "dof",
    ),
    "camera": (
        "fov", "field of view", "field_of_view", "camera distance",
        "camera_distance", "camera height", "camera_height", "camera shake",
        "camera_shake", "camera smoothing", "camera_smoothing",
    ),
    "replay_photo": (
        "replay", "photo mode", "photo_mode", "free camera", "free_camera",
        "screenshot", "frame step", "frame_step",
    ),
    "ui": (
        "graphics", "video settings", "video_settings", "display settings",
        "display_settings", "camera settings", "camera_settings", "options",
        "settings",
    ),
}

BINARY_SUFFIXES = {".exe", ".dll"}
TEXT_SUFFIXES = {".ini", ".cfg", ".json", ".xml", ".txt", ".lua", ".csv"}


@dataclass
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int


@dataclass
class Evidence:
    file: str
    category: str
    keyword: str
    text: str
    encoding: str
    raw_offset: int | None
    rva: int | None
    va: int | None
    xref_raw_offsets: list[int]
    status: str = "candidate-only"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pe(data: bytes) -> tuple[int, list[Section]] | None:
    if len(data) < 0x100 or data[:2] != b"MZ":
        return None
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 0x18 >= len(data) or data[pe:pe + 4] != b"PE\0\0":
        return None
    num_sections = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    if opt + opt_size > len(data):
        return None
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic != 0x10B:  # PE32/x86 target
        return None
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    section_table = opt + opt_size
    sections: list[Section] = []
    for i in range(num_sections):
        off = section_table + i * 40
        if off + 40 > len(data):
            break
        raw_name = data[off:off + 8].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, off + 8)
        sections.append(Section(name, virtual_address, virtual_size, raw_offset, raw_size))
    return image_base, sections


def raw_to_rva(raw: int, sections: Iterable[Section]) -> int | None:
    for s in sections:
        if s.raw_offset <= raw < s.raw_offset + s.raw_size:
            return s.virtual_address + (raw - s.raw_offset)
    return None


def iter_ascii_strings(data: bytes, min_len: int = 4):
    start = None
    for i, b in enumerate(data):
        printable = 32 <= b <= 126 or b in (9,)
        if printable:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_len:
                yield start, data[start:i].decode("ascii", errors="ignore")
            start = None
    if start is not None and len(data) - start >= min_len:
        yield start, data[start:].decode("ascii", errors="ignore")


def iter_utf16le_strings(data: bytes, min_len: int = 4):
    i = 0
    n = len(data)
    while i + 1 < n:
        start = i
        chars: list[int] = []
        while i + 1 < n:
            code = data[i] | (data[i + 1] << 8)
            if 32 <= code <= 126 or code == 9:
                chars.append(code)
                i += 2
            else:
                break
        if len(chars) >= min_len:
            yield start, "".join(chr(c) for c in chars)
        i = max(i + 2, start + 2)


def classify(text: str) -> list[tuple[str, str]]:
    low = text.lower()
    out: list[tuple[str, str]] = []
    for category, words in KEYWORDS.items():
        for word in words:
            if word in low:
                out.append((category, word))
    return out


def find_xrefs(data: bytes, value: int, sections: list[Section], max_hits: int = 32) -> list[int]:
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    text_ranges = [
        (s.raw_offset, min(len(data), s.raw_offset + s.raw_size))
        for s in sections
        if s.name == ".text"
    ]
    if not text_ranges:
        text_ranges = [(0, len(data))]

    hits: list[int] = []
    for begin, end in text_ranges:
        pos = begin
        while len(hits) < max_hits:
            idx = data.find(needle, pos, end)
            if idx < 0:
                break
            hits.append(idx)
            pos = idx + 1
    return hits


def audit_binary(path: Path, root: Path) -> tuple[dict, list[Evidence]]:
    data = path.read_bytes()
    pe_info = parse_pe(data)
    image_base = None
    sections: list[Section] = []
    if pe_info:
        image_base, sections = pe_info

    evidence: list[Evidence] = []
    seen: set[tuple[int, str, str]] = set()

    for encoding, iterator in (
        ("ascii", iter_ascii_strings(data)),
        ("utf16le", iter_utf16le_strings(data)),
    ):
        for raw, text in iterator:
            matches = classify(text)
            if not matches:
                continue

            rva = raw_to_rva(raw, sections) if sections else None
            va = (image_base + rva) if image_base is not None and rva is not None else None
            xrefs: list[int] = []
            if va is not None:
                xrefs = find_xrefs(data, va, sections)

            for category, keyword in matches:
                key = (raw, category, keyword)
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(Evidence(
                    file=path.relative_to(root).as_posix(),
                    category=category,
                    keyword=keyword,
                    text=text[:240],
                    encoding=encoding,
                    raw_offset=raw,
                    rva=rva,
                    va=va,
                    xref_raw_offsets=xrefs,
                ))

    info = {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256(path),
        "size": len(data),
        "pe32": bool(pe_info),
        "image_base": image_base,
        "sections": [asdict(s) for s in sections],
    }
    return info, evidence


def audit_text(path: Path, root: Path) -> list[Evidence]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    evidence: list[Evidence] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        matches = classify(line)
        for category, keyword in matches:
            evidence.append(Evidence(
                file=path.relative_to(root).as_posix(),
                category=category,
                keyword=keyword,
                text=f"L{line_no}: {line[:220]}",
                encoding="text",
                raw_offset=None,
                rva=None,
                va=None,
                xref_raw_offsets=[],
                status="config-or-text-candidate",
            ))
    return evidence


def find_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in BINARY_SUFFIXES or suffix in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit real graphics/camera/replay/UI evidence in an Asphalt Xtreme installation"
    )
    ap.add_argument("input", type=Path, help="AMS.exe, DLL, or game directory")
    ap.add_argument("--out", type=Path, default=Path("presentation-capability-audit.json"))
    args = ap.parse_args()

    root = args.input.resolve()
    if not root.exists():
        ap.error(f"input does not exist: {root}")

    logical_root = root if root.is_dir() else root.parent
    binaries: list[dict] = []
    evidence: list[Evidence] = []

    for path in find_inputs(root):
        if path.suffix.lower() in BINARY_SUFFIXES:
            try:
                info, hits = audit_binary(path, logical_root)
                binaries.append(info)
                evidence.extend(hits)
            except (OSError, struct.error, ValueError) as exc:
                binaries.append({
                    "path": path.relative_to(logical_root).as_posix(),
                    "error": str(exc),
                })
        elif path.suffix.lower() in TEXT_SUFFIXES:
            evidence.extend(audit_text(path, logical_root))

    evidence.sort(key=lambda x: (x.category, x.file, x.raw_offset or -1, x.keyword))

    category_counts: dict[str, int] = {}
    xref_candidates = 0
    for item in evidence:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
        if item.xref_raw_offsets:
            xref_candidates += 1

    report = {
        "format": "rextreme-presentation-capability-audit",
        "version": 1,
        "input": str(root),
        "rule": (
            "Evidence in this report is candidate-only. No graphics/camera/replay option "
            "is considered supported until its runtime read/write path and behavior are verified."
        ),
        "confirmed_capabilities": [],
        "summary": {
            "files_scanned": len(find_inputs(root)),
            "binary_files": len(binaries),
            "evidence_count": len(evidence),
            "evidence_with_x86_absolute_xrefs": xref_candidates,
            "by_category": category_counts,
        },
        "binaries": binaries,
        "evidence": [asdict(e) for e in evidence],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {args.out}")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
