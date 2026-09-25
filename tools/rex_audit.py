#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

FORBIDDEN = (
    "CampaignFrontendBridge",
    "CampaignGarageFlow",
    "CampaignTutorialBuildConsumer",
    "CampaignRuntimeState",
    "CampaignApplication",
    "CampaignFrontendPort",
    "CampaignService",
    "CampaignCore",
    "CraftCar",
    "GlobalSync",
    "GS_Garage",
    "_AMS_PHASE2",
    "campaign_frontend_garage",
    "campaign_career_adapter",
    "RUN-CLEAN-RUNTIME-V1",
    "RUN-FRONTEND-ONLY",
)

ACTIVE = (
    "src/campaign-edition",
    "runtime-stubs/rex_campaign_gateway.asm",
    "runtime-stubs/IGPLib_x86_rex_campaign.def",
    "tools/rex_build_base.ps1",
    "tools/rex_build_content.py",
    "tools/rex_patch_frontend.py",
    "tools/rex_apply.ps1",
    "tools/rex_test.ps1",
    "RUN-REX-CAMPAIGN.ps1",
    "FINALIZE-CAMPAIGN-EDITION.cmd",
)

def files_under(root:Path, rel:str):
    p=root/rel
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(x for x in p.rglob("*") if x.is_file())
    return []

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()

    problems=[]
    scanned=[]

    for rel in ACTIVE:
        items=files_under(root,rel)
        if not items:
            problems.append({"file":rel,"rule":"missing-active-file"})
            continue
        for p in items:
            scanned.append(str(p.relative_to(root)))
            text=p.read_text(encoding="utf-8",errors="replace")
            for token in FORBIDDEN:
                if token in text:
                    problems.append({
                        "file":str(p.relative_to(root)),
                        "rule":"old-code-reference",
                        "token":token,
                    })

    # Runtime source may not contain executable-network APIs.
    net=re.compile(r"https?://|WinHttp|WinInet|WSAStartup|socket\s*\(",re.I)
    for p in files_under(root,"src/campaign-edition"):
        text=p.read_text(encoding="utf-8",errors="replace")
        if net.search(text):
            problems.append({
                "file":str(p.relative_to(root)),
                "rule":"network-api-in-new-runtime"
            })

    report={
        "schema":1,
        "runtime":"Rex Campaign Edition",
        "original_frontend_only":True,
        "old_campaign_code_used":False,
        "scanned":scanned,
        "problems":problems,
        "pass":not problems,
    }

    out=root/"prebuilt"/"rex-campaign"
    out.mkdir(parents=True,exist_ok=True)
    (out/"AUDIT.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8"
    )

    if problems:
        for x in problems:
            print("[ERRO]",x)
        return 1

    print("[OK] New Campaign Edition path contains no previous runtime/adapters.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
