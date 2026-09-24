#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

FORBIDDEN = {
    "GS_Garage": re.compile(r"\bGS_Garage\b"),
    "CraftCar": re.compile(r"CraftCar"),
    "GlobalSync": re.compile(r"GlobalSync"),
    "legacy": re.compile(r"\blegacy\b", re.I),
    "adapter": re.compile(r"\badapter\b", re.I),
    "AMS_RVA": re.compile(r"CAMPAIGN_AMS|AMS_RVA"),
    "game_mode_gui": re.compile(r"game_mode_gui", re.I),
    "original-game-pointer": re.compile(r"ResolveSelectedCarId|RefreshGarageUi|CampaignCallVirtual"),
    "old-frontend-bridge": re.compile(r"CampaignFrontendBridge|CampaignTutorialBuildConsumer|CampaignGarageFlow"),
    "network": re.compile(r"https?://|winhttp|wininet|ws2_32|socket\s*\(", re.I),
}

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    src=root/"src-reconstructed"/"campaign-runtime"
    if not src.is_dir():
        print("[ERRO] clean runtime source missing:",src)
        return 2

    problems=[]
    files=[]
    for p in sorted(src.glob("*.[ch]")):
        text=p.read_text(encoding="utf-8",errors="replace")
        files.append(str(p.relative_to(root)))
        for name,pat in FORBIDDEN.items():
            if pat.search(text):
                problems.append({"file":str(p.relative_to(root)),"rule":name})

    gw=root/"runtime-stubs"/"campaign_runtime_gateway.asm"
    if not gw.is_file():
        problems.append({"file":str(gw.relative_to(root)),"rule":"missing-clean-gateway"})
    else:
        text=gw.read_text(encoding="utf-8",errors="replace")
        for name in ("CampaignCraftInvoke","CampaignFrontendGarageBuild",
                     "CampaignBeginRaceFromGui","CampaignFinishRaceFromGui"):
            if name in text:
                problems.append({"file":str(gw.relative_to(root)),"rule":"old-symbol:"+name})

    active_files = (
        "RUN-CLEAN-RUNTIME-V1.ps1",
        "tools/test_clean_runtime_v1.ps1",
        "tools/apply_clean_runtime_v1.ps1",
        "tools/build_package_phase5.ps1",
        "tools/public_beta.ps1",
        "FINALIZE-CAMPAIGN-EDITION.cmd",
    )
    active_forbidden = (
        "_AMS_PHASE2",
        "campaign_frontend_garage_v",
        "campaign_career_adapter_v",
        "CampaignFrontendBridge",
        "CampaignGarageFlow",
        "CampaignTutorialBuildConsumer",
    )
    for rel in active_files:
        p = root / rel
        if not p.is_file():
            problems.append({"file":rel,"rule":"missing-active-clean-path"})
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for token in active_forbidden:
            if token in text:
                problems.append({"file":rel,"rule":"active-old-path:"+token})

    report={
        "schema":1,
        "runtime":"Campaign Runtime V1",
        "frontend_only_original_code":True,
        "scanned":files,
        "problems":problems,
        "pass":not problems,
    }
    out=root/"prebuilt"/"campaign-runtime"
    out.mkdir(parents=True,exist_ok=True)
    (out/"CLEAN-RUNTIME-AUDIT.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8"
    )

    if problems:
        for p in problems:
            print("[ERRO]",p["file"],p["rule"])
        return 1

    print("[OK] Campaign Runtime contains no original gameplay structures.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
