#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

# This module is the only binary-facing presentation adapter.
# It does not call or preserve any original gameplay/business flow.
# Original code is used only as frontend presentation and input surface.

IMAGE_BASE=0x00400000
GATEWAY_IAT_RVA=0x0112A034
GATEWAY_IAT_VA=IMAGE_BASE+GATEWAY_IAT_RVA

OFFLINE_POLICY_OFF=0x00BACDD0
OFFLINE_POLICY=bytes.fromhex("31 C0 C3 90 90 90 90")

# Frontend presentation boundaries.
BOOT_PATCH_OFF=0x0092B82A
BOOT_PATCH_VA=BOOT_PATCH_OFF+0x00400C00
BOOT_EXPECTED=bytes.fromhex("0F 84 8D 01 00 00")
BOOT_CONTINUE_VA=0x00D2C5BD

HOME_PATCH_OFF=0x009171DC
HOME_PATCH_VA=HOME_PATCH_OFF+0x00400C00
HOME_EXPECTED=bytes.fromhex("51 8B CC C6 45")
HOME_CONTINUE_VA=0x00D18009

# Presentation state writer for the visible MONTAR control.
# We replace the old computed value; no old state is consumed.
GARAGE_ACTION_RENDER_OFF=0x00574FA7
GARAGE_ACTION_RENDER_EXPECTED=bytes.fromhex("FF 75 D8")
GARAGE_ACTION_RENDER_ACTIVE=bytes.fromhex("6A 01 90")

# Frontend input event boundary. Entire old body is replaced.
GARAGE_ACTION_EVENT_VA=0x00973C90
GARAGE_ACTION_EVENT_EXPECTED=bytes.fromhex("55 8B EC")
GARAGE_ACTION_EVENT_STACK_CLEANUP=8

# Presentation-only obsolete service popup: disabled because the product has
# no online-service state at all.
SERVICE_POPUP_OFF=0x009168B0
SERVICE_POPUP_EXPECTED=bytes.fromhex("55 8B EC 6A FF")
SERVICE_POPUP_DISABLED=bytes.fromhex("31 C0 C2 18 00")

# Fresh executable padding used only by our presentation adapter.
BRIDGE_PAD_OFF=0x004693C1
BRIDGE_PAD_VA=0x00869FC1
BRIDGE_PAD_SIZE=47
BRIDGE_PAD_EMPTY=b"\xCC"*BRIDGE_PAD_SIZE

SEL_BOOT=0xDEC0A001
SEL_HOME=0xDEC0A002
SEL_BUILD=0xDEC0A003

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def rel32(src:int,n:int,dst:int)->bytes:
    v=dst-(src+n)
    if not -0x80000000<=v<=0x7fffffff:
        raise ValueError("rel32 range")
    return struct.pack("<i",v)

def gateway_then_continue(stub_va:int,selector:int,resume_va:int)->bytes:
    b=bytearray()
    b+=b"\x68"+struct.pack("<I",selector)
    call_va=stub_va+len(b)
    b+=b"\xE8\0\0\0\0"
    after_call=call_va+5
    b+=b"\x58"
    b+=b"\x05"+struct.pack("<I",(GATEWAY_IAT_VA-after_call)&0xffffffff)
    b+=b"\xFF\x10"
    jump_va=stub_va+len(b)
    b+=b"\xE9"+rel32(jump_va,5,resume_va)
    return bytes(b)

def gateway_then_return(stub_va:int,selector:int,cleanup:int)->bytes:
    b=bytearray()
    b+=b"\x68"+struct.pack("<I",selector)
    call_va=stub_va+len(b)
    b+=b"\xE8\0\0\0\0"
    after_call=call_va+5
    b+=b"\x58"
    b+=b"\x05"+struct.pack("<I",(GATEWAY_IAT_VA-after_call)&0xffffffff)
    b+=b"\xFF\x10"
    b+=b"\xC2"+struct.pack("<H",cleanup)
    return bytes(b)

BOOT_BRIDGE=gateway_then_continue(BRIDGE_PAD_VA,SEL_BOOT,BOOT_CONTINUE_VA)
HOME_BRIDGE_VA=BRIDGE_PAD_VA+len(BOOT_BRIDGE)
HOME_BRIDGE=gateway_then_continue(HOME_BRIDGE_VA,SEL_HOME,HOME_CONTINUE_VA)
BRIDGE_BYTES=BOOT_BRIDGE+HOME_BRIDGE
if len(BRIDGE_BYTES)>BRIDGE_PAD_SIZE:
    raise RuntimeError("presentation bridge overflow")
BRIDGE_BYTES+=b"\xCC"*(BRIDGE_PAD_SIZE-len(BRIDGE_BYTES))

BOOT_REPLACEMENT=b"\xE9"+rel32(BOOT_PATCH_VA,5,BRIDGE_PAD_VA)+b"\x90"
HOME_REPLACEMENT=b"\xE9"+rel32(HOME_PATCH_VA,5,HOME_BRIDGE_VA)

def u16(d,o): return struct.unpack_from("<H",d,o)[0]
def u32(d,o): return struct.unpack_from("<I",d,o)[0]

def pe_sections(d:bytes):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise ValueError("bad PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    ib=u32(d,opt+28); so=opt+osz
    sections=[]
    for i in range(n):
        o=so+i*40
        sections.append((u32(d,o+12),u32(d,o+8),u32(d,o+16),u32(d,o+20)))
    return ib,sections

def va_to_file(va:int,ib:int,sections)->int:
    rva=va-ib
    for sva,vsize,rsize,raw in sections:
        if sva<=rva<sva+max(vsize,rsize):
            return raw+(rva-sva)
    raise ValueError(f"unmapped VA {va:#x}")

def replace(data:bytearray,off:int,before:bytes,after:bytes,label:str,changes:list):
    current=bytes(data[off:off+len(after)])
    if current==after:
        changes.append({"name":label,"status":"already"})
        return
    if bytes(data[off:off+len(before)])!=before:
        raise RuntimeError(f"{label}: guard mismatch at {off:#x}")
    data[off:off+len(after)]=after
    changes.append({"name":label,"status":"replaced","offset":f"0x{off:08X}"})

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
    if raw[OFFLINE_POLICY_OFF:OFFLINE_POLICY_OFF+len(OFFLINE_POLICY)]!=OFFLINE_POLICY:
        raise RuntimeError("base is not hard-offline")

    ib,sections=pe_sections(raw)
    if ib!=IMAGE_BASE:
        raise RuntimeError("unexpected image base")

    garage_event_off=va_to_file(GARAGE_ACTION_EVENT_VA,ib,sections)
    garage_event_replacement=gateway_then_return(
        GARAGE_ACTION_EVENT_VA,SEL_BUILD,GARAGE_ACTION_EVENT_STACK_CLEANUP
    )

    data=bytearray(raw)
    changes=[]

    current_pad=bytes(data[BRIDGE_PAD_OFF:BRIDGE_PAD_OFF+BRIDGE_PAD_SIZE])
    if current_pad not in (BRIDGE_PAD_EMPTY,BRIDGE_BYTES):
        raise RuntimeError("presentation bridge region is not pristine")
    if current_pad==BRIDGE_PAD_EMPTY:
        data[BRIDGE_PAD_OFF:BRIDGE_PAD_OFF+BRIDGE_PAD_SIZE]=BRIDGE_BYTES
        changes.append({"name":"new presentation bridge","status":"installed"})

    replace(data,BOOT_PATCH_OFF,BOOT_EXPECTED,BOOT_REPLACEMENT,
            "boot visual boundary",changes)
    replace(data,HOME_PATCH_OFF,HOME_EXPECTED,HOME_REPLACEMENT,
            "home visual boundary",changes)
    replace(data,GARAGE_ACTION_RENDER_OFF,
            GARAGE_ACTION_RENDER_EXPECTED,GARAGE_ACTION_RENDER_ACTIVE,
            "garage action render command",changes)
    replace(data,garage_event_off,GARAGE_ACTION_EVENT_EXPECTED,
            garage_event_replacement,"garage action input command",changes)
    replace(data,SERVICE_POPUP_OFF,SERVICE_POPUP_EXPECTED,SERVICE_POPUP_DISABLED,
            "obsolete service popup",changes)

    backup=root/"_BACKUPS"/"REX-PRESENTATION-ADAPTER-V2"
    backup.mkdir(parents=True,exist_ok=True)
    before_hash=sha(raw)
    bak=backup/f"AMS.exe.{before_hash}.bak"
    if not bak.exists():
        shutil.copy2(ams,bak)

    tmp=ams.with_suffix(".presentation-v2.tmp")
    tmp.write_bytes(data)
    tmp.replace(ams)
    shutil.copy2(runtime,root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll")

    report={
        "schema":2,
        "component":"Rex Presentation Adapter V2",
        "original_code_allowed":"frontend presentation/input surface only",
        "original_gameplay_state_read":False,
        "original_gameplay_flow_called":False,
        "previous_campaign_code_called":False,
        "network":False,
        "multiplayer":False,
        "commands":{
            "boot":"REX_INTENT_BOOT",
            "home":"REX_INTENT_ENTER_HOME",
            "garage_render":"ACTIVE",
            "garage_input":"REX_INTENT_BUILD_CAR",
        },
        "changes":changes,
        "ams_sha256":sha(ams.read_bytes()),
        "runtime_sha256":sha((root/"_PACKAGE_PHASE5"/"IGPLib_x86.dll").read_bytes()),
    }
    out=root/"_TRACE_MONTAR"/"REX-PRESENTATION-ADAPTER-V2.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("[OK] Rex Presentation Adapter V2 installed.")
    print("[ORIGINAL GAMEPLAY STATE] NONE")
    print("[ORIGINAL GAMEPLAY FLOW] NONE")
    print("[GARAGE RENDER] ACTIVE")
    print("[GARAGE INPUT] REX_INTENT_BUILD_CAR")
    print("[REPORT]",out)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
