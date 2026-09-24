#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

EXPECTED = {
    # name: (magic, version, require_nonzero, required)
    "CampaignCatalog.dat":      (0x54435852, 1, True,  True),
    "CampaignEvents.dat":       (0x45435852, 1, True,  True),
    "CampaignObjectives.dat":   (0x4F435852, 1, True,  False),
    "CampaignUpgrades.dat":     (0x55435852, 2, True,  True),
    # Beta compatibility: a zero-entry UI map is a deliberate fail-closed
    # state. Upgrade actions are intercepted and rejected locally until the
    # real legacy raw-id mapping is reconstructed.
    "CampaignUpgradeUiMap.dat": (0x4D555852, 1, False, True),
    "CampaignStore.dat":        (0x53535852, 1, False, True),
}

def read_header(path: Path):
    data = path.read_bytes()
    if len(data) < 20:
        return None
    magic, version, count, reserved = struct.unpack_from("<4I", data, 0)
    return {
        "magic": magic,
        "version": version,
        "count": count,
        "reserved": reserved,
        "size": len(data),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ns = ap.parse_args()

    pkg = ns.package.resolve()
    report = {"package": str(pkg), "files": {}, "blocking": []}

    for name, (magic, version, require_nonzero, required) in EXPECTED.items():
        p = pkg / name
        row = {"exists": p.is_file()}
        if not p.is_file():
            row["required"] = required
            if required:
                report["blocking"].append(f"{name} missing")
            report["files"][name] = row
            continue

        hdr = read_header(p)
        row["header"] = hdr
        if hdr is None:
            report["blocking"].append(f"{name} too small/corrupt")
        else:
            if hdr["magic"] != magic:
                report["blocking"].append(
                    f"{name} magic mismatch: 0x{hdr['magic']:08X}"
                )
            if hdr["version"] != version:
                report["blocking"].append(
                    f"{name} version mismatch: {hdr['version']} != {version}"
                )
            if require_nonzero and hdr["count"] == 0:
                report["blocking"].append(f"{name} has zero entries")
        report["files"][name] = row

    report["ready"] = not report["blocking"]
    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
