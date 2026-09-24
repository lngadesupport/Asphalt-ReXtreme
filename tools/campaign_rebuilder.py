#!/usr/bin/env python3
"""Create a separate Campaign Edition staging tree from a supported source.

The rebuilder never edits the source directory. It verifies/copies the source,
applies only hash-guarded verified patches, applies optional local offline data
overrides, moves APPX deployment metadata out of the runtime root, and writes a
machine-readable build status.

This is a development staging builder. portable_startup_ready remains false
until package/WinRT startup dependencies have been replaced and validated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_METADATA = (
    "AppxManifest.xml",
    "AppxBlockMap.xml",
    "AppxSignature.p7x",
    "[Content_Types].xml",
)

PACKAGE_METADATA_DIRS = (
    "AppxMetadata",
)

DEFAULT_MANIFEST = Path("patches/1.7.3.8-x86.json")
DEFAULT_CONFIG = Path("config/ReXtreme-1.0.ini")
DEFAULT_PRESENTATION_CAPABILITIES = Path("config/presentation-capabilities.verified.json")


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("files"), list):
        raise BuildError("Patch manifest has no files list.")
    return data


def verify_source(source: Path, manifest: dict) -> list[dict]:
    verified = []
    for entry in manifest["files"]:
        rel = Path(entry["path"])
        target = source / rel
        if not target.is_file():
            raise BuildError(f"Required source file is missing: {rel}")
        actual = sha256_file(target).lower()
        expected = str(entry["sha256"]).lower()
        patched = str(entry.get("patched_sha256", "")).lower()
        if actual not in {expected, patched}:
            raise BuildError(
                f"Unsupported source hash for {rel}: {actual} "
                f"(expected original {expected}"
                + (f" or patched {patched}" if patched else "")
                + ")"
            )
        verified.append({
            "path": rel.as_posix(),
            "sha256": actual,
            "state": "patched" if patched and actual == patched else "original",
        })
    return verified


def copy_source(source: Path, output: Path) -> None:
    if output.exists():
        raise BuildError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output)


def quarantine_package_metadata(output: Path) -> list[str]:
    quarantine = output / "_source_metadata" / "appx"
    moved: list[str] = []

    for name in PACKAGE_METADATA:
        src = output / name
        if src.exists():
            quarantine.mkdir(parents=True, exist_ok=True)
            dst = quarantine / name
            shutil.move(str(src), str(dst))
            moved.append(name)

    for name in PACKAGE_METADATA_DIRS:
        src = output / name
        if src.exists():
            quarantine.mkdir(parents=True, exist_ok=True)
            dst = quarantine / name
            shutil.move(str(src), str(dst))
            moved.append(name + "/")

    return moved


def copy_config(output: Path, config: Path) -> str:
    if not config.is_file():
        raise BuildError(f"Campaign config not found: {config}")
    dst = output / "ReXtreme.ini"
    shutil.copy2(config, dst)
    return dst.name


def apply_verified_patches(
    output: Path,
    manifest: Path,
    patcher: Path,
    dry_run: bool = False,
) -> None:
    cmd = [
        sys.executable,
        str(patcher),
        str(output),
        "--manifest",
        str(manifest),
        "--require-patches",
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise BuildError(f"Verified patcher failed with exit code {result.returncode}")


def prepare_portable_user_data(output: Path) -> list[str]:
    root = output / "UserData"
    folders = [
        root / "CampaignEdition",
        root / "Replays",
        root / "Screenshots",
    ]
    created: list[str] = []
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        created.append(folder.relative_to(output).as_posix() + "/")
    return created


def build_presentation_catalog(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Presentation capability source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Presentation capability builder not found: {builder}")

    target = output / "CampaignPresentationOptions.dat"
    report = output / "CampaignPresentationOptions.report.json"
    cmd = [
        sys.executable,
        str(builder),
        str(source),
        str(target),
        "--report",
        str(report),
    ]
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise BuildError(
            f"Presentation capability catalog build failed with exit code {result.returncode}"
        )

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid presentation capability report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
    }


def overlay_directory(output: Path, overlay: Path) -> list[str]:
    if not overlay.is_dir():
        raise BuildError(f"Overlay directory not found: {overlay}")

    copied: list[str] = []
    for src in overlay.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(overlay)
        dst = output / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel.as_posix())
    return sorted(copied)


def write_status(
    output: Path,
    verified: list[dict],
    moved_metadata: list[str],
    overlay_files: list[str],
    presentation_catalog: dict,
    portable_user_data: list[str],
) -> Path:
    status = {
        "edition": "Campaign",
        "source_build": "1.7.3.8-x86",
        "source_files_verified": verified,
        "verified_core_patches_applied": True,
        "offline_overlay_files": overlay_files,
        "presentation_capability_catalog": presentation_catalog,
        "portable_user_data": portable_user_data,
        "package_metadata_moved_out_of_runtime_root": moved_metadata,
        "portable_startup_ready": False,
        "startup_decoupling_status": "pending-runtime-validation",
        "notes": [
            "This tree is separate from the original source.",
            "APPX deployment metadata is retained under _source_metadata for analysis only.",
            "The runtime root is not treated as an APPX package.",
            "Direct portable startup is not declared ready until package/WinRT startup dependencies are replaced and tested.",
        ],
    }
    path = output / "CAMPAIGN_BUILD_STATUS.json"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Campaign Edition staging tree")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--presentation-capabilities",
        type=Path,
        default=DEFAULT_PRESENTATION_CAPABILITIES,
    )
    parser.add_argument("--offline-overlay", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    source = args.source_dir.resolve()
    output = args.output_dir.resolve()
    manifest_path = args.manifest.resolve()
    config_path = args.config.resolve()
    presentation_capabilities_path = args.presentation_capabilities.resolve()
    tools_dir = Path(__file__).resolve().parent
    patcher = (tools_dir / "patcher.py").resolve()
    presentation_builder = (tools_dir / "build_presentation_capability_catalog.py").resolve()

    if not source.is_dir():
        print(f"ERROR: source directory not found: {source}", file=sys.stderr)
        return 2
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_manifest(manifest_path)
        verified = verify_source(source, manifest)
        print(f"[VERIFY] supported source files: {len(verified)}")

        if args.verify_only:
            print("[DONE] verify-only")
            return 0

        copy_source(source, output)
        print(f"[COPY] {source} -> {output}")

        apply_verified_patches(output, manifest_path, patcher)
        moved = quarantine_package_metadata(output)
        print(f"[METADATA] moved from runtime root: {len(moved)}")

        copy_config(output, config_path)
        portable_user_data = prepare_portable_user_data(output)
        print(f"[USERDATA] portable directories: {len(portable_user_data)}")

        presentation_catalog = build_presentation_catalog(
            output,
            presentation_capabilities_path,
            presentation_builder,
        )
        print(
            "[PRESENTATION] verified options: "
            f"{presentation_catalog['count']} "
            f"(safe empty={presentation_catalog['safe_empty_catalog']})"
        )

        overlay_files: list[str] = []
        if args.offline_overlay:
            overlay_files = overlay_directory(output, args.offline_overlay.resolve())
            print(f"[OVERLAY] files applied: {len(overlay_files)}")

        status_path = write_status(
            output,
            verified,
            moved,
            overlay_files,
            presentation_catalog,
            portable_user_data,
        )
        print(f"[STATUS] {status_path}")
        print("[DONE] Campaign staging tree created; portable startup validation still pending")
        return 0

    except (BuildError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
