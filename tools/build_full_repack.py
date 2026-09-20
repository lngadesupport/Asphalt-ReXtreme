#!/usr/bin/env python3
"""
Build a clean Asphalt ReXtreme 1.0 RC staging tree from a verified
Asphalt Xtreme 1.7.3.8 x86 source directory.

The public tool transforms a user-provided local source. Proprietary game
payload and decrypted game data are never required in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import make_premium_shop
import patcher
import repack_xmlbin


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


def resolve_xml_plaintext_dir(source: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.resolve()

    env = os.environ.get("REXTREME_XML_PLAINTEXT_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    conventional = source.parent / "ReXtremeOverrides" / "xml"
    if conventional.is_dir():
        return conventional.resolve()

    return None


def entry_name_for_plaintext(path: Path) -> str:
    return f"xml/{path.stem}.xtea"


def apply_xml_data(stage: Path, plaintext_dir: Path | None) -> dict:
    if plaintext_dir is None:
        return {
            "applied": False,
            "release_eligible": False,
            "reason": "no private XML plaintext directory supplied",
        }
    if not plaintext_dir.is_dir():
        raise RuntimeError(f"XML plaintext directory not found: {plaintext_dir}")

    xml_bin = stage / "data" / "xml.bin"
    hdr = stage / "data" / "xml.bin.hdr"
    if not xml_bin.is_file() or not hdr.is_file():
        raise RuntimeError("stage is missing data/xml.bin or data/xml.bin.hdr")

    originals = [
        p for p in plaintext_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".xml", ".json"}
    ]
    if not originals:
        raise RuntimeError(f"No XML/JSON plaintext files found in {plaintext_dir}")

    with tempfile.TemporaryDirectory(prefix="rextreme-xml-") as tmp_raw:
        tmp = Path(tmp_raw)
        replacements: dict[str, Path] = {}
        transforms: list[dict] = []

        for src in originals:
            out = tmp / src.name
            if src.stem.lower() == "asphaltshop":
                report_path = tmp / "asphaltshop.report.json"
                report = make_premium_shop.transform_file(
                    src,
                    out,
                    report_path=report_path,
                    vehicle_multiplier=0.80,
                )
                transforms.append(
                    {
                        "entry": entry_name_for_plaintext(src),
                        "transform": "premium_vehicle_prices_80pct",
                        "report": report,
                    }
                )
            else:
                shutil.copy2(src, out)
                transforms.append(
                    {
                        "entry": entry_name_for_plaintext(src),
                        "transform": "approved_plaintext_override",
                    }
                )
            replacements[entry_name_for_plaintext(src)] = out

        header = repack_xmlbin.parse_hdr(hdr)
        original_problems = repack_xmlbin.verify(xml_bin, header)
        if original_problems:
            raise RuntimeError(
                "Original xml.bin does not match xml.bin.hdr: "
                + "; ".join(original_problems)
            )

        rebuilt = tmp / "xml.bin"
        report = repack_xmlbin.rebuild(xml_bin, rebuilt, replacements)
        layout_problems = repack_xmlbin.verify(rebuilt, header)

        if layout_problems or rebuilt.stat().st_size != xml_bin.stat().st_size:
            raise RuntimeError(
                "Rebuilt xml.bin is not HDR-compatible: "
                + "; ".join(layout_problems)
            )

        shutil.copy2(rebuilt, xml_bin)

    final = {
        "applied": True,
        "release_eligible": True,
        "plaintext_source": str(plaintext_dir),
        "replacement_count": len(replacements),
        "transforms": transforms,
        "xmlbin_sha256": sha256_file(xml_bin),
    }

    report_dir = stage / "ReXtreme"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "xml-data-report.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return final


def write_build_metadata(
    stage: Path,
    source: Path,
    manifest_info: dict,
    patch_results: list[dict],
    xml_data: dict,
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
        "xml_data": xml_data,
        "release_eligible": bool(xml_data.get("release_eligible")),
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
    ap.add_argument(
        "--xml-plaintext-dir",
        type=Path,
        default=None,
        help="Private plaintext XML/JSON derived from the user's supported source",
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

        print("[1/7] Copying full source tree...")
        copy_source(source, stage)

        print("[2/7] Applying verified binary patches...")
        patch_results = apply_verified_patches(stage, manifest)

        print("[3/7] Applying Premium/offline XML data...")
        plaintext_dir = resolve_xml_plaintext_dir(source, args.xml_plaintext_dir)
        xml_data = apply_xml_data(stage, plaintext_dir)
        if not xml_data["applied"]:
            print("[WARN] Premium XML data was not applied; build is not 1.0-release eligible.")

        print("[4/7] Rewriting package identity...")
        manifest_info = rewrite_manifest(stage / "AppxManifest.xml")

        print("[5/7] Installing ReXtreme configuration...")
        shutil.copy2(config_path, stage / "ReXtreme.ini")

        print("[6/7] Applying optional branding overlay...")
        overlay_branding(stage, args.branding_dir.resolve() if args.branding_dir else None)

        print("[7/7] Writing build metadata...")
        write_build_metadata(stage, source, manifest_info, patch_results, xml_data)

        print(f"RC1 staging tree ready: {stage}")
        return 0
    except (
        RuntimeError,
        patcher.PatchError,
        repack_xmlbin.RepackError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
