#!/usr/bin/env python3
"""Fail closed unless an Asphalt ReXtreme build satisfies the 1.0 RC release gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


EXPECTED_IDENTITY = {
    "Name": "ReXtreme.AsphaltXtreme",
    "Publisher": "CN=ReXtreme",
    "Version": "1.0.0.0",
    "ProcessorArchitecture": "x86",
}

FORBIDDEN_CAPABILITIES = {
    "internetClient",
    "internetClientServer",
    "privateNetworkClientServer",
    "location",
}


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise GateError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_stage(stage: Path, patch_manifest_path: Path) -> list[str]:
    notes: list[str] = []
    build = read_json(stage / "ReXtremeBuild.json")

    if not build.get("release_eligible"):
        raise GateError("ReXtremeBuild.json says release_eligible=false")

    xml_data = build.get("xml_data") or {}
    if not xml_data.get("applied"):
        raise GateError("Premium/offline XML data was not applied")

    manifest_path = stage / "AppxManifest.xml"
    if not manifest_path.is_file():
        raise GateError("AppxManifest.xml is missing from stage")

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    identity = next((n for n in root.iter() if lname(n.tag) == "Identity"), None)
    if identity is None:
        raise GateError("AppxManifest.xml has no Identity")

    for key, expected in EXPECTED_IDENTITY.items():
        actual = identity.attrib.get(key)
        if actual != expected:
            raise GateError(f"Identity {key}: expected {expected!r}, got {actual!r}")

    declared_caps = {
        n.attrib.get("Name", "")
        for n in root.iter()
        if lname(n.tag) in {"Capability", "DeviceCapability"}
    }
    bad = sorted(FORBIDDEN_CAPABILITIES & declared_caps)
    if bad:
        raise GateError("Forbidden online/location capabilities remain: " + ", ".join(bad))

    patch_manifest = read_json(patch_manifest_path)
    expected_by_path = {
        item["path"]: item.get("patched_sha256") or item["sha256"]
        for item in patch_manifest["files"]
    }

    for rel, expected_hash in expected_by_path.items():
        target = stage / rel
        if not target.is_file():
            raise GateError(f"Critical file missing: {rel}")
        actual = sha256_file(target)
        if actual.lower() != expected_hash.lower():
            raise GateError(
                f"Critical hash mismatch for {rel}: expected {expected_hash}, got {actual}"
            )
        notes.append(f"hash ok: {rel}")

    config = stage / "ReXtreme.ini"
    if not config.is_file():
        raise GateError("ReXtreme.ini is missing")
    config_text = config.read_text(encoding="utf-8-sig")
    required_config = {
        "OfflineMode=1",
        "VehiclePriceMultiplier=0.80",
        "PremiumCurrencyRaceMultiplier=0.50",
        "FullRepeatRewards=1",
        "DisableDiminishingReturns=1",
        "DisableDailyRewardCaps=1",
        "DisableRaceRewardCooldowns=1",
        "RequireOfflineCareerCompletable=1",
    }
    missing_config = sorted(v for v in required_config if v not in config_text)
    if missing_config:
        raise GateError("Required config values missing: " + ", ".join(missing_config))

    notes.append("stage identity/capabilities/config ok")
    return notes


def check_payload(payload: Path) -> list[str]:
    notes: list[str] = []
    install = read_json(payload / "install-manifest.json")

    if not install.get("releaseEligible"):
        raise GateError("Installer payload says releaseEligible=false")

    dependency = install.get("dependency")
    if not dependency:
        raise GateError("VC120 dependency is not bundled in the installer payload")

    for key, hash_key in (
        ("package", "packageSha256"),
        ("certificate", "certificateSha256"),
        ("dependency", "dependencySha256"),
    ):
        name = install.get(key)
        expected = install.get(hash_key)
        if not name or not expected:
            raise GateError(f"Payload manifest lacks {key}/{hash_key}")
        target = payload / name
        if not target.is_file():
            raise GateError(f"Payload file missing: {name}")
        actual = sha256_file(target)
        if actual.lower() != str(expected).lower():
            raise GateError(f"Payload SHA-256 mismatch: {name}")
        notes.append(f"payload hash ok: {name}")

    dependency_path = payload / dependency
    if not dependency_path.is_file():
        raise GateError(f"Bundled dependency missing: {dependency}")

    lower_name = dependency.lower()
    if not lower_name.startswith("microsoft.vclibs.120.00_"):
        raise GateError("Bundled dependency is not Microsoft.VCLibs.120.00")
    if "_x86__8wekyb3d8bbwe.appx" not in lower_name:
        raise GateError("Bundled VC120 dependency is not the expected x86 Microsoft package")

    notes.append("installer payload ok")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=Path)
    ap.add_argument(
        "--patch-manifest",
        type=Path,
        default=Path("patches/1.7.3.8-x86.json"),
    )
    ap.add_argument("--payload", type=Path)
    args = ap.parse_args()

    try:
        notes = check_stage(args.stage.resolve(), args.patch_manifest.resolve())
        if args.payload:
            notes.extend(check_payload(args.payload.resolve()))
    except (GateError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"RELEASE GATE: FAIL\n{exc}", file=sys.stderr)
        return 1

    print("RELEASE GATE: PASS")
    for note in notes:
        print(f"  - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
