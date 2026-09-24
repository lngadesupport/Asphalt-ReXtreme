#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

IMAGE_BASE=0x00400000
IGP_HTTPPOST_IAT_RVA=0x0112A034
IGP_HTTPPOST_PREF_VA=IMAGE_BASE+IGP_HTTPPOST_IAT_RVA

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

BUILD_OFF=0x00686D60
BUILD_VA=0x00A87960
BUILD_ORIG=bytes.fromhex(
    "55 8B EC 6A FF 68 D0 30 3F 01 64 A1 00 00 00 00 50 83 EC"
)

GARAGE_BUILD_MAGIC=0xC0DE7713

def fmt(b:bytes)->str:
    return " ".join(f"{x:02X}" for x in b)

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def pic_gateway_stub(stub_va:int, selector:int)->bytes:
    code=bytearray()
    code += b"\x68" + struct.pack("<I",selector)
    code += b"\xE8\x00\x00\x00\x00"
    code += b"\x58"
    pop_next=stub_va+len(code)
    code += b"\x05" + struct.pack("<I",(IGP_HTTPPOST_PREF_VA-pop_next)&0xffffffff)
    code += b"\xFF\x10"
    code += b"\xC3"
    return bytes(code)

BUILD_PATCH=pic_gateway_stub(BUILD_VA,GARAGE_BUILD_MAGIC)
if len(BUILD_PATCH)!=19: raise RuntimeError(len(BUILD_PATCH))

def patch(d:bytearray,off:int,orig:bytes,new:bytes,label:str,changes:list):
    cur=bytes(d[off:off+len(new)])
    if cur==new:
        changes.append({"label":label,"offset":f"0x{off:08X}","status":"already-patched"})
        return
    expected=orig[:len(new)]
    if cur!=expected:
        raise RuntimeError(f"{label}: unexpected bytes at 0x{off:08X}: {fmt(cur)}")
    d[off:off+len(new)]=new
    changes.append({
        "label":label,"offset":f"0x{off:08X}","status":"patched",
        "before":fmt(expected),"after":fmt(new)
    })

def apply(root:Path)->int:
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    core=root/"prebuilt"/"campaign-core"/"IGPLib_x86.dll"
    target_core=root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll"
    if not ams.is_file(): raise FileNotFoundError(ams)
    if not core.is_file(): raise FileNotFoundError(core)

    raw=ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")

    d=bytearray(raw)
    changes=[]
    patch(
        d,BUILD_OFF,BUILD_ORIG,BUILD_PATCH,
        "MONTAR frontend -> CampaignFrontendGarageBuild",changes
    )

    before=sha(raw)
    backup_dir=root/"_BACKUPS"/"FRONTEND-ONLY-GARAGE-V2"
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/f"AMS.exe.{before}.bak"
    if not backup.exists(): shutil.copy2(ams,backup)

    tmp=ams.with_suffix(".frontend-garage-v2.tmp")
    tmp.write_bytes(d)
    verify=tmp.read_bytes()
    if verify[BUILD_OFF:BUILD_OFF+len(BUILD_PATCH)]!=BUILD_PATCH:
        raise RuntimeError("BuildCar verification failed")
    tmp.replace(ams)
    shutil.copy2(core,target_core)

    out=root/"_TRACE_MONTAR"
    out.mkdir(parents=True,exist_ok=True)
    report={
      "phase":"Frontend-Only Garage v2",
      "frontend_preserved":[
        "garage screen","MONTAR button","selected-car UI","menu transitions"
      ],
      "legacy_business_retired":[
        "GS_Garage::BuildCar body","CraftCarCaller","CraftCarRequestImpl",
        "remote CraftCar","remote completion"
      ],
      "build":{
        "file_offset":f"0x{BUILD_OFF:08X}",
        "va":f"0x{BUILD_VA:08X}",
        "selector":f"0x{GARAGE_BUILD_MAGIC:08X}",
        "authority":"CampaignGarageService / CampaignCatalog / CampaignSave"
      },
      "ownership":{
        "authority":"CampaignSave",
        "api":"CampaignFrontendIsOwned(car_id)",
        "generic_vector_contains_hook":False,
        "consumer_cutover":"targeted frontend consumers only"
      },
      "global_isonline":False,
      "sha256_before":before,
      "sha256_after":sha(ams.read_bytes()),
      "core_sha256":sha(target_core.read_bytes()),
      "backup":str(backup),
      "changes":changes
    }
    rp=out/"FRONTEND-ONLY-GARAGE-V2.json"
    rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

    print("[OK] Frontend-Only Garage v2 applied.")
    print("[MONTAR] -> CampaignFrontendGarageBuild")
    print("[OWNERSHIP] authority -> CampaignSave / explicit car-id API")
    print("[OWNERSHIP] generic vector<int>::contains -> UNTOUCHED")
    print("[CRAFTCAR] legacy path unreachable from MONTAR")
    print("[NETWORK] Global IsOnline -> FALSE")
    print(f"[AMS] {report['sha256_after']}")
    print(f"[CORE] {report['core_sha256']}")
    print(f"[REPORT] {rp}")
    return 0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print(f"[ERRO] {e}")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
