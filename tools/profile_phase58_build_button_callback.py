#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

TARGETS = {
    "build_button_callback": 0x00973C90,
    "neighbor_callback_A":   0x00973D20,
    "neighbor_callback_B":   0x00973E40,
    "build_button_ui_updater": 0x00972B90,
    "build_request_handler": 0x00A87960,
    "craftcar_unique_caller":0x0099FF50,
    "craftcar_start":        0x009A4BA0,
    "global_IsOnline":       0x00FAD9D0,
}

P53_OFF=0x00574FA7
P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2
P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45
P55=bytes.fromhex("90 90 90 90 90 90")
GLOBAL_OFF=0x00BACDD0
GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0
POPUP=bytes.fromhex("31 C0 C2 18 00")

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4] != b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4) != 0x14c or u16(d,opt) != 0x10b:
        raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16),
            raw=u32(d,o+20), ch=u32(d,o+36)
        ))
    return ib,secs

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"] <= off < s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"] <= rva < s["va"]+max(s["vs"],s["rs"]):
            return s["raw"]+(rva-s["va"])
    return None

def is_exec_file(off,secs):
    for s in secs:
        if s["raw"] <= off < s["raw"]+s["rs"]:
            return bool(s["ch"] & 0x20000000)
    return False

def dump(d,a,z):
    out=[]
    a=max(0,a); z=min(len(d),z)
    for p in range(a,z,16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(z,p+16)]))
    return out

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: break
        out.append(p); p+=1
    return out

def prologue_before(d,near,back=0x800):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3] == b"\x55\x8B\xEC":
            return p
    return None

def next_prologue(d,start,limit=0x600):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p >= 0 else min(len(d),start+limit)

def flow(d,start,end,ib,secs):
    out=[]; p=start
    while p < end-6:
        va=f2v(p,ib,secs)
        if va is None:
            p+=1; continue
        op=d[p]
        if op in (0xE8,0xE9):
            dst=(va+5+i32(d,p+1)) & 0xffffffff
            out.append((p,"CALL" if op==0xE8 else "JMP",dst,v2f(dst,ib,secs)))
            p+=5; continue
        if op==0x0F and 0x80 <= d[p+1] <= 0x8F:
            dst=(va+6+i32(d,p+2)) & 0xffffffff
            out.append((p,f"JCC 0F{d[p+1]:02X}",dst,v2f(dst,ib,secs)))
            p+=6; continue
        if 0x70 <= op <= 0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel) & 0xffffffff
            out.append((p,f"JCC {op:02X}",dst,v2f(dst,ib,secs)))
            p+=2; continue
        if op==0xFF and p+1<end and ((d[p+1]>>3)&7)==2:
            out.append((p,"CALL [indirect]",None,None))
        p+=1
    return out

def direct_callers(d,target,ib,secs):
    out=[]
    for s in secs:
        if not (s["ch"] & 0x20000000): continue
        p=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p <= z:
            if d[p]==0xE8:
                src=f2v(p,ib,secs)
                if src is not None and ((src+5+i32(d,p+1)) & 0xffffffff)==target:
                    out.append(p); p+=5; continue
            p+=1
    return out

def target_refs_in_window(d,start,end):
    rows=[]
    for name,va in TARGETS.items():
        pat=struct.pack("<I",va)
        p=start
        while True:
            p=d.find(pat,p,end)
            if p<0: break
            rows.append((p,name,va,"ABS_DWORD"))
            p+=1
    return sorted(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    guards=[
        ("Phase53",P53_OFF,P53),
        ("Phase54",P54_OFF,P54),
        ("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),
        ("Phase36Popup",POPUP_OFF,POPUP),
    ]
    for name,off,exp in guards:
        cur=d[off:off+len(exp)]
        if cur != exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE58_BUILD_BUTTON_CALLBACK"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE58-BUILD-BUTTON-CALLBACK.txt"

    lines=[]; w=lines.append
    w("="*82)
    w(" ReXtreme Phase 58 - actual build_button callback map")
    w("="*82)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    # Re-document callback registration around the exact build_button block.
    reg_start=v2f(0x00972DD0,ib,secs)
    reg_end=v2f(0x00972F40,ib,secs)
    if reg_start is not None and reg_end is not None:
        w("===== BUILD_BUTTON CALLBACK REGISTRATION WINDOW =====")
        lines.extend(dump(d,reg_start,reg_end))
        w("")
        cb_pat=struct.pack("<I",TARGETS["build_button_callback"])
        refs=[p for p in find_all(d,cb_pat) if reg_start <= p < reg_end]
        w("CallbackPointerRefsInRegistration="+(",".join(f"0x{x:08X}" for x in refs) if refs else "NONE"))
        w("")

    # Exact callback bodies and neighboring callbacks registered by the same UI updater.
    for label in ("build_button_callback","neighbor_callback_A","neighbor_callback_B"):
        va=TARGETS[label]
        fo=v2f(va,ib,secs)
        w(f"===== {label} =====")
        w(f"VA=0x{va:08X} File={('0x%08X'%fo) if fo is not None else 'N/A'}")
        if fo is None:
            w("")
            continue

        # The callback pointer may land at a thunk or in a function body.
        pb=prologue_before(d,fo)
        w(f"NearestPrologueBefore={('0x%08X'%pb) if pb is not None else 'N/A'}")
        # Prefer exact pointer start; cap at next standard prologue, otherwise 0x400.
        end=next_prologue(d,fo,0x400)
        w(f"DetectedEnd=0x{end:08X} LengthFromPointer=0x{end-fo:X}")
        lines.extend(dump(d,fo,end))
        w("--- CONTROL FLOW ---")
        for p,k,dst,dfo in flow(d,fo,end,ib,secs):
            if dst is None:
                w(f"{k} file=0x{p:08X}")
            else:
                tag=""
                for tn,tv in TARGETS.items():
                    if dst==tv: tag=f" [{tn}]"
                w(f"{k} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'}{tag}")
        w("--- KNOWN TARGET ABSOLUTE REFS ---")
        refs=target_refs_in_window(d,fo,end)
        if not refs: w("NONE")
        for p,n,v,k in refs:
            w(f"{k} file=0x{p:08X} -> {n}=0x{v:08X}")
        w("--- DIRECT RELATIVE CALLERS ---")
        callers=direct_callers(d,va,ib,secs)
        w(f"Count={len(callers)}")
        for c in callers[:50]:
            cv=f2v(c,ib,secs)
            pr=prologue_before(d,c)
            w(f" callerFile=0x{c:08X} callerVA={('0x%08X'%cv) if cv is not None else 'N/A'} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
            lines.extend(dump(d,c-48,c+80))
        w("")

    # Search executable references to callback pointer itself: registration / tables / stores.
    w("===== EXECUTABLE DWORD REFS TO CALLBACK POINTERS =====")
    for label in ("build_button_callback","neighbor_callback_A","neighbor_callback_B"):
        va=TARGETS[label]
        refs=[p for p in find_all(d,struct.pack("<I",va)) if is_exec_file(p,secs)]
        w(f"[{label}] VA=0x{va:08X} refs={len(refs)}")
        for r in refs[:60]:
            rv=f2v(r,ib,secs)
            pr=prologue_before(d,r)
            w(f" refFile=0x{r:08X} refVA={('0x%08X'%rv) if rv is not None else 'N/A'} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
            lines.extend(dump(d,r-48,r+80))
        w("")

    # Map any direct calls made by build callback to functions that themselves call known
    # build/request/CraftCar functions within a shallow one-hop view.
    bfo=v2f(TARGETS["build_button_callback"],ib,secs)
    if bfo is not None:
        bend=next_prologue(d,bfo,0x400)
        direct_dsts=[]
        for p,k,dst,dfo in flow(d,bfo,bend,ib,secs):
            if k=="CALL" and dst is not None and dfo is not None:
                direct_dsts.append((dst,dfo))
        w("===== BUILD CALLBACK ONE-HOP CALLEE WINDOWS =====")
        seen=set()
        for dst,dfo in direct_dsts:
            if dst in seen: continue
            seen.add(dst)
            w(f"CalleeVA=0x{dst:08X} File=0x{dfo:08X}")
            lines.extend(dump(d,dfo,min(len(d),dfo+0x180)))
            refs=target_refs_in_window(d,dfo,min(len(d),dfo+0x180))
            for p,n,v,k in refs:
                w(f"  {k} file=0x{p:08X} -> {n}=0x{v:08X}")
            w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*82)
    print(" PHASE 58 ACTUAL BUILD_BUTTON CALLBACK MAP READY")
    print("="*82)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
