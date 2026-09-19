#!/usr/bin/env python3
"""
Asphalt ReXtreme - local build inventory / string triage.

Usage:
    python tools/analyze_build.py "C:\\path\\to\\extracted\\Asphalt Xtreme"

This tool does NOT modify game files. It creates a report containing:
- file inventory and SHA-256 hashes
- AppxManifest identity / executable
- PE candidates (.exe/.dll)
- URLs/domains and strings related to ads, online services, economy and graphics
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KEYWORDS = (
    "http", "https", "gameloft", "server", "online", "offline", "login",
    "auth", "telemetry", "analytics", "advert", "ads", "rewarded", "video",
    "purchase", "iap", "store", "currency", "credit", "token", "cash",
    "coin", "upgrade", "unlock", "energy", "fuel", "garage", "car",
    "fov", "fieldofview", "resolution", "fullscreen", "vsync", "fps",
    "framerate", "xbox", "controller", "xinput",
)

ASCII_RE = re.compile(rb"[\x20-\x7e]{5,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){5,}")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
DOMAIN_RE = re.compile(r"(?<![\w.-])(?:[a-z0-9-]+\.)+(?:com|net|org|io|gg|co|tv|me|cloud|games|game)(?![\w.-])", re.I)

MAX_SCAN_FILE = 256 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_strings(path: Path) -> list[str]:
    if path.stat().st_size > MAX_SCAN_FILE:
        return []
    data = path.read_bytes()
    out: list[str] = []
    out.extend(m.group().decode("ascii", "ignore") for m in ASCII_RE.finditer(data))
    out.extend(m.group().decode("utf-16le", "ignore") for m in UTF16_RE.finditer(data))
    return out


def interesting_strings(strings: list[str]) -> list[str]:
    seen = set()
    hits = []
    for s in strings:
        low = s.lower()
        if any(k in low for k in KEYWORDS):
            normalized = s.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                hits.append(normalized)
    return hits[:2000]


def parse_manifest(path: Path) -> dict:
    result = {}
    try:
        root = ET.parse(path).getroot()
        ident = next((x for x in root.iter() if x.tag.endswith("Identity")), None)
        if ident is not None:
            result["identity"] = dict(ident.attrib)
        apps = []
        for app in root.iter():
            if app.tag.endswith("Application"):
                apps.append(dict(app.attrib))
        result["applications"] = apps
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("analysis-output"))
    args = ap.parse_args()

    root = args.game_dir.resolve()
    out = args.out.resolve()
    if not root.is_dir():
        print(f"Game directory not found: {root}", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    inventory = []
    manifests = []
    string_report = {}
    urls = set()
    domains = set()

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        try:
            item = {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            inventory.append(item)

            if path.name.lower() == "appxmanifest.xml":
                manifests.append({"path": rel, "data": parse_manifest(path)})

            if path.suffix.lower() in {".exe", ".dll", ".xml", ".json", ".ini", ".cfg", ".txt", ".bin"}:
                strings = extract_strings(path)
                hits = interesting_strings(strings)
                if hits:
                    string_report[rel] = hits
                for s in strings:
                    urls.update(URL_RE.findall(s))
                    domains.update(DOMAIN_RE.findall(s))
        except Exception as exc:
            inventory.append({"path": rel, "error": str(exc)})

    report = {
        "root": str(root),
        "files": inventory,
        "manifests": manifests,
        "urls": sorted(urls),
        "domains": sorted(domains),
        "interesting_strings": string_report,
    }

    (out / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    with (out / "summary.txt").open("w", encoding="utf-8") as f:
        f.write(f"Root: {root}\n")
        f.write(f"Files: {len(inventory)}\n\n")
        f.write("Manifests:\n")
        for m in manifests:
            f.write(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
        f.write("\nURLs:\n")
        for u in sorted(urls):
            f.write(u + "\n")
        f.write("\nDomains:\n")
        for d in sorted(domains):
            f.write(d + "\n")
        f.write("\nFiles with interesting strings:\n")
        for rel, hits in string_report.items():
            f.write(f"\n[{rel}]\n")
            for s in hits[:200]:
                f.write(s + "\n")

    print(f"Wrote: {out / 'build-report.json'}")
    print(f"Wrote: {out / 'summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
