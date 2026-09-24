#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

EXPECTED="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
FN_OFF=0x006A4100
FN_VA =0x00AA4D00
MAXLEN=0x800
IMAGE_BASE=0x00400000

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+osz
    sec=[]
    for i in range(n):
        o=so+40*i
        sec.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16), raw=u32(d,o+20),
            ch=u32(d,o+36)
        ))
    return ib,sec

def file_to_va(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def va_to_file(va,ib,secs):
    rva=va-ib
    for s in secs:
        span=max(s["vs"],s["rs"])
        if s["va"]<=rva<s["va"]+span:
            return s["raw"]+(rva-s["va"])
    return None

def hexdump(d,a,z):
    out=[]
    for p in range(a,z,16):
        q=min(p+16,z)
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:q]))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE47_CRAFTCAR_COMPLETION"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE47-CRAFTCAR-COMPLETION.txt"

    d=ams.read_bytes()
    sha=hashlib.sha256(d).hexdigest()
    if sha!=EXPECTED:
        raise SystemExit(f"Expected Phase36-only hash {EXPECTED}, got {sha}")

    ib,secs=parse_pe(d)
    start=FN_OFF; end=min(len(d),start+MAXLEN)

    # Find earliest plausible function return after prologue.
    returns=[]
    p=start+3
    while p<end:
        op=d[p]
        if op==0xC3:
            returns.append((p,"RET"))
        elif op==0xC2 and p+2<end:
            returns.append((p,f"RET 0x{u16(d,p+1):X}"))
        p+=1

    # Direct relative calls / branches in the analysis window.
    flow=[]
    p=start
    while p<end-6:
        op=d[p]
        va=file_to_va(p,ib,secs)
        if va is None: p+=1; continue
        if op in (0xE8,0xE9):
            rel=i32(d,p+1); dst=(va+5+rel)&0xffffffff
            flow.append((p,"CALL" if op==0xE8 else "JMP",dst,va_to_file(dst,ib,secs)))
            p+=5; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            rel=i32(d,p+2); dst=(va+6+rel)&0xffffffff
            flow.append((p,f"JCC 0F{d[p+1]:02X}",dst,va_to_file(dst,ib,secs)))
            p+=6; continue
        if 0x70<=op<=0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff
            flow.append((p,f"JCC {op:02X}",dst,va_to_file(dst,ib,secs)))
            p+=2; continue
        p+=1

    # Find references to stack arguments [ebp+8,+C,+10,...] and key parent-relative
    # displacements from observer subobject: +0x114/+0x118 => parent +0x3AC/+0x3B0.
    stack_refs=[]
    field_refs=[]
    for p in range(start,end-7):
        # common ModRM with EBP disp8: ?? 45 xx / ?? 4D xx / ?? 55 xx / etc
        if d[p] in (0x8B,0x89,0x8A,0x88,0xFF,0x83,0x80,0xC7,0xC6,0x8D) and (d[p+1]&0xC7)==0x45:
            disp=d[p+2]
            if disp in (0x08,0x0C,0x10,0x14,0x18,0x1C,0x20,0x24):
                stack_refs.append((p,disp,d[p:p+8]))
        # disp32 memory operands; report known observer-relative offsets.
        if d[p] in (0x8B,0x89,0x8D,0xC7,0xC6,0x83,0x80) and (d[p+1]&0xC0)==0x80:
            disp=i32(d,p+2)
            if disp in (0x114,0x118,0xC4,0x298,0x35C,0x3AC,0x3B0,-0x298):
                field_refs.append((p,disp,d[p:p+12]))

    # Detect virtual calls FF 5x/9x with displacement.
    virtual=[]
    for p in range(start,end-7):
        if d[p]==0xFF:
            modrm=d[p+1]
            reg=(modrm>>3)&7
            if reg==2: # CALL r/m32
                virtual.append((p,d[p:p+8]))

    lines=[]
    w=lines.append
    w("="*64)
    w(" ReXtreme Phase 47 - CraftCar Completion Callback Focus")
    w("="*64)
    w(f"AMS_SHA256={sha}")
    w(f"FunctionVA=0x{FN_VA:08X}")
    w(f"FunctionFile=0x{FN_OFF:08X}")
    w("")
    w("===== RETURN CANDIDATES =====")
    for o,t in returns[:80]:
        w(f"file=0x{o:08X} VA=0x{file_to_va(o,ib,secs):08X} {t}")
    w("")
    w("===== STACK ARGUMENT REFERENCES =====")
    for o,disp,raw in stack_refs:
        w(f"file=0x{o:08X} [EBP+0x{disp:X}] bytes="+" ".join(f"{x:02X}" for x in raw))
    w("")
    w("===== OBSERVER/PARENT FIELD REFERENCES =====")
    for o,disp,raw in field_refs:
        parent = disp+0x298 if disp>=0 and disp in (0x114,0x118,0xC4) else None
        extra=f" => parent+0x{parent:X}" if parent is not None else ""
        w(f"file=0x{o:08X} disp={disp:+#x}{extra} bytes="+" ".join(f"{x:02X}" for x in raw))
    w("")
    w("===== DIRECT CONTROL FLOW =====")
    for o,k,dst,fo in flow:
        w(f"{k:10s} file=0x{o:08X} -> VA=0x{dst:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
    w("")
    w("===== VIRTUAL CALL-LIKE SITES =====")
    for o,raw in virtual:
        w(f"file=0x{o:08X} bytes="+" ".join(f"{x:02X}" for x in raw))
    w("")
    w("===== RAW FUNCTION WINDOW =====")
    lines.extend(hexdump(d,start,end))
    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*64)
    print(" PHASE 47 CRAFTCAR COMPLETION MAP READY")
    print("="*64)
    print(f"Report: {out}")

if __name__=="__main__":
    main()
