#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

TARGETS = {
    "slot_plus_18": 0x00975040,
    "slot_plus_1C": 0x009743C0,
    "slot_plus_20": 0x00974A40,
    "slot_plus_24": 0x00974ED0,
}
KNOWN = {
    "build_request_handler": 0x00A87960,
    "craftcar_unique_caller": 0x0099FF50,
    "craftcar_start": 0x009A4BA0,
    "global_isonline": 0x00FAD9D0,
    "build_button_getter": 0x00973510,
    "preclick_secondary_updater": 0x00975A50,
}

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16), raw=u32(d,o+20), ch=u32(d,o+36)
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
        if s["va"]<=rva<s["va"]+max(s["vs"],s["rs"]):
            return s["raw"]+(rva-s["va"])
    return None

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: return out
        out.append(p); p+=1

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def next_prologue(d,start,limit=0x1800):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def scan_flow(d,start,end,ib,secs):
    out=[]; p=start
    while p<end-6:
        va=f2v(p,ib,secs)
        if va is None: p+=1; continue
        op=d[p]
        if op in (0xE8,0xE9):
            dst=(va+5+i32(d,p+1))&0xffffffff
            out.append((p,"CALL" if op==0xE8 else "JMP",dst,v2f(dst,ib,secs)))
            p+=5; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            dst=(va+6+i32(d,p+2))&0xffffffff
            out.append((p,f"JCC 0F{d[p+1]:02X}",dst,v2f(dst,ib,secs)))
            p+=6; continue
        if 0x70<=op<=0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff
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
        while p<=z:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    out.append(p); p+=5; continue
            p+=1
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        cur=d[off:off+len(exp)]
        if cur!=exp: raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE58_GARAGE_ACTION_SLOTS"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE58-GARAGE-ACTION-SLOTS.txt"
    lines=[]; w=lines.append

    w("="*82)
    w(" ReXtreme Phase 58 - GarageBottomBarWidget action-slot map")
    w("="*82)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    for name,va in TARGETS.items():
        fo=v2f(va,ib,secs)
        if fo is None:
            w(f"[{name}] VA=0x{va:08X} file=N/A")
            continue
        end=next_prologue(d,fo,0x1800)
        w(f"===== {name} =====")
        w(f"VA=0x{va:08X} File=0x{fo:08X} End=0x{end:08X} Len=0x{end-fo:X}")
        lines.extend(dump(d,fo,end))
        w("--- FLOW ---")
        hits=[]
        for p,k,dst,dfo in scan_flow(d,fo,end,ib,secs):
            if dst is None:
                w(f"{k} file=0x{p:08X}")
            else:
                tag=""
                for kn,kva in KNOWN.items():
                    if dst==kva:
                        tag=f" [{kn}]"
                        hits.append((p,kn,dst))
                w(f"{k} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'}{tag}")
        w("KnownTargetHits="+(", ".join(f"{kn}@0x{p:08X}" for p,kn,_ in hits) if hits else "none"))
        callers=direct_callers(d,va,ib,secs)
        w(f"DirectRelativeCallers={len(callers)}")
        for c in callers[:80]:
            w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X}")
            lines.extend(dump(d,c-48,c+96))
        w("")

    w("===== ABSOLUTE REFERENCES TO KNOWN TARGETS NEAR GARAGE CODE =====")
    lo=0x00570000; hi=0x00578000
    for name,va in KNOWN.items():
        refs=[p for p in find_all(d,struct.pack("<I",va)) if lo<=p<hi]
        w(f"{name} VA=0x{va:08X} refs_in_00570000_00578000={len(refs)}")
        for r in refs:
            w(f" refFile=0x{r:08X} refVA=0x{f2v(r,ib,secs):08X}")
            lines.extend(dump(d,r-48,r+80))
        w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*82)
    print(" PHASE 58 GARAGE ACTION-SLOT MAP READY")
    print("="*82)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
