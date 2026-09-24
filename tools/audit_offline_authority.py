#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path

ONLINE_OFF = 0x00BACDD0
ONLINE_FALSE = bytes.fromhex("31 C0 C3 90 90 90 90")
LEGACY_LOCALHOST_ROUTE_OFF = 0x00BAEA4B
LEGACY_LOCALHOST_ROUTE = bytes.fromhex("1C 68 40 C3 57 01")

FORBIDDEN_SOURCE_PATTERNS = {
    "legacy-craft-completion-rva": re.compile(r"CAMPAIGN_AMS_CRAFT_UI_COMPLETION_RVA|0x006A4D00u"),
    "legacy-craft-completion-symbol": re.compile(r"CampaignFrontendCompleteGarageBuild"),
}

REQUIRED_SOURCE_PATTERNS = {
    "network-hard-deny": ("src-reconstructed/campaign-core/CampaignOnlinePolicy.c",
                          re.compile(r"CampaignOnlineIsNetworkAllowed\s*\([^)]*\)\s*\{\s*return\s+0\s*;", re.S)),
    "local-startup": ("src-reconstructed/campaign-core/CampaignStartupService.c",
                      re.compile(r"CampaignStartupBegin")),
    "local-tutorial-build": ("src-reconstructed/campaign-core/CampaignTutorialBuildConsumer.c",
                             re.compile(r"CampaignTutorialBuildComplete")),
    "local-event-bus": ("src-reconstructed/campaign-core/CampaignEventBus.c",
                        re.compile(r"CampaignEventPublish")),
    "igp-http-is-local-gateway": ("runtime-stubs/IGPLib_x86_campaign.def",
                                  re.compile(r"HttpPostLink.*=campaign_gateway")),
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument(
        "--require-source",
        action="store_true",
        help="Fail if reconstructed source files required for source-level validation are absent."
    )
    ns = ap.parse_args()

    root = Path(ns.project_root).resolve()
    registry_path = root / "config" / "OFFLINE-AUTHORITY.json"
    if not registry_path.is_file():
        print("[ERRO] missing registry:", registry_path)
        return 2

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    problems = []
    checks = []

    if registry.get("network_allowed") is not False:
        problems.append("registry.network_allowed must be false")
    if registry.get("multiplayer_allowed") is not False:
        problems.append("registry.multiplayer_allowed must be false")

    ams = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if ams.is_file():
        data = ams.read_bytes()
        current = data[ONLINE_OFF:ONLINE_OFF + len(ONLINE_FALSE)]
        ok = current == ONLINE_FALSE
        checks.append({"check":"global-isonline-false","ok":ok,
                       "offset":f"0x{ONLINE_OFF:08X}",
                       "bytes":current.hex(" ")})
        if not ok:
            problems.append("AMS Global IsOnline is not hard FALSE")

        localhost_bytes = data[
            LEGACY_LOCALHOST_ROUTE_OFF:
            LEGACY_LOCALHOST_ROUTE_OFF + len(LEGACY_LOCALHOST_ROUTE)
        ]
        localhost_active = localhost_bytes == LEGACY_LOCALHOST_ROUTE
        checks.append({
            "check":"no-legacy-localhost-backend",
            "ok":not localhost_active,
            "offset":f"0x{LEGACY_LOCALHOST_ROUTE_OFF:08X}",
            "bytes":localhost_bytes.hex(" ")
        })
        if localhost_active:
            problems.append(
                "legacy localhost backend emulation is active; Campaign Edition forbids fake servers"
            )
    else:
        checks.append({"check":"global-isonline-false","ok":None,"reason":"AMS not present"})

    source_root = root / "src-reconstructed" / "campaign-core"
    combined = ""
    if source_root.is_dir():
        for p in sorted(source_root.glob("*.[ch]")):
            combined += "\n/* " + p.name + " */\n"
            combined += p.read_text(encoding="utf-8", errors="replace")

    if source_root.is_dir():
        for name, pat in FORBIDDEN_SOURCE_PATTERNS.items():
            hit = bool(pat.search(combined))
            checks.append({"check":name,"ok":not hit,"scope":"source"})
            if hit:
                problems.append(f"forbidden legacy dependency still present: {name}")
    else:
        for name in FORBIDDEN_SOURCE_PATTERNS:
            checks.append({
                "check":name,
                "ok":None,
                "scope":"source",
                "reason":"source tree not present in runtime distribution"
            })
        if ns.require_source:
            problems.append(
                "reconstructed source tree is required for this audit mode but is not present"
            )

    for name, (rel, pat) in REQUIRED_SOURCE_PATTERNS.items():
        p = root / rel
        if not p.is_file():
            checks.append({
                "check":name,
                "ok":None,
                "scope":"source",
                "path":rel,
                "reason":"source file not present in runtime distribution"
            })
            if ns.require_source:
                problems.append(f"required offline source component missing: {name}")
            continue

        text = p.read_text(encoding="utf-8", errors="replace")
        ok = bool(pat.search(text))
        checks.append({"check":name,"ok":ok,"scope":"source","path":rel})
        if not ok:
            problems.append(f"required offline component invalid: {name}")

    domains = registry.get("domains", [])
    bad_statuses = set(registry.get("forbidden_final_statuses", ["MIGRATING","UNRESOLVED"]))
    unresolved = [d for d in domains if d.get("status") in bad_statuses]
    local = [d for d in domains if d.get("status") == "LOCAL"]
    retired = [d for d in domains if d.get("status") == "RETIRED"]

    report = {
        "schema": 1,
        "target": registry.get("target"),
        "strict": bool(ns.strict),
        "require_source": bool(ns.require_source),
        "counts": {
            "domains": len(domains),
            "local": len(local),
            "retired": len(retired),
            "not_final": len(unresolved),
            "hard_problems": len(problems),
        },
        "unresolved": unresolved,
        "checks": checks,
        "hard_problems": problems,
    }

    out_dir = root / "_TRACE_MONTAR"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "OFFLINE-AUTHORITY-AUDIT.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OFFLINE] target:", registry.get("target"))
    print("[OFFLINE] network_allowed=false")
    print("[OFFLINE] multiplayer_allowed=false")
    print("[OFFLINE] source_validation=", "required" if ns.require_source else "best-effort")
    print(f"[OFFLINE] LOCAL={len(local)} RETIRED={len(retired)} NOT_FINAL={len(unresolved)}")
    for d in unresolved:
        print(f"[PENDENTE] {d['id']}: {d['status']} -> {d.get('authority','')}")
    for p in problems:
        print("[ERRO]", p)
    print("[REPORT]", out)

    if problems:
        return 1
    if ns.strict and unresolved:
        return 3
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
