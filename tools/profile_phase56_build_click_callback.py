#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

TARGETS = {
    "ready_to_build_ui": 0x00974480,
    "candidate_click_handler": 0x009747F0,
    "template_build_button_builder": 0x0096F3B0,
    "build_button_getter": 0x00973510,
    "preclick_secondary_updater": 0x00975A50,
    "build_request_handler": 0x00A87960,
    "craftcar_unique_caller": 0x0099FF50,
    "craftcar_start": 0x009A4BA0,
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
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16), raw=u32(d,o+20),
            ch=u32(d,o+36)
        ))
    return ib,secs

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        span=max(s["vs"],s["rs"])
        if s["va"]<=rva<s["va"]+span:
            return s["raw"]+(rva-s["va"])
    return None

def sec_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return s
    return None

def is_exec_file(off,secs):
    s=sec_for_file(off,secs)
    return bool(s and (s["ch"] & 0x20000000))

def is_exec_va(va,ib,secs):
    fo=v2f(va,ib,secs)
    return fo is not None and is_exec_file(fo,secs)

def dump(d,a,z):
    out=[]
    a=max(0,a); z=min(len(d),z)
    for p in range(a,z,16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: break
        out.append(p); p+=1
    return out

def prologue(d,near,back=0x1200):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC":
            return p
    return None

def scan_flow(d,start,end,ib,secs):
    rows=[]
    p=start
    while p<end-6:
        va=f2v(p,ib,secs)
        if va is None:
            p+=1; continue
        op=d[p]
        if op in (0xE8,0xE9):
            dst=(va+5+i32(d,p+1))&0xffffffff
            rows.append((p,"CALL" if op==0xE8 else "JMP",dst,v2f(dst,ib,secs)))
            p+=5; continue
        if op==0x0F and p+5<end and 0x80<=d[p+1]<=0x8F:
            dst=(va+6+i32(d,p+2))&0xffffffff
            rows.append((p,f"JCC 0F{d[p+1]:02X}",dst,v2f(dst,ib,secs)))
            p+=6; continue
        if 0x70<=op<=0x7F and p+1<end:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff
            rows.append((p,f"JCC {op:02X}",dst,v2f(dst,ib,secs)))
            p+=2; continue
        # FF /2 indirect call, useful for vtable slots.
        if op==0xFF and p+1<end:
            modrm=d[p+1]
            reg=(modrm>>3)&7
            if reg==2:
                rows.append((p,"CALL [indirect]",None,None))
        p+=1
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE56_BUILD_CLICK_CALLBACK"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE56-BUILD-CLICK-CALLBACK.txt"

    # Current-chain guards: report, do not mutate.
    guards=[
        ("Phase53",P53_OFF,P53),
        ("Phase54",P54_OFF,P54),
        ("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),
        ("Phase36Popup",POPUP_OFF,POPUP),
    ]
    for name,off,exp in guards:
        cur=d[off:off+len(exp)]
        if cur!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    lines=[]; w=lines.append
    w("="*78)
    w(" ReXtreme Phase 56 - build_button click/callback map")
    w("="*78)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("ImageBase=0x%08X"%ib)
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    w("===== TARGET ADDRESS REFERENCES (ABSOLUTE DWORD XREFS) =====")
    for name,va in TARGETS.items():
        refs=find_all(d,struct.pack("<I",va))
        w(f"[{name}] VA=0x{va:08X} refs={len(refs)}")
        for r in refs[:100]:
            s=sec_for_file(r,secs)
            kind="EXEC" if is_exec_file(r,secs) else (s["name"] if s else "NOSEC")
            rv=f2v(r,ib,secs)
            pr=prologue(d,r) if is_exec_file(r,secs) else None
            w(f" refFile=0x{r:08X} refVA={('0x%08X'%rv) if rv is not None else 'N/A'} section={kind} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
            lines.extend(dump(d,r-48,r+80))
        w("")

    # Candidate vtables/tables: any non-exec reference to target address.
    w("===== CANDIDATE VTABLE / CALLBACK TABLES =====")
    seen=set()
    for name,va in TARGETS.items():
        for r in find_all(d,struct.pack("<I",va)):
            if is_exec_file(r,secs): continue
            base=max(0,r-0x80)
            base &= ~3
            key=(base,r)
            if key in seen: continue
            seen.add(key)
            w(f"Target={name} targetVA=0x{va:08X} hitFile=0x{r:08X} section={(sec_for_file(r,secs) or {}).get('name','NOSEC')}")
            # Decode dwords around hit as possible function pointers.
            for p in range(max(0,r-0x60)&~3,min(len(d)-4,r+0x64),4):
                val=u32(d,p)
                mark="*" if p==r else " "
                if is_exec_va(val,ib,secs):
                    fo=v2f(val,ib,secs)
                    pr=prologue(d,fo) if fo is not None else None
                    w(f"{mark} tableFile=0x{p:08X} -> execVA=0x{val:08X} file=0x{fo:08X} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
                elif p==r:
                    w(f"* tableFile=0x{p:08X} -> 0x{val:08X}")
            w("")

    # Exact candidate handler body and neighbors.
    for label,start_va,span in [
        ("candidate_click_handler",0x009747F0,0x500),
        ("ready_to_build_ui",0x00974480,0x500),
        ("template_build_button_builder",0x0096F3B0,0x380),
        ("preclick_secondary_updater",0x00975A50,0x3B0),
    ]:
        start=v2f(start_va,ib,secs)
        if start is None: continue
        # stop at next standard prologue after minimum range if present
        nxt=d.find(b"\x55\x8B\xEC",start+0x20,min(len(d),start+span))
        end=nxt if nxt!=-1 else min(len(d),start+span)
        w(f"===== {label} BODY =====")
        w(f"StartVA=0x{start_va:08X} StartFile=0x{start:08X} EndFile=0x{end:08X}")
        lines.extend(dump(d,start,end))
        w("--- FLOW ---")
        for p,k,dst,fo in scan_flow(d,start,end,ib,secs):
            if dst is None:
                w(f"{k} file=0x{p:08X}")
            else:
                w(f"{k} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
        w("")

    # Direct relative callers of all target functions.
    w("===== DIRECT RELATIVE CALLERS =====")
    execsecs=[s for s in secs if s["ch"]&0x20000000]
    for name,tva in TARGETS.items():
        callers=[]
        for s in execsecs:
            p=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
            while p<=z:
                if d[p]==0xE8:
                    src=f2v(p,ib,secs)
                    if src is not None and ((src+5+i32(d,p+1))&0xffffffff)==tva:
                        callers.append(p); p+=5; continue
                p+=1
        w(f"[{name}] directCallers={len(callers)}")
        for c in callers[:80]:
            w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X} prologue={('0x%08X'%prologue(d,c)) if prologue(d,c) is not None else 'N/A'}")
            lines.extend(dump(d,c-64,c+96))
        w("")

    # Search for function-pointer-like stores of candidate handler immediate.
    w("===== MOV/PUSH IMMEDIATE USES OF CANDIDATE HANDLER =====")
    hva=TARGETS["candidate_click_handler"]
    pat=struct.pack("<I",hva)
    for r in find_all(d,pat):
        if not is_exec_file(r,secs): continue
        w(f"handler immediate in executable @ file=0x{r:08X} VA=0x{f2v(r,ib,secs):08X}")
        lines.extend(dump(d,r-64,r+96))
    w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*78)
    print(" PHASE 56 BUILD CLICK/CALLBACK MAP READY")
    print("="*78)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
