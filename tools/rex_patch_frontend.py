#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

IMAGE_BASE=0x00400000
IAT_RVA=0x0112A034
IAT_VA=IMAGE_BASE+IAT_RVA

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

# Presentation boundaries only. We replace the original decision/dispatch code
# at these sites; no original gameplay flow is called after the patch.
BOOT_OFF=0x0092B82A
BOOT_VA=BOOT_OFF+0x00400C00
BOOT_BEFORE=bytes.fromhex("0F 84 8D 01 00 00")
BOOT_RESUME=0x00D2C5BD

HOME_OFF=0x009171DC
HOME_VA=HOME_OFF+0x00400C00
HOME_BEFORE=bytes.fromhex("51 8B CC C6 45")
HOME_RESUME=0x00D18009

# The original frontend periodically decides how to render the build control.
# We replace that decision with a constant presentation state: active button.
BUILD_RENDER_OFF=0x00574FA7
BUILD_RENDER_BEFORE=bytes.fromhex("FF 75 D8")
BUILD_RENDER_AFTER =bytes.fromhex("6A 01 90")

# Build-control event entry. Its old body is replaced completely.
BUILD_EVENT_VA=0x00973C90
BUILD_EVENT_STACK=8
BUILD_EVENT_PROLOGUE=bytes.fromhex("55 8B EC")

POPUP_OFF=0x009168B0
POPUP_BEFORE=bytes.fromhex("55 8B EC 6A FF")
POPUP_AFTER =bytes.fromhex("31 C0 C2 18 00")

CAVE_OFF=0x004693C1
CAVE_VA=0x00869FC1
CAVE_LEN=47
CAVE_EMPTY=b"\xCC"*CAVE_LEN

SEL_BOOT =0xDEC0A001
SEL_HOME =0xDEC0A002
SEL_BUILD=0xDEC0A003

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def rel32(src:int,n:int,dst:int)->bytes:
    v=dst-(src+n)
    if not -0x80000000<=v<=0x7fffffff:
        raise ValueError("rel32 range")
    return struct.pack("<i",v)

def call_and_jump(stub_va:int,selector:int,resume:int)->bytes:
    b=bytearray()
    b+=b"\x68"+struct.pack("<I",selector)
    call=stub_va+len(b)
    b+=b"\xE8\0\0\0\0"
    after_call=call+5
    b+=b"\x58"
    b+=b"\x05"+struct.pack("<I",(IAT_VA-after_call)&0xffffffff)
    b+=b"\xFF\x10"
    j=stub_va+len(b)
    b+=b"\xE9"+rel32(j,5,resume)
    return bytes(b)

def call_and_return(stub_va:int,selector:int,cleanup:int)->bytes:
    b=bytearray()
    b+=b"\x68"+struct.pack("<I",selector)
    call=stub_va+len(b)
    b+=b"\xE8\0\0\0\0"
    after_call=call+5
    b+=b"\x58"
    b+=b"\x05"+struct.pack("<I",(IAT_VA-after_call)&0xffffffff)
    b+=b"\xFF\x10"
    b+=b"\xC2"+struct.pack("<H",cleanup)
    return bytes(b)

BOOT_STUB=call_and_jump(CAVE_VA,SEL_BOOT,BOOT_RESUME)
HOME_STUB_VA=CAVE_VA+len(BOOT_STUB)
HOME_STUB=call_and_jump(HOME_STUB_VA,SEL_HOME,HOME_RESUME)
CAVE_DATA=BOOT_STUB+HOME_STUB
if len(CAVE_DATA)>CAVE_LEN:
    raise RuntimeError("cave capacity")
CAVE_DATA+=b"\xCC"*(CAVE_LEN-len(CAVE_DATA))

BOOT_AFTER=b"\xE9"+rel32(BOOT_VA,5,CAVE_VA)+b"\x90"
HOME_AFTER=b"\xE9"+rel32(HOME_VA,5,HOME_STUB_VA)

def u16(d,o): return struct.unpack_from("<H",d,o)[0]
def u32(d,o): return struct.unpack_from("<I",d,o)[0]

def pe_sections(d:bytes):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise ValueError("bad PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    ib=u32(d,opt+28); so=opt+osz
    out=[]
    for i in range(n):
        o=so+i*40
        out.append((u32(d,o+12),u32(d,o+8),u32(d,o+16),u32(d,o+20)))
    return ib,out

def va_to_file(va:int,ib:int,secs)->int:
    r=va-ib
    for sva,vsize,rsize,raw in secs:
        if sva<=r<sva+max(vsize,rsize):
            return raw+(r-sva)
    raise ValueError(f"unmapped VA {va:#x}")

def replace(d:bytearray,off:int,before:bytes,after:bytes,label:str,log:list):
    cur=bytes(d[off:off+len(after)])
    if cur==after:
        log.append({"name":label,"status":"already"})
        return
    if bytes(d[off:off+len(before)])!=before:
        raise RuntimeError(f"{label}: guard mismatch at {off:#x}")
    d[off:off+len(after)]=after
    log.append({"name":label,"status":"replaced","offset":f"0x{off:08X}"})

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",type=Path,required=True)
    ns=ap.parse_args()
    root=ns.project_root.resolve()

    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    runtime=root/"prebuilt"/"rex-campaign"/"IGPLib_x86.dll"
    if not ams.is_file(): raise FileNotFoundError(ams)
    if not runtime.is_file(): raise FileNotFoundError(runtime)

    raw=ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("REX base is not hard-offline")

    ib,secs=pe_sections(raw)
    if ib!=IMAGE_BASE: raise RuntimeError("image base changed")
    build_off=va_to_file(BUILD_EVENT_VA,ib,secs)
    build_after=call_and_return(BUILD_EVENT_VA,SEL_BUILD,BUILD_EVENT_STACK)

    d=bytearray(raw)
    changes=[]

    cave=bytes(d[CAVE_OFF:CAVE_OFF+CAVE_LEN])
    if cave not in (CAVE_EMPTY,CAVE_DATA):
        raise RuntimeError("frontend injection region is not pristine")
    if cave==CAVE_EMPTY:
        d[CAVE_OFF:CAVE_OFF+CAVE_LEN]=CAVE_DATA
        changes.append({"name":"new boot/home frontend bridge","status":"installed"})

    replace(d,BOOT_OFF,BOOT_BEFORE,BOOT_AFTER,"boot presentation boundary",changes)
    replace(d,HOME_OFF,HOME_BEFORE,HOME_AFTER,"home presentation boundary",changes)
    replace(d,BUILD_RENDER_OFF,BUILD_RENDER_BEFORE,BUILD_RENDER_AFTER,
            "build control render state",changes)
    replace(d,build_off,BUILD_EVENT_PROLOGUE,build_after,
            "build control input event",changes)
    replace(d,POPUP_OFF,POPUP_BEFORE,POPUP_AFTER,
            "obsolete online popup entry",changes)

    backup=root/"_BACKUPS"/"REX-CAMPAIGN-FRONTEND"
    backup.mkdir(parents=True,exist_ok=True)
    before_hash=sha(raw)
    b=backup/f"AMS.exe.{before_hash}.bak"
    if not b.exists(): shutil.copy2(ams,b)

    tmp=ams.with_suffix(".rex.tmp")
    tmp.write_bytes(d)
    tmp.replace(ams)
    shutil.copy2(runtime,root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll")

    report={
        "schema":1,
        "frontend_original_only":True,
        "old_gameplay_code_called":False,
        "old_campaign_code_called":False,
        "network":False,
        "multiplayer":False,
        "selectors":{
            "boot":hex(SEL_BOOT),
            "home":hex(SEL_HOME),
            "build":hex(SEL_BUILD),
        },
        "changes":changes,
        "ams_sha256":sha(ams.read_bytes()),
        "runtime_sha256":sha((root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll").read_bytes()),
    }
    out=root/"_TRACE_MONTAR"/"REX-CAMPAIGN-FRONTEND.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("[OK] New Campaign Edition frontend bridge installed.")
    print("[OLD GAMEPLAY CODE] NONE")
    print("[OLD CAMPAIGN CODE] NONE")
    print("[MONTAR RENDER] ACTIVE")
    print("[MONTAR INPUT] REX_INTENT_BUILD_CAR")
    print("[REPORT]",out)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
