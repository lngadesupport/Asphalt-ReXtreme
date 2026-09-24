#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

SLOT = 0x110
BUILD_REQ = 0x00A87960
GARAGE_VTABLE = 0x0186A9CC

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
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
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

def sec_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]: return s
    return None

def is_exec_file(off,secs):
    s=sec_for_file(off,secs)
    return bool(s and (s["ch"] & 0x20000000))

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def guess_prologue(d,near,back=0x3000):
    lo=max(0,near-back)
    # Prefer classic MSVC frame function.
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC":
            return p
    return None

def next_prologue(d,start,limit=0x4000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def direct_callers(d,target_va,ib,secs):
    out=[]
    for s in secs:
        if not (s["ch"] & 0x20000000): continue
        p=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=z:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target_va:
                    out.append(p)
                    p+=5
                    continue
            p+=1
    return out

def decode_ff_call_disp32(d,p,end):
    if p+6>end or d[p]!=0xFF: return None
    modrm=d[p+1]
    if ((modrm>>3)&7)!=2: return None
    mod=(modrm>>6)&3
    rm=modrm&7
    regs=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]
    if mod!=2: return None
    if rm==4:
        if p+7>end: return None
        sib=d[p+2]
        disp=u32(d,p+3)
        base=sib&7
        index=(sib>>3)&7
        scale=1<<((sib>>6)&3)
        return {
            "len":7,"disp":disp,
            "operand":f"[{regs[base]}+{regs[index]}*{scale}+0x{disp:X}]",
            "modrm":modrm,"sib":sib
        }
    disp=u32(d,p+2)
    return {
        "len":6,"disp":disp,
        "operand":f"[{regs[rm]}+0x{disp:X}]",
        "modrm":modrm,"sib":None
    }

def scan_slot_calls(d,secs,slot):
    hits=[]
    for s in secs:
        if not (s["ch"] & 0x20000000): continue
        p=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
        while p<end-6:
            if d[p]==0xFF:
                dec=decode_ff_call_disp32(d,p,end)
                if dec and dec["disp"]==slot:
                    hits.append((p,dec))
                    p+=dec["len"]; continue
            p+=1
    return hits

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p); p+=1

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
        if cur!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE60_SCREEN_SLOT110_CALLERS"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE60-SCREEN-SLOT110-CALLERS.txt"

    lines=[]; w=lines.append
    w("="*88)
    w(" ReXtreme Phase 60 - screen virtual slot +0x110 caller map")
    w("="*88)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("TargetBuildRequestHandler=0x%08X"%BUILD_REQ)
    w("GS_GarageVtable=0x%08X"%GARAGE_VTABLE)
    w("")

    hits=scan_slot_calls(d,secs,SLOT)
    w(f"===== ALL VIRTUAL CALLS WITH DISP +0x{SLOT:X} =====")
    w(f"Count={len(hits)}")
    funcs={}
    for p,dec in hits:
        va=f2v(p,ib,secs)
        pr=guess_prologue(d,p)
        funcs.setdefault(pr,[]).append((p,dec))
        w(f"callFile=0x{p:08X} callVA=0x{va:08X} operand={dec['operand']} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
        lines.extend(dump(d,p-96,p+128))
        w("")

    w("===== CONTAINING FUNCTIONS =====")
    for pr,arr in sorted(funcs.items(), key=lambda kv:(kv[0] is None, kv[0] or 0)):
        if pr is None:
            w("[no prologue]")
            continue
        pva=f2v(pr,ib,secs)
        end=next_prologue(d,pr,0x3000)
        w(f"Function file=0x{pr:08X} VA=0x{pva:08X} end=0x{end:08X} slot110Calls={len(arr)}")
        callers=direct_callers(d,pva,ib,secs)
        w(f"DirectCallers={len(callers)}")
        for c in callers[:100]:
            cp=guess_prologue(d,c)
            w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X} callerPrologue={('0x%08X'%cp) if cp is not None else 'N/A'}")
            lines.extend(dump(d,c-80,c+128))
        # look for useful constants / compare sequences around the function
        lines.extend(dump(d,pr,min(end,pr+0x1000)))
        w("")

    w("===== GS_GARAGE VTABLE REFERENCES IN EXECUTABLE CODE =====")
    pat=struct.pack("<I",GARAGE_VTABLE)
    refs=[r for r in find_all(d,pat) if is_exec_file(r,secs)]
    w(f"Count={len(refs)}")
    for r in refs:
        pr=guess_prologue(d,r)
        w(f"refFile=0x{r:08X} refVA=0x{f2v(r,ib,secs):08X} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
        lines.extend(dump(d,r-96,r+160))
        w("")

    w("===== BUILD REQUEST HANDLER DIRECT REFERENCES / CALLERS =====")
    bref=find_all(d,struct.pack("<I",BUILD_REQ))
    w(f"AbsoluteRefs={len(bref)}")
    for r in bref:
        s=sec_for_file(r,secs)
        w(f"refFile=0x{r:08X} section={(s or {}).get('name','NOSEC')} exec={is_exec_file(r,secs)}")
    callers=direct_callers(d,BUILD_REQ,ib,secs)
    w(f"DirectCallers={len(callers)}")
    for c in callers:
        w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X}")
        lines.extend(dump(d,c-96,c+160))

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*88)
    print(" PHASE 60 SCREEN SLOT +0x110 CALLER MAP READY")
    print("="*88)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
