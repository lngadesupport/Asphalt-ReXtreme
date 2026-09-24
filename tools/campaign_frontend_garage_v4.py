#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

IMAGE_BASE=0x00400000
IGP_HTTPPOST_IAT_RVA=0x0112A034
IGP_HTTPPOST_PREF_VA=IMAGE_BASE+IGP_HTTPPOST_IAT_RVA

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

BUILD_VA=0x00A87960
BUILD_MAGIC=0xC0DE7713
BUILD_PREFIX=bytes.fromhex("55 8B EC")

GBBW_BUILD_CALLBACK_VA=0x00973C90
GBBW_BUILD_MAGIC=0xC0DE7714
GBBW_BUILD_PREFIX=bytes.fromhex("55 8B EC")
GBBW_BUILD_STACK_CLEANUP=8

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]

def parse_pe(d:bytes):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6)
    opt_size=u16(d,pe+20)
    opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:
        raise RuntimeError("expected x86 PE32")
    image_base=u32(d,opt+28)
    sec_off=opt+opt_size
    secs=[]
    for i in range(n):
        o=sec_off+i*40
        secs.append({
            "name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            "vsize":u32(d,o+8),
            "va":u32(d,o+12),
            "raw_size":u32(d,o+16),
            "raw":u32(d,o+20),
        })
    return image_base,secs

def va_to_file(va:int,image_base:int,secs)->int:
    rva=va-image_base
    for s in secs:
        span=max(s["vsize"],s["raw_size"])
        if s["va"]<=rva<s["va"]+span:
            return s["raw"]+(rva-s["va"])
    raise RuntimeError(f"VA 0x{va:08X} not mapped")

def pic_gateway_stub(stub_va:int,selector:int,stack_cleanup:int=0)->bytes:
    code=bytearray()
    code += b"\x68"+struct.pack("<I",selector)
    code += b"\xE8\x00\x00\x00\x00"
    code += b"\x58"
    pop_next=stub_va+len(code)
    code += b"\x05"+struct.pack("<I",(IGP_HTTPPOST_PREF_VA-pop_next)&0xffffffff)
    code += b"\xFF\x10"
    if stack_cleanup:
        if not (0 < stack_cleanup <= 0xffff):
            raise RuntimeError("invalid stack cleanup")
        code += b"\xC2"+struct.pack("<H",stack_cleanup)
    else:
        code += b"\xC3"
    return bytes(code)

BUILD_PATCH=pic_gateway_stub(BUILD_VA,BUILD_MAGIC,0)
GBBW_BUILD_PATCH=pic_gateway_stub(
    GBBW_BUILD_CALLBACK_VA,
    GBBW_BUILD_MAGIC,
    GBBW_BUILD_STACK_CLEANUP
)

def patch_entry(d:bytearray,off:int,prefix:bytes,new:bytes,label:str,changes:list):
    cur=bytes(d[off:off+len(new)])
    if cur==new:
        changes.append({"label":label,"offset":f"0x{off:08X}","status":"already-patched"})
        return

    if bytes(d[off:off+len(prefix)])!=prefix:
        raise RuntimeError(
            f"{label}: unexpected entry bytes at 0x{off:08X}: "
            + bytes(d[off:off+24]).hex(" ")
        )

    before=bytes(d[off:off+len(new)])
    d[off:off+len(new)]=new
    changes.append({
        "label":label,
        "offset":f"0x{off:08X}",
        "status":"patched",
        "before":before.hex(" "),
        "after":new.hex(" "),
    })

def apply(root:Path)->int:
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    core=root/"prebuilt"/"campaign-core"/"IGPLib_x86.dll"
    target_core=root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll"

    for p in (ams,core):
        if not p.is_file(): raise FileNotFoundError(p)

    raw=ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")

    image_base,secs=parse_pe(raw)
    if image_base!=IMAGE_BASE:
        raise RuntimeError(f"unexpected preferred image base 0x{image_base:08X}")

    build_off=va_to_file(BUILD_VA,image_base,secs)
    gbbw_cb_off=va_to_file(GBBW_BUILD_CALLBACK_VA,image_base,secs)

    d=bytearray(raw)
    changes=[]

    patch_entry(
        d,gbbw_cb_off,GBBW_BUILD_PREFIX,GBBW_BUILD_PATCH,
        "GBBW build callback -> local Campaign build (ABI ret 8)",changes
    )
    patch_entry(
        d,build_off,BUILD_PREFIX,BUILD_PATCH,
        "GS_Garage::BuildCar fallback -> local Campaign build",changes
    )

    before=sha(raw)
    backup_dir=root/"_BACKUPS"/"FRONTEND-ONLY-GARAGE-V4"
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/f"AMS.exe.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams,backup)

    tmp=ams.with_suffix(".frontend-garage-v4.tmp")
    tmp.write_bytes(d)
    verify=tmp.read_bytes()

    if verify[gbbw_cb_off:gbbw_cb_off+len(GBBW_BUILD_PATCH)]!=GBBW_BUILD_PATCH:
        raise RuntimeError("GBBW build callback verification failed")
    if verify[build_off:build_off+len(BUILD_PATCH)]!=BUILD_PATCH:
        raise RuntimeError("BuildCar verification failed")

    tmp.replace(ams)
    shutil.copy2(core,target_core)

    report={
      "phase":"Frontend-Only Garage v4",
      "architecture":"direct local callback with corrected x86 ABI",
      "network_authority":False,
      "multiplayer":False,
      "gbbw_build_callback":{
        "preferred_va":f"0x{GBBW_BUILD_CALLBACK_VA:08X}",
        "file_offset":f"0x{gbbw_cb_off:08X}",
        "selector":f"0x{GBBW_BUILD_MAGIC:08X}",
        "original_epilogue":"ret 8",
        "replacement_epilogue":"ret 8",
        "stack_cleanup":GBBW_BUILD_STACK_CLEANUP,
        "route":"GBBW -> validated GS_Garage owner -> CampaignGarageService"
      },
      "gs_garage_build_fallback":{
        "preferred_va":f"0x{BUILD_VA:08X}",
        "file_offset":f"0x{build_off:08X}",
        "selector":f"0x{BUILD_MAGIC:08X}",
        "replacement_epilogue":"ret"
      },
      "sha256_before":before,
      "sha256_after":sha(ams.read_bytes()),
      "core_sha256":sha(target_core.read_bytes()),
      "backup":str(backup),
      "changes":changes
    }

    out=root/"_TRACE_MONTAR"
    out.mkdir(parents=True,exist_ok=True)
    rp=out/"FRONTEND-ONLY-GARAGE-V4.json"
    rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

    print("[OK] Frontend-Only Garage v4 applied.")
    print("[ABI] 0x00973C90 original ret 8 -> replacement ret 8")
    print("[MONTAR] local Campaign route; no request / no server / no multiplayer")
    print(f"[AMS] {report['sha256_after']}")
    print(f"[CORE] {report['core_sha256']}")
    print(f"[REPORT] {rp}")
    return 0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:
        return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print(f"[ERRO] {e}")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
