#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

# Phase51 normalization
P51_OFF=0x0068712F
P51_ORIG=bytes.fromhex("6A 00")
P51_PATCH=bytes.fromhex("6A 01")
STABLE="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"

TARGETS=[
    ("build_button UI updater",0x00572100,0x00972D00,0x300),
    ("build_button getter",0x00572910,0x00973510,0x100),
    ("build_button secondary updater",0x00574E70,0x00975A70,0x300),
]

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

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(a,z,16)]

def find_prologue(d,near,back=0x500):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE52_PRECLICK_BUILD_BUTTON"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE52-PRECLICK-BUILD-BUTTON.txt"

    d=bytearray(ams.read_bytes())
    p51_reverted=False
    if d[P51_OFF:P51_OFF+2]==P51_PATCH:
        backup=root/"_PACKAGE_PHASE5"/"AMS.PRE-PHASE52-PRECLICK-MAP.exe"
        if not backup.exists(): backup.write_bytes(d)
        d[P51_OFF:P51_OFF+2]=P51_ORIG
        ams.write_bytes(d)
        p51_reverted=True
    elif d[P51_OFF:P51_OFF+2]!=P51_ORIG:
        raise SystemExit(f"Unexpected Phase51 bytes: {d[P51_OFF:P51_OFF+2].hex(' ')}")

    sha=hashlib.sha256(d).hexdigest()
    if sha!=STABLE:
        raise SystemExit(f"Expected stable Phase36-only hash {STABLE}, got {sha}")

    ib,secs=parse_pe(d)
    execsecs=[s for s in secs if s["ch"]&0x20000000]

    lines=[]; w=lines.append
    w("="*72)
    w(" ReXtreme Phase 52 - pre-click build_button / spinner map")
    w("="*72)
    w(f"AMS_SHA256={sha}")
    w(f"Phase51Reverted={p51_reverted}")
    w("")

    for label,guess_off,guess_va,span in TARGETS:
        pro=find_prologue(d,guess_off)
        start=pro if pro is not None else guess_off
        # next prologue after at least 0x20
        nxt=d.find(b"\x55\x8B\xEC",start+0x20,min(len(d),start+span+0x300))
        end=nxt if nxt!=-1 else min(len(d),start+span)

        w(f"===== {label} =====")
        w(f"StartFile=0x{start:08X} StartVA=0x{f2v(start,ib,secs):08X} EndFile=0x{end:08X}")
        lines.extend(dump(d,start,end))
        w("")
        w("--- CONTROL FLOW ---")
        p=start
        while p<end-6:
            op=d[p]; va=f2v(p,ib,secs)
            if va is None: p+=1; continue
            if op in (0xE8,0xE9):
                dst=(va+5+i32(d,p+1))&0xffffffff; fo=v2f(dst,ib,secs)
                w(f"{'CALL' if op==0xE8 else 'JMP ':4s} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
                p+=5; continue
            if op==0x0F and 0x80<=d[p+1]<=0x8F:
                dst=(va+6+i32(d,p+2))&0xffffffff; fo=v2f(dst,ib,secs)
                w(f"JCC 0F{d[p+1]:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
                p+=6; continue
            if 0x70<=op<=0x7F:
                rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
                dst=(va+2+rel)&0xffffffff; fo=v2f(dst,ib,secs)
                w(f"JCC {op:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
                p+=2; continue
            p+=1
        w("")
        w("--- BOOL/STATE CANDIDATES ---")
        for p in range(start,end-10):
            # push 0/1, mov byte imm 0/1, cmp/test around likely UI calls
            if d[p:p+2] in (b"\x6A\x00",b"\x6A\x01"):
                w(f"push{d[p+1]} @ 0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(end,p+16)]))
            if d[p]==0xC6 and d[p+2] in (0,1):
                w(f"C6 bool-ish @ 0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(end,p+16)]))
        w("")

        # Direct callers of actual start VA.
        tva=f2v(start,ib,secs)
        callers=[]
        if tva is not None:
            for s in execsecs:
                p=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
                while p<=z:
                    if d[p]==0xE8:
                        src=f2v(p,ib,secs)
                        if src is not None and ((src+5+i32(d,p+1))&0xffffffff)==tva:
                            callers.append(p)
                        p+=5
                    else: p+=1
        w(f"--- DIRECT CALLERS: {len(callers)} ---")
        for c in callers[:40]:
            w(f"callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X}")
            lines.extend(dump(d,max(0,c-48),min(len(d),c+80)))
        w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*72)
    print(" PHASE 52 PRE-CLICK BUILD BUTTON MAP READY")
    print("="*72)
    print("Phase51 reverted:",p51_reverted)
    print("Report:",out)

if __name__=="__main__":
    main()
