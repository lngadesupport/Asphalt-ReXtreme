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
DEFAULT_PRESENTATION_BINDINGS = Path("config/presentation-bindings.verified.json")
DEFAULT_PHOTO_BINDINGS = Path("config/photo-bindings.verified.json")
DEFAULT_REPLAY_BINDINGS = Path("config/replay-bindings.verified.json")
DEFAULT_ORIGINAL_UI_BINDINGS = Path("config/original-ui-bindings.verified.json")
DEFAULT_RACE_HUD_BINDINGS = Path("config/race-hud-bindings.verified.json")
DEFAULT_CHALLENGES = Path("config/campaign_challenges.json")
DEFAULT_ACHIEVEMENTS = Path("config/campaign_achievements.json")
DEFAULT_SPECIAL_EVENTS = Path("config/campaign_special_events.json")
DEFAULT_CHAMPIONSHIPS = Path("config/campaign_championships.json")


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


def build_presentation_bindings(
    output: Path,
    source: Path,
    capability_source: Path,
    builder: Path,
) -> dict:
    if not source.is_file():
        raise BuildError(f"Presentation binding source not found: {source}")
    if not capability_source.is_file():
        raise BuildError(f"Presentation capability source not found: {capability_source}")
    if not builder.is_file():
        raise BuildError(f"Presentation binding builder not found: {builder}")

    target = output / "CampaignPresentationBindings.dat"
    report = output / "CampaignPresentationBindings.report.json"
    cmd = [
        sys.executable,
        str(builder),
        str(source),
        str(capability_source),
        str(target),
        "--report",
        str(report),
    ]
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise BuildError(
            f"Presentation binding catalog build failed with exit code {result.returncode}"
        )

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid presentation binding report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
    }


def build_photo_bindings(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Photo binding source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Photo binding builder not found: {builder}")

    target = output / "CampaignPhotoBindings.dat"
    report = output / "CampaignPhotoBindings.report.json"
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
        raise BuildError(f"Photo binding catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Photo binding report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "free_camera_ready": bool(summary.get("free_camera_ready", False)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
    }


def build_replay_bindings(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Replay binding source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Replay binding builder not found: {builder}")

    target = output / "CampaignReplayBindings.dat"
    report = output / "CampaignReplayBindings.report.json"
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
        raise BuildError(f"Replay binding catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Replay binding report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "recording_ready": bool(summary.get("recording_ready", False)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
    }


def build_original_ui_bindings(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Original UI binding source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Original UI binding builder not found: {builder}")

    target = output / "CampaignOriginalUiBindings.dat"
    report = output / "CampaignOriginalUiBindings.report.json"
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
        raise BuildError(f"Original UI binding catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Original UI binding report: {exc}") from exc

    if not summary.get("original_ui_only", False):
        raise BuildError("Original UI policy unexpectedly disabled")
    if summary.get("custom_ui_assets_allowed", True):
        raise BuildError("Custom in-game UI assets unexpectedly enabled")

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
        "original_ui_only": True,
        "custom_ui_assets_allowed": False,
        "fallback_if_unmapped": "feature-hidden",
    }


def build_race_hud_bindings(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Race HUD binding source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Race HUD binding builder not found: {builder}")

    target = output / "CampaignRaceHudBindings.dat"
    report = output / "CampaignRaceHudBindings.report.json"
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
        raise BuildError(f"Race HUD binding catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Race HUD binding report: {exc}") from exc

    if not summary.get("original_elements_only", False):
        raise BuildError("Race HUD original-elements-only policy unexpectedly disabled")
    if summary.get("create_new_hud_widgets", True):
        raise BuildError("Race HUD new-widget creation unexpectedly enabled")

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "safe_empty_catalog": bool(summary.get("safe_empty_catalog", False)),
        "original_elements_only": True,
        "create_new_hud_widgets": False,
    }


def build_challenge_catalog(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Challenge source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Challenge builder not found: {builder}")

    target = output / "CampaignChallenges.dat"
    report = output / "CampaignChallenges.report.json"
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
        raise BuildError(f"Challenge catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Challenge report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "state": "UserData/CampaignEdition/ChallengeState.dat",
        "portable": True,
    }


def build_achievement_catalog(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Achievement source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Achievement builder not found: {builder}")

    target = output / "CampaignAchievements.dat"
    report = output / "CampaignAchievements.report.json"
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
        raise BuildError(f"Achievement catalog build failed with exit code {result.returncode}")

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Achievement report: {exc}") from exc

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "state": "UserData/CampaignEdition/AchievementState.dat",
        "metrics_source": "CampaignStatistics-v1",
        "rewards": "none",
        "portable": True,
    }


def build_special_event_catalog(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Special Event source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Special Event builder not found: {builder}")

    target = output / "CampaignSpecialEvents.dat"
    report = output / "CampaignSpecialEvents.report.json"
    event_catalog = output / "CampaignEvents.dat"

    cmd = [
        sys.executable,
        str(builder),
        str(source),
        str(target),
        "--report",
        str(report),
    ]
    if event_catalog.is_file():
        cmd.extend(["--event-catalog", str(event_catalog)])

    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise BuildError(
            "Special Event catalog build failed. Non-empty Special Events require "
            "a valid CampaignEvents.dat in the staging tree."
        )

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Special Event report: {exc}") from exc

    if not summary.get("uses_existing_campaign_events_only", False):
        raise BuildError("Special Events must reuse existing Campaign events")
    if summary.get("online_backend_required", True):
        raise BuildError("Special Events unexpectedly require online backend")

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "validated_against_event_catalog": bool(
            summary.get("validated_against_event_catalog", False)
        ),
        "uses_existing_campaign_events_only": True,
        "online_backend_required": False,
        "portable": True,
    }


def build_championship_catalog(output: Path, source: Path, builder: Path) -> dict:
    if not source.is_file():
        raise BuildError(f"Championship source not found: {source}")
    if not builder.is_file():
        raise BuildError(f"Championship builder not found: {builder}")

    target = output / "CampaignChampionships.dat"
    report = output / "CampaignChampionships.report.json"
    event_catalog = output / "CampaignEvents.dat"
    cmd = [
        sys.executable,
        str(builder),
        str(source),
        str(target),
        "--report",
        str(report),
    ]
    if event_catalog.is_file():
        cmd.extend(["--event-catalog", str(event_catalog)])

    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise BuildError(
            "Championship catalog build failed. Non-empty Championships require "
            "a valid CampaignEvents.dat in the staging tree."
        )

    try:
        summary = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid Championship report: {exc}") from exc

    if not summary.get("uses_existing_campaign_events_only", False):
        raise BuildError("Championships must reuse existing Campaign events")
    if summary.get("online_backend_required", True):
        raise BuildError("Championships unexpectedly require online backend")

    return {
        "catalog": target.name,
        "report": report.name,
        "count": int(summary.get("count", 0)),
        "validated_against_event_catalog": bool(
            summary.get("validated_against_event_catalog", False)
        ),
        "uses_existing_campaign_events_only": True,
        "online_backend_required": False,
        "state": "UserData/CampaignEdition/ChampionshipState.dat",
        "portable": True,
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
    presentation_bindings: dict,
    photo_bindings: dict,
    replay_bindings: dict,
    original_ui_bindings: dict,
    race_hud_bindings: dict,
    challenge_catalog: dict,
    achievement_catalog: dict,
    special_event_catalog: dict,
    championship_catalog: dict,
    portable_user_data: list[str],
) -> Path:
    status = {
        "edition": "Campaign",
        "source_build": "1.7.3.8-x86",
        "source_files_verified": verified,
        "verified_core_patches_applied": True,
        "offline_overlay_files": overlay_files,
        "presentation_capability_catalog": presentation_catalog,
        "presentation_binding_catalog": presentation_bindings,
        "presentation_values_require_verified_binding": True,
        "photo_binding_catalog": photo_bindings,
        "photo_free_camera_ready": bool(photo_bindings.get("free_camera_ready", False)),
        "replay_binding_catalog": replay_bindings,
        "replay_recording_ready": bool(replay_bindings.get("recording_ready", False)),
        "original_ui_binding_catalog": original_ui_bindings,
        "original_ui_only": True,
        "custom_in_game_ui_assets_allowed": False,
        "unmapped_ui_feature_behavior": "hidden",
        "race_hud_binding_catalog": race_hud_bindings,
        "race_hud_original_elements_only": True,
        "race_hud_new_widgets_allowed": False,
        "challenge_catalog": challenge_catalog,
        "challenge_state_portable": True,
        "challenge_metrics_source": "CampaignRaceMetrics-v1",
        "statistics_state": "UserData/CampaignEdition/CampaignStatistics.dat",
        "statistics_source": "CampaignRaceMetrics-v1",
        "statistics_portable": True,
        "achievement_catalog": achievement_catalog,
        "achievement_state_portable": True,
        "achievement_metrics_source": "CampaignStatistics-v1",
        "achievement_rewards": "none",
        "achievement_ui_requires_original_templates": True,
        "last_race_result_state": "UserData/CampaignEdition/LastRaceResult.dat",
        "last_race_result_source": "Committed CampaignRaceMetrics-v1",
        "last_race_result_portable": True,
        "results_ui_requires_original_templates": True,
        "special_event_catalog": special_event_catalog,
        "special_events_reuse_campaign_events": True,
        "special_events_online_backend_required": False,
        "special_events_ui_requires_original_templates": True,
        "special_event_period_state": "UserData/CampaignEdition/SpecialEventPeriodState.dat",
        "special_event_rotating_progress_reset": True,
        "championship_catalog": championship_catalog,
        "championship_state_portable": True,
        "championships_reuse_campaign_events": True,
        "championships_online_backend_required": False,
        "championships_ui_requires_original_templates": True,
        "activity_context_state": "UserData/CampaignEdition/ActivityContext.dat",
        "special_event_and_championship_progress_requires_explicit_context": True,
        "career_races_do_not_advance_special_modes_by_event_id": True,
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
    parser.add_argument(
        "--presentation-bindings",
        type=Path,
        default=DEFAULT_PRESENTATION_BINDINGS,
    )
    parser.add_argument(
        "--photo-bindings",
        type=Path,
        default=DEFAULT_PHOTO_BINDINGS,
    )
    parser.add_argument(
        "--replay-bindings",
        type=Path,
        default=DEFAULT_REPLAY_BINDINGS,
    )
    parser.add_argument(
        "--original-ui-bindings",
        type=Path,
        default=DEFAULT_ORIGINAL_UI_BINDINGS,
    )
    parser.add_argument(
        "--race-hud-bindings",
        type=Path,
        default=DEFAULT_RACE_HUD_BINDINGS,
    )
    parser.add_argument(
        "--challenges",
        type=Path,
        default=DEFAULT_CHALLENGES,
    )
    parser.add_argument(
        "--achievements",
        type=Path,
        default=DEFAULT_ACHIEVEMENTS,
    )
    parser.add_argument(
        "--special-events",
        type=Path,
        default=DEFAULT_SPECIAL_EVENTS,
    )
    parser.add_argument(
        "--championships",
        type=Path,
        default=DEFAULT_CHAMPIONSHIPS,
    )
    parser.add_argument("--offline-overlay", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    source = args.source_dir.resolve()
    output = args.output_dir.resolve()
    manifest_path = args.manifest.resolve()
    config_path = args.config.resolve()
    presentation_capabilities_path = args.presentation_capabilities.resolve()
    presentation_bindings_path = args.presentation_bindings.resolve()
    photo_bindings_path = args.photo_bindings.resolve()
    replay_bindings_path = args.replay_bindings.resolve()
    original_ui_bindings_path = args.original_ui_bindings.resolve()
    race_hud_bindings_path = args.race_hud_bindings.resolve()
    challenges_path = args.challenges.resolve()
    achievements_path = args.achievements.resolve()
    special_events_path = args.special_events.resolve()
    championships_path = args.championships.resolve()
    tools_dir = Path(__file__).resolve().parent
    patcher = (tools_dir / "patcher.py").resolve()
    presentation_builder = (tools_dir / "build_presentation_capability_catalog.py").resolve()
    presentation_binding_builder = (tools_dir / "build_presentation_binding_catalog.py").resolve()
    photo_binding_builder = (tools_dir / "build_photo_binding_catalog.py").resolve()
    replay_binding_builder = (tools_dir / "build_replay_binding_catalog.py").resolve()
    original_ui_binding_builder = (tools_dir / "build_original_ui_binding_catalog.py").resolve()
    race_hud_binding_builder = (tools_dir / "build_race_hud_binding_catalog.py").resolve()
    challenge_builder = (tools_dir / "build_campaign_challenge_catalog.py").resolve()
    achievement_builder = (tools_dir / "build_campaign_achievement_catalog.py").resolve()
    special_event_builder = (tools_dir / "build_campaign_special_event_catalog.py").resolve()
    championship_builder = (tools_dir / "build_campaign_championship_catalog.py").resolve()

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

        presentation_bindings = build_presentation_bindings(
            output,
            presentation_bindings_path,
            presentation_capabilities_path,
            presentation_binding_builder,
        )
        print(
            "[PRESENTATION] verified bindings: "
            f"{presentation_bindings['count']} "
            f"(safe empty={presentation_bindings['safe_empty_catalog']})"
        )

        photo_bindings = build_photo_bindings(
            output,
            photo_bindings_path,
            photo_binding_builder,
        )
        print(
            "[PHOTO] verified bindings: "
            f"{photo_bindings['count']} "
            f"(free camera ready={photo_bindings['free_camera_ready']})"
        )

        replay_bindings = build_replay_bindings(
            output,
            replay_bindings_path,
            replay_binding_builder,
        )
        print(
            "[REPLAY] verified bindings: "
            f"{replay_bindings['count']} "
            f"(recording ready={replay_bindings['recording_ready']})"
        )

        original_ui_bindings = build_original_ui_bindings(
            output,
            original_ui_bindings_path,
            original_ui_binding_builder,
        )
        print(
            "[UI] original-only verified bindings: "
            f"{original_ui_bindings['count']} "
            f"(unmapped features hidden)"
        )

        race_hud_bindings = build_race_hud_bindings(
            output,
            race_hud_bindings_path,
            race_hud_binding_builder,
        )
        print(
            "[HUD] verified original-element bindings: "
            f"{race_hud_bindings['count']} "
            f"(new widgets allowed={race_hud_bindings['create_new_hud_widgets']})"
        )

        challenge_catalog = build_challenge_catalog(
            output,
            challenges_path,
            challenge_builder,
        )
        print(
            "[CHALLENGES] definitions: "
            f"{challenge_catalog['count']} "
            f"(portable state={challenge_catalog['portable']})"
        )

        achievement_catalog = build_achievement_catalog(
            output,
            achievements_path,
            achievement_builder,
        )
        print(
            "[ACHIEVEMENTS] definitions: "
            f"{achievement_catalog['count']} "
            f"(metrics={achievement_catalog['metrics_source']}, rewards={achievement_catalog['rewards']})"
        )

        special_event_catalog = build_special_event_catalog(
            output,
            special_events_path,
            special_event_builder,
        )
        print(
            "[SPECIAL EVENTS] definitions: "
            f"{special_event_catalog['count']} "
            f"(offline={not special_event_catalog['online_backend_required']})"
        )

        championship_catalog = build_championship_catalog(
            output,
            championships_path,
            championship_builder,
        )
        print(
            "[CHAMPIONSHIPS] definitions: "
            f"{championship_catalog['count']} "
            f"(offline={not championship_catalog['online_backend_required']})"
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
            presentation_bindings,
            photo_bindings,
            replay_bindings,
            original_ui_bindings,
            race_hud_bindings,
            challenge_catalog,
            achievement_catalog,
            special_event_catalog,
            championship_catalog,
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
