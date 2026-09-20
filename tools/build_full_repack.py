#!/usr/bin/env python3
"""
Build a clean Asphalt ReXtreme 1.0 RC staging tree from a verified
Asphalt Xtreme 1.7.3.8 x86 source directory.

This tool does not redistribute proprietary game content. It transforms
a user-provided local source into a new staging directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import patcher


DROP_ROOT_FILES = {
    "AppxSignature.p7x",
    "AppxBlockMap.xml",
    "[Content_Types].xml",
}

STRIP_CAPABILITIES = {
    "internetClient",
    "internetClientServer",
    "privateNetworkClientServer",
    "location",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def copy_source(source: Path, stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)

    def ignore(path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        if Path(path).resolve() == source.resolve():
            ignored |= DROP_ROOT_FILES.intersection(names)
        ignored |= {n for n in names if n.endswith(".rex.bak")}
        return ignored

    shutil.copytree(source, stage, ignore=ignore)


def rewrite_manifest(manifest_path: Path) -> dict:
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    identity = next((x for x in root.iter() if lname(x.tag) == "Identity"), None)
    if identity is None:
        raise RuntimeError("AppxManifest.xml has no Identity element")

    old = dict(identity.attrib)
    identity.set("Name", "ReXtreme.AsphaltXtreme")
    identity.set("Publisher", "CN=ReXtreme")
    identity.set("Version", "1.0.0.0")
    if "ProcessorArchitecture" not in identity.attrib:
        identity.set("ProcessorArchitecture", "x86")

    for node in root.iter():
        local = lname(node.tag)
        if local == "DisplayName":
            node.text = "Asphalt ReXtreme"
        elif local == "PublisherDisplayName":
            node.text = "ReXtreme"
        elif local == "Description":
            node.text = "Asphalt ReXtreme Offline Edition"

        if local in {"VisualElements", "Application"}:
            if "DisplayName" in node.attrib:
                node.set("DisplayName", "Asphalt ReXtreme")
            if "Description" in node.attrib:
                node.set("Description", "Asphalt ReXtreme Offline Edition")

    removed_caps: list[str] = []
    for parent in list(root.iter()):
        if lname(parent.tag) != "Capabilities":
            continue
        for child in list(parent):
            name = child.attrib.get("Name", "")
            if name in STRIP_CAPABILITIES:
                parent.remove(child)
                removed_caps.append(name)

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    return {"old_identity": old, "removed_capabilities": sorted(set(removed_caps))}


def apply_verified_patches(stage: Path, manifest: dict) -> list[dict]:
    results: list[dict] = []
    for entry in manifest["files"]:
        target = stage / entry["path"]
        if not target.is_file():
            raise RuntimeError(f"Required source file missing: {entry['path']}")
        patcher.apply_file_patches(
            target,
            entry,
            dry_run=False,
            create_backup=False,
        )
        results.append(
            {
                "path": entry["path"],
                "sha256": sha256_file(target),
                "patched": bool(entry.get("patches")),
            }
        )
    return results


def overlay_branding(stage: Path, branding_dir: Path | None) -> None:
    if branding_dir is None:
        return
    if not branding_dir.is_dir():
        raise RuntimeError(f"Branding directory not found: {branding_dir}")
    for src in branding_dir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(branding_dir)
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def write_build_metadata(
    stage: Path,
    source: Path,
    manifest_info: dict,
    patch_results: list[dict],
) -> None:
    data = {
        "product": "Asphalt ReXtreme Offline Edition",
        "rextreme_version": "1.0.0-rc1",
        "package_identity": {
            "name": "ReXtreme.AsphaltXtreme",
            "publisher": "CN=ReXtreme",
            "version": "1.0.0.0",
            "architecture": "x86",
        },
        "source": {
            "path": str(source),
            "target_game_version": "1.7.3.8",
        },
        "manifest_transform": manifest_info,
        "critical_files": patch_results,
        "built_utc": datetime.now(timezone.utc).isoformat(),
    }
    (stage / "ReXtremeBuild.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, help="Extracted legitimate 1.7.3.8 x86 source")
    ap.add_argument("stage", type=Path, help="Output staging directory")
    ap.add_argument(
        "--patch-manifest",
        type=Path,
        default=Path("patches/1.7.3.8-x86.json"),
    )
    ap.add_argument(
        "--config",
        type=Path,
        default=Path("config/ReXtreme-1.0.ini"),
    )
    ap.add_argument(
        "--branding-dir",
        type=Path,
        default=None,
        help="Optional overlay tree containing ReXtreme assets at package-relative paths",
    )
    args = ap.parse_args()

    source = args.source.resolve()
    stage = args.stage.resolve()
    patch_manifest_path = args.patch_manifest.resolve()
    config_path = args.config.resolve()

    try:
        if not source.is_dir():
            raise RuntimeError(f"Source directory not found: {source}")
        if not (source / "AppxManifest.xml").is_file():
            raise RuntimeError("Source is missing AppxManifest.xml")
        if not patch_manifest_path.is_file():
            raise RuntimeError(f"Patch manifest not found: {patch_manifest_path}")
        if not config_path.is_file():
            raise RuntimeError(f"Config not found: {config_path}")

        manifest = patcher.load_manifest(patch_manifest_path)

        print("[1/6] Copying full source tree...")
        copy_source(source, stage)

        print("[2/6] Applying verified binary patches...")
        patch_results = apply_verified_patches(stage, manifest)

        print("[3/6] Rewriting package identity...")
        manifest_info = rewrite_manifest(stage / "AppxManifest.xml")

        print("[4/6] Installing ReXtreme configuration...")
        shutil.copy2(config_path, stage / "ReXtreme.ini")

        print("[5/6] Applying optional branding overlay...")
        overlay_branding(stage, args.branding_dir.resolve() if args.branding_dir else None)

        print("[6/6] Writing build metadata...")
        write_build_metadata(stage, source, manifest_info, patch_results)

        print(f"RC1 staging tree ready: {stage}")
        return 0
    except (RuntimeError, patcher.PatchError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
