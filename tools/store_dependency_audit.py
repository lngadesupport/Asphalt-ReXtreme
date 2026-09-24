#!/usr/bin/env python3
"""Audit an extracted Asphalt Xtreme build for Microsoft Store/UWP coupling.

Read-only. No files are modified. The report is intended to drive the
Campaign Edition Win32 separation work.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

CATEGORIES = {
    "store_iap": [
        "windows.applicationmodel.store", "windows.services.store",
        "currentapp", "currentappsimulator", "storecontext",
        "ms-windows-store:", "inapppurchase", "iapcomponent",
    ],
    "package_identity": [
        "appxmanifest.xml", "appxsignature.p7x", "appxblockmap.xml",
        "packagefamilyname", "packagefullname", "packagemanager",
        "package.current", "appusermodelid", "add-appxpackage",
        "windows.applicationmodel.package",
    ],
    "xbox_microsoft_auth": [
        "xboxlive", "xbox live", "microsoft account", "msa",
        "microsoft.live", "liveconnect", "signin", "sign-in",
    ],
    "uwp_activation": [
        "windows.applicationmodel.activation", "coreapplication",
        "applicationview", "windows.ui.core", "roactivateinstance",
        "windows.foundation",
    ],
    "gameloft_services": [
        "iap.gameloft.com", "secure.gameloft.com", "eve.gameloft.com",
        "gameoptions.gameloft.com", "201205igp.gameloft.com",
        "scripts/ad_rewards/", "scripts/credits/", "scripts/energy/",
    ],
}

PACKAGE_FILES = {
    "appxmanifest.xml", "appxsignature.p7x", "appxblockmap.xml",
    "[content_types].xml",
}

SCAN_SUFFIXES = {
    ".exe", ".dll", ".winmd", ".xml", ".json", ".ini", ".cfg", ".txt",
    ".js", ".html", ".dat", ".bin",
}


def strings_from_bytes(data: bytes, min_len: int = 5):
    ascii_re = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    utf16_re = re.compile(rb"(?:[\x20-\x7e]\x00){%d,}" % min_len)
    for m in ascii_re.finditer(data):
        yield m.group().decode("ascii", "ignore")
    for m in utf16_re.finditer(data):
        yield m.group()[::2].decode("ascii", "ignore")


def scan_file(path: Path, root: Path):
    rel = path.relative_to(root).as_posix()
    findings = []
    name_lower = path.name.lower()

    if name_lower in PACKAGE_FILES:
        findings.append({
            "category": "package_identity",
            "term": name_lower,
            "source": "package-file",
        })

    if path.suffix.lower() not in SCAN_SUFFIXES and not findings:
        return findings

    try:
        data = path.read_bytes()
    except OSError as exc:
        return [{"category": "read_error", "term": str(exc), "source": "io"}]

    # Limit pathological files while still scanning binaries/assets likely to contain imports/URLs.
    if len(data) > 256 * 1024 * 1024:
        data = data[:64 * 1024 * 1024]

    seen = set()
    for s in strings_from_bytes(data):
        low = s.lower()
        for category, terms in CATEGORIES.items():
            for term in terms:
                if term in low:
                    key = (category, term)
                    if key not in seen:
                        seen.add(key)
                        findings.append({
                            "category": category,
                            "term": term,
                            "source": "string",
                        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir", type=Path)
    ap.add_argument("--json", dest="json_path", type=Path)
    ap.add_argument("--markdown", dest="md_path", type=Path)
    ap.add_argument("--strict", action="store_true",
                    help="return non-zero when Microsoft Store/package blockers remain")
    args = ap.parse_args()

    root = args.game_dir.resolve()
    if not root.is_dir():
        raise SystemExit(f"Game directory not found: {root}")

    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        for finding in scan_file(path, root):
            rows.append({
                "file": path.relative_to(root).as_posix(),
                **finding,
            })

    counts = Counter(r["category"] for r in rows)
    microsoft_blockers = sum(
        counts[k] for k in ("store_iap", "package_identity", "xbox_microsoft_auth")
    )

    report = {
        "root": str(root),
        "files_scanned": sum(1 for p in root.rglob("*") if p.is_file()),
        "finding_count": len(rows),
        "microsoft_blocker_count": microsoft_blockers,
        "counts": dict(sorted(counts.items())),
        "findings": rows,
    }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    if args.md_path:
        lines = [
            "# Microsoft/Store dependency audit",
            "",
            f"- Files scanned: {report['files_scanned']}",
            f"- Findings: {len(rows)}",
            f"- Microsoft blockers: {microsoft_blockers}",
            "",
            "## Counts",
            "",
        ]
        for k, v in sorted(counts.items()):
            lines.append(f"- `{k}`: {v}")
        lines += ["", "## Findings", "", "| File | Category | Term |", "|---|---|---|"]
        for r in rows:
            f = r["file"].replace("|", "\\|")
            lines.append(f"| `{f}` | `{r['category']}` | `{r['term']}` |")
        args.md_path.parent.mkdir(parents=True, exist_ok=True)
        args.md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.strict and microsoft_blockers:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
