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
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from tools import (
        audit_offline_data,
        make_premium_shop,
        patcher,
        repack_xmlbin,
        xtea_assets,
    )
except ModuleNotFoundError:  # direct script execution from tools/
    import audit_offline_data
    import make_premium_shop
    import patcher
    import repack_xmlbin
    import xtea_assets


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


def derive_baseline_plaintext(xml_bin: Path, out_dir: Path) -> Path:
    """Derive only the data that has a deterministic public transform.

    The source remains the user's own xml.bin. No decrypted game data is
    checked into the repository.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = {
        "xml/asphaltshop.xtea": out_dir / "asphaltshop.xml",
    }

    with zipfile.ZipFile(xml_bin) as archive:
        names = set(archive.namelist())
        missing = sorted(set(wanted) - names)
        if missing:
            raise RuntimeError(
                "xml.bin lacks required baseline entries: " + ", ".join(missing)
            )

        for entry, destination in wanted.items():
            try:
                payload, _meta = xtea_assets.decode_stream(archive.read(entry))
            except xtea_assets.DecodeError as exc:
                raise RuntimeError(f"Could not decode {entry}: {exc}") from exc
            destination.write_bytes(payload)

    return out_dir


def load_override_manifest(plaintext_dir: Path) -> dict:
    manifest_path = plaintext_dir / "rextreme-overrides.json"
    if not manifest_path.is_file():
        return {
            "approved": False,
            "reason": "rextreme-overrides.json is missing",
            "files": [],
        }

    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if data.get("schema") != 1:
        raise RuntimeError("unsupported ReXtreme override manifest schema")
    if data.get("target_build") != "1.7.3.8-x86":
        raise RuntimeError("override manifest targets a different game build")
    if not isinstance(data.get("files"), list):
        raise RuntimeError("override manifest must contain a files array")

    verified: list[dict] = []
    for item in data["files"]:
        filename = str(item.get("file", "")).strip()
        entry = str(item.get("entry", "")).replace("\\", "/").strip()
        expected_hash = str(item.get("sha256", "")).lower().strip()

        if not filename or not entry or not expected_hash:
            raise RuntimeError("override manifest file records require file/entry/sha256")
        if "/" in filename or "\\" in filename:
            raise RuntimeError(f"override filename must be a basename: {filename}")
        if not entry.startswith("xml/") or not entry.endswith(".xtea"):
            raise RuntimeError(f"invalid override xml.bin entry: {entry}")

        source = plaintext_dir / filename
        if not source.is_file():
            raise RuntimeError(f"approved override file is missing: {filename}")

        actual_hash = sha256_file(source)
        if actual_hash.lower() != expected_hash:
            raise RuntimeError(
                f"override hash mismatch for {filename}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

        verified.append(
            {
                "file": filename,
                "entry": entry,
                "sha256": actual_hash,
                "purpose": str(item.get("purpose", "")).strip(),
                "source": source,
            }
        )

    approved = bool(data.get("approved_for_release")) and bool(verified)
    return {
        "approved": approved,
        "reason": None if approved else "override manifest is not approved for release",
        "files": verified,
    }


def apply_xml_data(stage: Path, plaintext_dir: Path | None) -> dict:
    xml_bin = stage / "data" / "xml.bin"
    hdr = stage / "data" / "xml.bin.hdr"
    if not xml_bin.is_file() or not hdr.is_file():
        raise RuntimeError("stage is missing data/xml.bin or data/xml.bin.hdr")

    with tempfile.TemporaryDirectory(prefix="rextreme-xml-") as tmp_raw:
        tmp = Path(tmp_raw)
        baseline_dir = derive_baseline_plaintext(
            xml_bin,
            tmp / "derived-baseline",
        )

        replacements: dict[str, Path] = {}
        transforms: list[dict] = []
        override_meta = {
            "approved": False,
            "reason": "no approved private override directory supplied",
            "files": [],
        }

        # Baseline Premium transform is always derived from the user's own source.
        shop_source = baseline_dir / "asphaltshop.xml"

        if plaintext_dir is not None:
            plaintext_dir = plaintext_dir.resolve()
            if not plaintext_dir.is_dir():
                raise RuntimeError(f"XML plaintext directory not found: {plaintext_dir}")

            override_meta = load_override_manifest(plaintext_dir)

            # Diagnostic/unapproved directories may still be used locally, but they
            # never make the build release-eligible.
            if override_meta["files"]:
                override_items = override_meta["files"]
            else:
                override_items = [
                    {
                        "file": p.name,
                        "entry": entry_name_for_plaintext(p),
                        "sha256": sha256_file(p),
                        "purpose": "unapproved diagnostic override",
                        "source": p,
                    }
                    for p in plaintext_dir.iterdir()
                    if p.is_file()
                    and p.name != "rextreme-overrides.json"
                    and p.suffix.lower() in {".xml", ".json"}
                ]

            for item in override_items:
                src = item["source"]
                entry = item["entry"]
                if Path(item["file"]).stem.lower() == "asphaltshop":
                    shop_source = src
                    continue

                out = tmp / ("override-" + Path(item["file"]).name)
                shutil.copy2(src, out)
                replacements[entry] = out
                transforms.append(
                    {
                        "entry": entry,
                        "transform": "approved_plaintext_override"
                            if override_meta["approved"]
                            else "diagnostic_plaintext_override",
                        "sha256": item["sha256"],
                        "purpose": item.get("purpose", ""),
                    }
                )

        shop_out = tmp / "patched-asphaltshop.xml"
        shop_report = make_premium_shop.transform_file(
            shop_source,
            shop_out,
            report_path=tmp / "asphaltshop.report.json",
            vehicle_multiplier=0.80,
        )
        replacements["xml/asphaltshop.xtea"] = shop_out
        transforms.insert(
            0,
            {
                "entry": "xml/asphaltshop.xtea",
                "transform": "premium_vehicle_prices_80pct",
                "report": shop_report,
            },
        )

        header = repack_xmlbin.parse_hdr(hdr)
        original_problems = repack_xmlbin.verify(xml_bin, header)
        if original_problems:
            raise RuntimeError(
                "Original xml.bin does not match xml.bin.hdr: "
                + "; ".join(original_problems)
            )

        rebuilt = tmp / "xml.bin"
        repack_xmlbin.rebuild(xml_bin, rebuilt, replacements)
        layout_problems = repack_xmlbin.verify(rebuilt, header)

        if layout_problems or rebuilt.stat().st_size != xml_bin.stat().st_size:
            raise RuntimeError(
                "Rebuilt xml.bin is not HDR-compatible: "
                + "; ".join(layout_problems)
            )

        shutil.copy2(rebuilt, xml_bin)

    release_eligible = bool(override_meta["approved"])
    final = {
        "applied": True,
        "baseline_premium_applied": True,
        "release_eligible": release_eligible,
        "plaintext_origin": (
            "approved-private-overrides"
            if release_eligible
            else "auto-derived-baseline-plus-diagnostic-overrides"
            if plaintext_dir is not None
            else "auto-derived-from-user-source"
        ),
        "override_manifest": {
            "approved": bool(override_meta["approved"]),
            "reason": override_meta.get("reason"),
            "verified_files": [
                {
                    "file": item["file"],
                    "entry": item["entry"],
                    "sha256": item["sha256"],
                    "purpose": item.get("purpose", ""),
                }
                for item in override_meta.get("files", [])
            ],
        },
        "replacement_count": len(replacements),
        "transforms": transforms,
        "xmlbin_sha256": sha256_file(xml_bin),
    }

    if not release_eligible:
        final["reason"] = (
            "Premium baseline was applied, but no hash-verified "
            "rextreme-overrides.json approved for release was supplied"
        )

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
    offline_audit: dict,
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
        "offline_audit": {
            "decoded_xtea_entries": offline_audit.get("decoded_xtea_entries", 0),
            "text_entries": offline_audit.get("text_entries", 0),
            "candidate_entries": offline_audit.get("candidate_entries", 0),
            "category_totals": offline_audit.get("category_totals", {}),
            "report": "ReXtreme/offline-data-audit.json",
        },
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

        print("[1/8] Copying full source tree...")
        copy_source(source, stage)

        print("[2/8] Applying verified binary patches...")
        patch_results = apply_verified_patches(stage, manifest)

        print("[3/8] Applying Premium/offline XML data...")
        plaintext_dir = resolve_xml_plaintext_dir(source, args.xml_plaintext_dir)
        xml_data = apply_xml_data(stage, plaintext_dir)
        if not xml_data["applied"]:
            print("[WARN] Premium XML data was not applied; build is not 1.0-release eligible.")

        print("[4/8] Auditing remaining offline/service data...")
        offline_audit = audit_offline_data.audit(stage / "data" / "xml.bin")
        report_dir = stage / "ReXtreme"
        report_dir.mkdir(exist_ok=True)
        (report_dir / "offline-data-audit.json").write_text(
            json.dumps(offline_audit, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print("[5/8] Rewriting package identity...")
        manifest_info = rewrite_manifest(stage / "AppxManifest.xml")

        print("[6/8] Installing ReXtreme configuration...")
        shutil.copy2(config_path, stage / "ReXtreme.ini")

        print("[7/8] Applying optional branding overlay...")
        overlay_branding(stage, args.branding_dir.resolve() if args.branding_dir else None)

        print("[8/8] Writing build metadata...")
        write_build_metadata(
            stage,
            source,
            manifest_info,
            patch_results,
            xml_data,
            offline_audit,
        )

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
