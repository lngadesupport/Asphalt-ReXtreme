#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

STABLE="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
SITE_OFF=0x00687110
SITE_ORIG=bytes.fromhex("8B 55 EC 8B CE")
SITE_P48 =bytes.fromhex("E9 AC 22 DE FF")
CAVE_OFF=0x004693C1
CAVE_ORIG=bytes([0xCC])*47

FN_OFF=0x0056E7B0
FN_VA =0x0096F3B0
WINDOW=0x1000

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

def in_exec(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return bool(s["ch"]&0x20000000)
    return False

def hexdump(d,a,z):
    out=[]
    for p in range(a,z,16):
        q=min(p+16,z)
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:q]))
    return out

def all_refs(d, value):
    pat=struct.pack("<I",value)
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: break
        out.append(p); p+=1
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE49_BUILD_BUTTON_MAP"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE49-BUILD-BUTTON-MAP.txt"

    d=bytearray(ams.read_bytes())

    # Normalize failed Phase48 experiment.
    if d[SITE_OFF:SITE_OFF+5]==SITE_P48:
        backup=root/"_PACKAGE_PHASE5"/"AMS.PRE-PHASE49-BUILD-BUTTON-MAP.exe"
        if not backup.exists():
            backup.write_bytes(d)
        d[SITE_OFF:SITE_OFF+5]=SITE_ORIG
        d[CAVE_OFF:CAVE_OFF+47]=CAVE_ORIG
        ams.write_bytes(d)
        phase48_reverted=True
    elif d[SITE_OFF:SITE_OFF+5]==SITE_ORIG:
        phase48_reverted=False
    else:
        raise SystemExit("Unexpected Phase48 hook bytes at 0x00687110")

    sha=hashlib.sha256(d).hexdigest()
    if sha!=STABLE:
        raise SystemExit(f"After Phase48 normalization expected stable Phase36 hash {STABLE}, got {sha}")

    ib,secs=parse_pe(d)

    # Locate relevant ASCII UI strings exactly.
    terms=[
        b"build_button",
        b"template_build_button",
        b"bcn_bottom_bar/template_build_button",
        b"STR_BP_READY_TO_BUILD",
        b"STR_BP_HINT_TO_BUILD",
    ]

    lines=[]
    w=lines.append
    w("="*68)
    w(" ReXtreme Phase 49 - Build Button / Spinner Focus Map")
    w("="*68)
    w(f"AMS_SHA256={sha}")
    w(f"Phase48Reverted={phase48_reverted}")
    w(f"TargetFunctionVA=0x{FN_VA:08X}")
    w(f"TargetFunctionFile=0x{FN_OFF:08X}")
    w("")

    w("===== UI STRING LOCATIONS + EXECUTABLE XREFS =====")
    for term in terms:
        w(f"TERM={term.decode('ascii')}")
        pos=0; count=0
        while True:
            pos=d.find(term,pos)
            if pos<0: break
            count+=1
            va=f2v(pos,ib,secs)
            w(f" stringFile=0x{pos:08X} stringVA={('0x%08X'%va) if va is not None else 'N/A'}")
            if va is not None:
                refs=[r for r in all_refs(d,va) if in_exec(r,secs)]
                w(f" executableRefs={len(refs)}")
                for r in refs[:40]:
                    w(f"  refFile=0x{r:08X} refVA=0x{f2v(r,ib,secs):08X}")
                    lines.extend(hexdump(d,max(0,r-32),min(len(d),r+80)))
            pos+=1
        if not count: w(" not found")
        w("")

    start=FN_OFF
    end=min(len(d),start+WINDOW)

    # Stop display at next likely standard function prologue after a safe minimum.
    next_pro=None
    pat=b"\x55\x8B\xEC"
    p=start+0x20
    while p<end-3:
        q=d.find(pat,p,end)
        if q<0: break
        # accept first prologue aligned after at least 0x40 bytes
        next_pro=q
        break
    fn_end=next_pro if next_pro is not None else end

    w("===== TARGET FUNCTION RAW WINDOW =====")
    w(f"DetectedEnd={('0x%08X'%fn_end)} Length=0x{fn_end-start:X}")
    lines.extend(hexdump(d,start,fn_end))
    w("")

    w("===== TARGET FUNCTION CONTROL FLOW =====")
    p=start
    while p<fn_end-6:
        op=d[p]
        va=f2v(p,ib,secs)
        if va is None: p+=1; continue
        if op in (0xE8,0xE9):
            rel=i32(d,p+1); dst=(va+5+rel)&0xffffffff; fo=v2f(dst,ib,secs)
            w(f"{'CALL' if op==0xE8 else 'JMP ':4s} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=5; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            rel=i32(d,p+2); dst=(va+6+rel)&0xffffffff; fo=v2f(dst,ib,secs)
            w(f"JCC 0F{d[p+1]:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=6; continue
        if 0x70<=op<=0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff; fo=v2f(dst,ib,secs)
            w(f"JCC {op:02X} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
            p+=2; continue
        p+=1
    w("")

    w("===== DIRECT CALLERS OF TARGET =====")
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
        w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X}")
        lines.extend(hexdump(d,max(0,c-48),min(len(d),c+96)))

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*68)
    print(" PHASE 49 BUILD BUTTON MAP READY")
    print("="*68)
    print("Phase48 reverted:",phase48_reverted)
    print("Report:",out)

if __name__=="__main__":
    main()
