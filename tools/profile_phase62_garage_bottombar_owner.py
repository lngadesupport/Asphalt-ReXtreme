#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path
from collections import deque

GBBW_CTOR = 0x0096EB10
GBBW_DTOR = 0x0096EDF0
GBBW_VTABLE = 0x01831854
GS_GARAGE_CTOR1 = 0x00E00B20
GS_GARAGE_CTOR2 = 0x00E0E8D0
GS_GARAGE_VTABLE = 0x0186A9CC
BUILD_HANDLER = 0x00A87960

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
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16),
            raw=u32(d,o+20), ch=u32(d,o+36)
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
    return bool(s and (s["ch"]&0x20000000))

def is_exec_va(va,ib,secs):
    fo=v2f(va,ib,secs)
    return fo is not None and is_exec_file(fo,secs)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def guess_prologue(d,near,back=0x3000):
    lo=max(0,near-back)
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
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; z=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=z:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target_va:
                    out.append(p); p+=5; continue
            p+=1
    return out

def direct_calls(d,func_va,ib,secs,limit=0x4000):
    st=v2f(func_va,ib,secs)
    if st is None:return []
    en=next_prologue(d,st,limit)
    out=[]; p=st
    while p<en-5:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,dst))
            p+=5; continue
        p+=1
    return out

def recursive_paths_to(d,start_va,target_va,ib,secs,max_depth=6,max_nodes=3000):
    q=deque([(start_va,[start_va],0)])
    seen={start_va:0}
    hits=[]
    while q and len(seen)<max_nodes:
        va,path,depth=q.popleft()
        if depth>=max_depth: continue
        for p,dst in direct_calls(d,va,ib,secs):
            np=path+[dst]
            if dst==target_va:
                hits.append((p,np))
                continue
            if is_exec_va(dst,ib,secs) and (dst not in seen or seen[dst]>depth+1):
                seen[dst]=depth+1
                q.append((dst,np,depth+1))
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
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE62_GARAGE_BOTTOMBAR_OWNER"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE62-GARAGE-BOTTOMBAR-OWNER.txt"
    lines=[];w=lines.append

    w("="*92)
    w(" ReXtreme Phase 62 - GarageBottomBarWidget owner/delegate wiring map")
    w("="*92)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w(f"GarageBottomBarWidgetCtor=0x{GBBW_CTOR:08X}")
    w(f"GarageBottomBarWidgetVtable=0x{GBBW_VTABLE:08X}")
    w(f"GS_GarageVtable=0x{GS_GARAGE_VTABLE:08X}")
    w(f"BuildHandler=0x{BUILD_HANDLER:08X}")
    w("")

    # Constructor/destructor body.
    for label,va in [("GBBW_CTOR",GBBW_CTOR),("GBBW_DTOR",GBBW_DTOR)]:
        st=v2f(va,ib,secs)
        w(f"===== {label} =====")
        if st is None:
            w("not mapped"); continue
        en=next_prologue(d,st,0x1800)
        w(f"VA=0x{va:08X} File=0x{st:08X} End=0x{en:08X}")
        lines.extend(dump(d,st,en))
        w("")

    # Direct callers of ctor.
    callers=direct_callers(d,GBBW_CTOR,ib,secs)
    w("===== DIRECT CALLERS OF GarageBottomBarWidget CTOR =====")
    w(f"Count={len(callers)}")
    caller_funcs=[]
    for c in callers:
        pr=guess_prologue(d,c)
        pva=f2v(pr,ib,secs) if pr is not None else None
        caller_funcs.append(pva)
        w(f"callFile=0x{c:08X} callVA=0x{f2v(c,ib,secs):08X} callerPrologue={('0x%08X'%pr) if pr is not None else 'N/A'} callerVA={('0x%08X'%pva) if pva is not None else 'N/A'}")
        lines.extend(dump(d,c-128,c+192))
        w("")

    # Trace callers upward several levels and flag GS_Garage constructor reachability.
    w("===== CALLER CHAINS ABOVE GBBW CTOR =====")
    frontier=[(va,[va]) for va in caller_funcs if va is not None]
    seen=set()
    for depth in range(6):
        nxt=[]
        w(f"-- depth {depth} --")
        for va,path in frontier:
            if va in seen: continue
            seen.add(va)
            ups=direct_callers(d,va,ib,secs)
            w(f"node=0x{va:08X} callers={len(ups)} pathDown="+" <- ".join(f"0x{x:08X}" for x in path))
            for c in ups[:120]:
                pr=guess_prologue(d,c)
                pva=f2v(pr,ib,secs) if pr is not None else None
                mark=""
                if pva in (GS_GARAGE_CTOR1,GS_GARAGE_CTOR2): mark=" [GS_GARAGE_CTOR]"
                w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X} parentFn={('0x%08X'%pva) if pva is not None else 'N/A'}{mark}")
                if pva is not None and pva not in seen:
                    nxt.append((pva,[pva]+path))
        frontier=nxt
        if not frontier: break
    w("")

    # Explicit GS_Garage ctor bodies and direct calls to any lower chain.
    for label,va in [("GS_GARAGE_CTOR1",GS_GARAGE_CTOR1),("GS_GARAGE_CTOR2",GS_GARAGE_CTOR2)]:
        st=v2f(va,ib,secs)
        w(f"===== {label} =====")
        if st is None:
            w("not mapped"); continue
        en=next_prologue(d,st,0x3000)
        w(f"VA=0x{va:08X} File=0x{st:08X} End=0x{en:08X}")
        lines.extend(dump(d,st,en))
        calls=direct_calls(d,va,ib,secs,0x3000)
        for p,dst in calls:
            tag=""
            if dst==GBBW_CTOR: tag=" [GBBW_CTOR]"
            elif dst==BUILD_HANDLER: tag=" [BUILD_HANDLER]"
            elif dst in caller_funcs: tag=" [GBBW_CTOR_CALLER]"
            w(f" CALL file=0x{p:08X} -> VA=0x{dst:08X}{tag}")
        w("")

    # Search vtable absolute refs around ctor-related callsites to identify factories/classes.
    w("===== GBBW VTABLE EXECUTABLE REFS =====")
    refs=[r for r in find_all(d,struct.pack("<I",GBBW_VTABLE)) if is_exec_file(r,secs)]
    w(f"Count={len(refs)}")
    for r in refs:
        pr=guess_prologue(d,r)
        pva=f2v(pr,ib,secs) if pr is not None else None
        w(f"refFile=0x{r:08X} refVA=0x{f2v(r,ib,secs):08X} fn={('0x%08X'%pva) if pva is not None else 'N/A'}")
        lines.extend(dump(d,r-96,r+256))
        w("")

    # Search direct GS_Garage ctor -> GBBW ctor paths, depth <= 6.
    w("===== GS_GARAGE CTOR -> GBBW CTOR RECURSIVE PATHS =====")
    for gva in (GS_GARAGE_CTOR1,GS_GARAGE_CTOR2):
        hits=recursive_paths_to(d,gva,GBBW_CTOR,ib,secs,6,4000)
        w(f"from=0x{gva:08X} paths={len(hits)}")
        for p,path in hits[:50]:
            w(" path="+" -> ".join(f"0x{x:08X}" for x in path)+f" finalCallFile=0x{p:08X}")
    w("")

    # Inspect all writes of GS_Garage vtable and nearby calls for widget creation.
    w("===== GS_GARAGE VTABLE INSTALL SITES =====")
    grefs=[r for r in find_all(d,struct.pack("<I",GS_GARAGE_VTABLE)) if is_exec_file(r,secs)]
    for r in grefs:
        pr=guess_prologue(d,r)
        pva=f2v(pr,ib,secs) if pr is not None else None
        w(f"refFile=0x{r:08X} refVA=0x{f2v(r,ib,secs):08X} fn={('0x%08X'%pva) if pva is not None else 'N/A'}")
        lines.extend(dump(d,r-160,r+768))
        w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*92)
    print(" PHASE 62 GARAGE BOTTOMBAR OWNER MAP READY")
    print("="*92)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
