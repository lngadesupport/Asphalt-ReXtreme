#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

EXPECTED="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
FN_OFF=0x00572910
FN_VA =0x00973510
WINDOW=0x500

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
        o=so+40*i
        secs.append(dict(name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
                         vs=u32(d,o+8),va=u32(d,o+12),rs=u32(d,o+16),raw=u32(d,o+20),
                         ch=u32(d,o+36)))
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

def hexline(d,p,q):
    return f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:q])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE50_BUILD_BUTTON_STATE"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE50-BUILD-BUTTON-STATE.txt"

    d=ams.read_bytes()
    sha=hashlib.sha256(d).hexdigest()
    if sha!=EXPECTED:
        raise SystemExit(f"Expected Phase36-only hash {EXPECTED}, got {sha}")
    ib,secs=parse_pe(d)

    start=FN_OFF
    end=min(len(d),start+WINDOW)

    # stop at next classic prologue after minimum body
    nxt=d.find(b"\x55\x8B\xEC",start+0x20,end)
    if nxt!=-1: end=nxt

    lines=[]
    w=lines.append
    w("="*68)
    w(" ReXtreme Phase 50 - build_button state function")
    w("="*68)
    w(f"AMS_SHA256={sha}")
    w(f"FunctionVA=0x{FN_VA:08X}")
    w(f"FunctionFile=0x{FN_OFF:08X}")
    w(f"DetectedEnd=0x{end:08X}")
    w("")

    w("===== RAW =====")
    for p in range(start,end,16):
        w(hexline(d,p,min(p+16,end)))
    w("")

    w("===== CONTROL FLOW =====")
    p=start
    while p<end-6:
        op=d[p]
        va=f2v(p,ib,secs)
        if va is None: p+=1; continue
        if op in (0xE8,0xE9):
            dst=(va+5+i32(d,p+1))&0xffffffff
            fo=v2f(dst,ib,secs)
            w(f"{'CALL' if op==0xE8 else 'JMP ':4s} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=5; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            dst=(va+6+i32(d,p+2))&0xffffffff
            fo=v2f(dst,ib,secs)
            w(f"JCC 0F{d[p+1]:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=6; continue
        if 0x70<=op<=0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff
            fo=v2f(dst,ib,secs)
            w(f"JCC {op:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=2; continue
        p+=1
    w("")

    # Find common bool state writes and virtual calls.
    w("===== STATE-LIKE WRITES / VIRTUAL CALLS =====")
    for p in range(start,end-8):
        # C6 / C7 stores
        if d[p] in (0xC6,0xC7,0x88,0x89):
            w(hexline(d,p,min(p+12,end)))
        if d[p]==0xFF and ((d[p+1]>>3)&7)==2:
            w("VCALL "+hexline(d,p,min(p+10,end)))
    w("")

    # Direct callers
    w("===== DIRECT CALLERS =====")
    callers=[]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        a=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
        p=a
        while p<=z:
            if d[p]==0xE8:
                src=f2v(p,ib,secs)
                if src is not None and ((src+5+i32(d,p+1))&0xffffffff)==FN_VA:
                    callers.append(p)
                p+=5
            else:
                p+=1
    w(f"Count={len(callers)}")
    for c in callers:
        w(f"callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X}")
        a=max(0,c-48); z=min(len(d),c+80)
        for p in range(a,z,16):
            w(hexline(d,p,min(p+16,z)))

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*68)
    print(" PHASE 50 BUILD BUTTON STATE MAP READY")
    print("="*68)
    print("Report:",out)

if __name__=="__main__":
    main()
