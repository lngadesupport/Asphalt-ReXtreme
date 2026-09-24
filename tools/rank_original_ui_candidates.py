#!/usr/bin/env python3
"""Rank candidates for reusable original Asphalt Xtreme UI components.

Input must come from audit_original_settings_ui.py. Output is discovery-only and
MUST NOT be used as a verified binding source. It only prioritizes candidates
for manual disassembly/runtime verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROLES = {
    "ui.screen": {
        "kind": "screen",
        "terms": ("screen", "menu", "settings", "options"),
    },
    "ui.panel": {
        "kind": "panel",
        "terms": ("panel", "container", "widget", "menu"),
    },
    "ui.button": {
        "kind": "button",
        "terms": ("button", "accept", "cancel", "back", "apply", "resume"),
    },
    "ui.slider": {
        "kind": "slider",
        "terms": ("slider", "resolution", "volume", "quality"),
    },
    "ui.toggle": {
        "kind": "toggle",
        "terms": ("toggle", "checkbox", "fullscreen", "vsync"),
    },
    "ui.label": {
        "kind": "label",
        "terms": ("label", "text", "title"),
    },
    "ui.list": {
        "kind": "list",
        "terms": ("list", "item", "menu"),
    },
    "settings.screen": {
        "kind": "screen",
        "terms": ("settings", "options", "video", "display", "graphics"),
    },
    "settings.row": {
        "kind": "panel",
        "terms": ("settings", "option", "item", "row", "panel"),
    },
    "pause.screen": {
        "kind": "screen",
        "terms": ("pause", "resume", "menu"),
    },
    "pause.menu.slot": {
        "kind": "panel",
        "terms": ("pause", "menu", "item", "container", "panel"),
    },
    "race.hud": {
        "kind": "panel",
        "terms": ("hud", "race", "position", "lap"),
    },
}


class CandidateError(RuntimeError):
    pass


def score_candidate(role: str, row: dict) -> tuple[int, list[str]]:
    spec = ROLES[role]
    text = str(row.get("text", "")).lower()
    source = str(row.get("source", "")).lower()
    keywords = {str(x).lower() for x in row.get("keywords", [])}
    xrefs = int(row.get("xref_count", 0) or 0)

    score = 0
    reasons: list[str] = []
    for term in spec["terms"]:
        if term in keywords:
            score += 20
            reasons.append(f"keyword:{term}")
        elif term in text:
            score += 12
            reasons.append(f"text:{term}")
        elif term in source:
            score += 6
            reasons.append(f"source:{term}")

    if row.get("rva") is not None:
        score += 10
        reasons.append("has-rva")
    if row.get("va") is not None:
        score += 4
        reasons.append("has-va")
    if xrefs:
        bonus = min(xrefs, 16) * 4
        score += bonus
        reasons.append(f"xrefs:{xrefs}")
    if source.endswith("ams.exe") or source == "ams.exe":
        score += 8
        reasons.append("ams-exe")
    if row.get("encoding") in {"ascii", "utf16le"}:
        score += 2

    return score, reasons


def rank(report: dict, top: int) -> dict:
    if report.get("format") != "rextreme-original-settings-ui-audit":
        raise CandidateError("input is not an original settings/UI audit")
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        raise CandidateError("audit has no candidates array")

    roles: dict[str, dict] = {}
    for role, spec in ROLES.items():
        ranked: list[dict] = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            score, reasons = score_candidate(role, row)
            if score <= 0:
                continue
            ranked.append({
                "score": score,
                "reasons": reasons,
                "source": row.get("source"),
                "text": row.get("text"),
                "encoding": row.get("encoding"),
                "offset": row.get("offset"),
                "rva": row.get("rva"),
                "va": row.get("va"),
                "xref_count": row.get("xref_count", 0),
                "xref_rvas": row.get("xref_rvas", []),
                "status": "candidate-only",
                "verified": False,
            })
        ranked.sort(
            key=lambda x: (
                -x["score"],
                -int(x.get("xref_count", 0) or 0),
                str(x.get("source", "")),
                int(x.get("offset") or -1),
            )
        )
        roles[role] = {
            "expected_kind": spec["kind"],
            "required_manual_verification": True,
            "candidates": ranked[:top],
        }

    return {
        "format": "rextreme-original-ui-candidate-ranking",
        "version": 1,
        "rule": (
            "Candidate ranking is never a verified binding. Copy nothing into "
            "original-ui-bindings.verified.json until exact PE target, object role, "
            "lifetime, callback semantics and runtime behavior are manually verified."
        ),
        "roles": roles,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank candidate original Asphalt UI components")
    ap.add_argument("audit", type=Path)
    ap.add_argument("--out", type=Path, default=Path("original-ui-candidate-ranking.json"))
    ap.add_argument("--top", type=int, default=12)
    ns = ap.parse_args()

    if ns.top < 1 or ns.top > 100:
        ap.error("--top must be 1..100")

    try:
        source = json.loads(ns.audit.read_text(encoding="utf-8"))
        output = rank(source, ns.top)
    except (OSError, json.JSONDecodeError, CandidateError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {ns.out}")
    for role, item in output["roles"].items():
        print(f"{role}: {len(item['candidates'])} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
