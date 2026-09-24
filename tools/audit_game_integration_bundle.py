#!/usr/bin/env python3
"""Run the full ReXtreme presentation/integration audit against a local game tree."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class AuditError(RuntimeError):
    pass


def run(cmd: list[str], label: str) -> None:
    print(f"[{label}] {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise AuditError(f"{label} failed with exit code {result.returncode}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Run complete ReXtreme game integration audit")
    ap.add_argument("game_dir", type=Path)
    ap.add_argument("--ams", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("_TRACE_MONTAR/REXTREME-INTEGRATION-AUDIT"))
    ns = ap.parse_args()

    game = ns.game_dir.resolve()
    if not game.is_dir():
        ap.error(f"game directory not found: {game}")

    ams = ns.ams.resolve() if ns.ams else game / "AMS.exe"
    if not ams.is_file():
        ap.error(f"AMS.exe not found: {ams}")

    out = ns.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tools = Path(__file__).resolve().parent

    presentation = out / "presentation-capabilities.json"
    ui = out / "original-settings-ui.json"
    hooks = out / "replay-photo-frame-hooks.json"

    try:
        run([
            sys.executable,
            str(tools / "audit_presentation_capabilities.py"),
            str(game),
            "--out",
            str(presentation),
        ], "PRESENTATION")

        run([
            sys.executable,
            str(tools / "audit_original_settings_ui.py"),
            str(game),
            "--out",
            str(ui),
        ], "ORIGINAL-UI")

        run([
            sys.executable,
            str(tools / "audit_replay_frame_hooks.py"),
            str(ams),
            "--out",
            str(hooks),
        ], "FRAME-HOOKS")

        p = read_json(presentation)
        u = read_json(ui)
        h = read_json(hooks)

        anchors = h.get("known_verified_anchors", [])
        anchor_matches = sum(1 for row in anchors if row.get("matches"))
        top = h.get("top_candidates", [])
        field = h.get("top_field_write_candidates", [])

        summary = {
            "format": "rextreme-integration-audit-summary",
            "version": 1,
            "game_dir": str(game),
            "ams": str(ams),
            "target_pe": h.get("target_pe"),
            "known_hook_anchors": {
                "matched": anchor_matches,
                "total": len(anchors),
                "all_match": bool(anchors) and anchor_matches == len(anchors),
                "details": anchors,
            },
            "presentation": {
                "candidate_evidence": p.get("summary", {}).get("evidence_count", 0),
                "with_x86_xrefs": p.get("summary", {}).get("evidence_with_x86_absolute_xrefs", 0),
                "by_category": p.get("summary", {}).get("by_category", {}),
                "confirmed_capabilities": p.get("confirmed_capabilities", []),
            },
            "original_ui": {
                "candidate_rows": u.get("summary", {}).get("candidate_rows", 0),
                "archives_scanned": u.get("summary", {}).get("archives_scanned", 0),
                "verified_bindings": u.get("verified_bindings", []),
            },
            "frame_hooks": {
                "mapped_classes": len(h.get("mapped_classes", [])),
                "candidate_methods": len(top),
                "field_write_methods": len(field),
                "top_candidates": [
                    {
                        "class": row.get("class"),
                        "slot_offset": row.get("slot_offset"),
                        "method_va": row.get("method_va"),
                        "method_file_offset": row.get("method_file_offset"),
                        "score": row.get("score"),
                        "reasons": row.get("reasons", []),
                    }
                    for row in top[:20]
                ],
                "top_field_write_candidates": field[:20],
            },
            "readiness": {
                "replay_frame_binding_verified": False,
                "photo_frame_binding_verified": False,
                "photo_camera_bindings_verified": False,
                "presentation_memory_bindings_verified": False,
            },
            "next_review": [
                "Verify the highest-ranked GameModeGUIBase update-like method at runtime.",
                "Verify player vehicle transform source and sample stability.",
                "Review camera/HUD object field writes for Photo semantic bindings.",
                "Review original Settings UI candidates before exposing any extra option.",
                "Promote only exact proven paths into the verified JSON registries.",
            ],
        }

        summary_path = out / "SUMMARY.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print("")
        print("[DONE] ReXtreme integration audit")
        print(f"  Anchors: {anchor_matches}/{len(anchors)}")
        print(f"  Presentation candidates: {summary['presentation']['candidate_evidence']}")
        print(f"  UI candidates: {summary['original_ui']['candidate_rows']}")
        print(f"  Hook candidates: {summary['frame_hooks']['candidate_methods']}")
        print(f"  Field-write candidates: {summary['frame_hooks']['field_write_methods']}")
        print(f"  Summary: {summary_path}")
        return 0

    except (OSError, json.JSONDecodeError, AuditError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
