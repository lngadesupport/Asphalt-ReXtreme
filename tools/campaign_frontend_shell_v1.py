#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

IMAGE_BASE=0x00400000
IGP_HTTPPOST_IAT_RVA=0x0112A034
IGP_HTTPPOST_PREF_VA=IMAGE_BASE+IGP_HTTPPOST_IAT_RVA

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

BOOT_SITE_OFF=0x0092B82A
BOOT_SITE_VA=BOOT_SITE_OFF+0x00400C00
BOOT_SITE_ORIG=bytes.fromhex("0F 84 8D 01 00 00")
BOOT_RESUME_VA=0x00D2C5BD

LOBBY_SITE_OFF=0x009171DC
LOBBY_SITE_VA=LOBBY_SITE_OFF+0x00400C00
LOBBY_SITE_ORIG=bytes.fromhex("51 8B CC C6 45")
LOBBY_RESUME_VA=0x00D18009

BUILD_CALLBACK_VA=0x00973C90
BUILD_CALLBACK_STACK=8
BUILD_PREFIX=bytes.fromhex("55 8B EC")

POPUP_OFF=0x009168B0
POPUP_ORIG=bytes.fromhex("55 8B EC 6A FF")
POPUP_RETIRED=bytes.fromhex("31 C0 C2 18 00")

CAVE_OFF=0x004693C1
CAVE_VA=0x00869FC1
CAVE_LEN=47
CAVE_FREE=b"\xCC"*CAVE_LEN

RT_BOOT=0xC0DE9005
RT_LOBBY=0xC0DE9006
RT_BUILD_SELECTED=0xC0DE9003

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def rel32(src:int,n:int,dst:int)->bytes:
    delta=dst-(src+n)
    if not -0x80000000<=delta<=0x7fffffff:
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i",delta)

def gateway_call(stub_va:int,selector:int,resume_va:int)->bytes:
    code=bytearray()
    code+=b"\x68"+struct.pack("<I",selector)
    call=stub_va+len(code)
    code+=b"\xE8\x00\x00\x00\x00"
    ret=call+5
    code+=b"\x58"
    code+=b"\x05"+struct.pack("<I",(IGP_HTTPPOST_PREF_VA-ret)&0xffffffff)
    code+=b"\xFF\x10"
    j=stub_va+len(code)
    code+=b"\xE9"+rel32(j,5,resume_va)
    return bytes(code)

def gateway_return(stub_va:int,selector:int,cleanup:int)->bytes:
    code=bytearray()
    code+=b"\x68"+struct.pack("<I",selector)
    call=stub_va+len(code)
    code+=b"\xE8\x00\x00\x00\x00"
    ret=call+5
    code+=b"\x58"
    code+=b"\x05"+struct.pack("<I",(IGP_HTTPPOST_PREF_VA-ret)&0xffffffff)
    code+=b"\xFF\x10"
    if cleanup:
        code+=b"\xC2"+struct.pack("<H",cleanup)
    else:
        code+=b"\xC3"
    return bytes(code)

BOOT_STUB=gateway_call(CAVE_VA,RT_BOOT,BOOT_RESUME_VA)
LOBBY_STUB_VA=CAVE_VA+len(BOOT_STUB)
LOBBY_STUB=gateway_call(LOBBY_STUB_VA,RT_LOBBY,LOBBY_RESUME_VA)
CAVE_PATCH=(BOOT_STUB+LOBBY_STUB)
if len(CAVE_PATCH)>CAVE_LEN:
    raise RuntimeError("frontend shell cave too small")
CAVE_PATCH+=b"\xCC"*(CAVE_LEN-len(CAVE_PATCH))

BOOT_PATCH=b"\xE9"+rel32(BOOT_SITE_VA,5,CAVE_VA)+b"\x90"
LOBBY_PATCH=b"\xE9"+rel32(LOBBY_SITE_VA,5,LOBBY_STUB_VA)

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]

def parse_pe(d:bytes):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append((u32(d,o+12),u32(d,o+8),u32(d,o+16),u32(d,o+20)))
    return ib,secs

def va2file(va:int,ib:int,secs)->int:
    r=va-ib
    for sva,vs,rs,raw in secs:
        if sva<=r<sva+max(vs,rs):
            return raw+(r-sva)
    raise RuntimeError(f"VA 0x{va:08X} not mapped")

def guarded_patch(d:bytearray,off:int,before:bytes,after:bytes,label:str,changes:list):
    cur=bytes(d[off:off+len(after)])
    if cur==after:
        changes.append({"label":label,"status":"already-patched","offset":f"0x{off:08X}"})
        return
    if bytes(d[off:off+len(before)])!=before:
        raise RuntimeError(f"{label}: unexpected bytes at 0x{off:08X}")
    d[off:off+len(after)]=after
    changes.append({"label":label,"status":"patched","offset":f"0x{off:08X}"})

def apply(root:Path)->int:
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    runtime=root/"prebuilt"/"campaign-runtime"/"IGPLib_x86.dll"
    if not ams.is_file(): raise FileNotFoundError(ams)
    if not runtime.is_file(): raise FileNotFoundError(runtime)

    raw=ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must be hard FALSE")

    ib,secs=parse_pe(raw)
    if ib!=IMAGE_BASE: raise RuntimeError("unexpected image base")
    build_off=va2file(BUILD_CALLBACK_VA,ib,secs)
    build_patch=gateway_return(BUILD_CALLBACK_VA,RT_BUILD_SELECTED,BUILD_CALLBACK_STACK)

    d=bytearray(raw)
    changes=[]

    cave=bytes(d[CAVE_OFF:CAVE_OFF+CAVE_LEN])
    if cave not in (CAVE_FREE,CAVE_PATCH):
        raise RuntimeError("clean frontend cave unavailable")
    if cave==CAVE_FREE:
        d[CAVE_OFF:CAVE_OFF+CAVE_LEN]=CAVE_PATCH
        changes.append({"label":"install clean BOOT/LOBBY intents","status":"patched"})

    guarded_patch(d,BOOT_SITE_OFF,BOOT_SITE_ORIG,BOOT_PATCH,
        "frontend BOOT -> runtime intent",changes)
    guarded_patch(d,LOBBY_SITE_OFF,LOBBY_SITE_ORIG,LOBBY_PATCH,
        "frontend LOBBY -> runtime intent",changes)
    guarded_patch(d,build_off,BUILD_PREFIX,build_patch,
        "frontend MONTAR -> BUILD_SELECTED_CAR",changes)
    guarded_patch(d,POPUP_OFF,POPUP_ORIG,POPUP_RETIRED,
        "remove obsolete online-service popup presentation",changes)

    before=sha(raw)
    bdir=root/"_BACKUPS"/"CLEAN-FRONTEND-SHELL-V1"
    bdir.mkdir(parents=True,exist_ok=True)
    bak=bdir/f"AMS.exe.{before}.bak"
    if not bak.exists(): shutil.copy2(ams,bak)

    tmp=ams.with_suffix(".clean-shell-v1.tmp")
    tmp.write_bytes(d)
    tmp.replace(ams)
    shutil.copy2(runtime,root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll")

    out=root/"_TRACE_MONTAR"
    out.mkdir(parents=True,exist_ok=True)
    report={
      "phase":"Clean Frontend Shell v1",
      "rule":"original frontend only",
      "gameplay_structures_from_original":False,
      "boot_selector":"0xC0DE9005",
      "lobby_selector":"0xC0DE9006",
      "build_selector":"0xC0DE9003",
      "build_input":"no object pointer; selected car belongs to Campaign Runtime",
      "network":False,
      "multiplayer":False,
      "sha256_before":before,
      "sha256_after":sha(ams.read_bytes()),
      "runtime_sha256":sha((root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll").read_bytes()),
      "changes":changes
    }
    rp=out/"CLEAN-FRONTEND-SHELL-V1.json"
    rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

    print("[OK] Clean Frontend Shell v1 applied.")
    print("[BOOT] frontend -> Campaign Runtime intent")
    print("[LOBBY] frontend -> Campaign Runtime intent")
    print("[MONTAR] frontend -> BUILD_SELECTED_CAR")
    print("[ORIGINAL GAMEPLAY STRUCTURES] NONE")
    print("[NETWORK] NONE")
    print("[MULTIPLAYER] NONE")
    print("[AMS]",report["sha256_after"])
    print("[RUNTIME]",report["runtime_sha256"])
    print("[REPORT]",rp)
    return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:
        return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print("[ERRO]",e)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
