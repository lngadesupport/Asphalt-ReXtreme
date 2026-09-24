#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path
from collections import deque

GS_GARAGE_VTABLE = 0x0186A9CC
BUILD_HANDLER = 0x00A87960
FOCUS = {
    "candidate_caller_fn": 0x00968330,
    "candidate_slot110_fn": 0x00968410,
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

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p); p+=1

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

def next_prologue(d,start,limit=0x3000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def direct_calls(d,func_va,ib,secs,limit=0x3000):
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

def scan_slot110_functions(d,ib,secs):
    funcs=set()
    hits=[]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
        while p<end-6:
            if d[p]==0xFF:
                modrm=d[p+1]
                reg=(modrm>>3)&7; mod=(modrm>>6)&3; rm=modrm&7
                if reg==2 and mod==2 and rm!=4 and u32(d,p+2)==0x110:
                    pr=guess_prologue(d,p)
                    pva=f2v(pr,ib,secs) if pr is not None else None
                    if pva is not None: funcs.add(pva)
                    hits.append((p,pva,modrm))
                    p+=6; continue
            p+=1
    return sorted(funcs),hits

def ascii_z(d,off,limit=300):
    if off is None or off<0 or off>=len(d):return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("ascii","replace")
    except:return ""
    if not s:return ""
    if sum(0x20<=ord(c)<0x7f for c in s) < max(1,int(len(s)*0.9)): return ""
    return s

def rtti_name_for_vtable_file(d,vf,ib,secs):
    if vf<4:return None
    col_va=u32(d,vf-4)
    col_f=v2f(col_va,ib,secs)
    if col_f is None or col_f+20>len(d):return None
    td_va=u32(d,col_f+12)
    td_f=v2f(td_va,ib,secs)
    if td_f is None:return None
    return ascii_z(d,td_f+8)

def candidate_vtables_for_method(d,method_va,ib,secs):
    out=[]
    for hit in find_all(d,struct.pack("<I",method_va)):
        if is_exec_file(hit,secs): continue
        for vf in range(hit,max(4,hit-0x800)-1,-4):
            name=rtti_name_for_vtable_file(d,vf,ib,secs)
            if not (name and name.startswith(".?A")): continue
            idx=(hit-vf)//4
            good=True
            for p in range(vf,hit+4,4):
                if not is_exec_va(u32(d,p),ib,secs):
                    good=False; break
            if good:
                out.append((vf,f2v(vf,ib,secs),idx,idx*4,name,hit))
                break
    # dedupe
    uniq=[]; seen=set()
    for x in out:
        key=(x[0],x[2])
        if key not in seen:
            seen.add(key); uniq.append(x)
    return uniq

def recursive_hits(d,start_va,target_set,ib,secs,max_depth=4,max_nodes=1500):
    q=deque([(start_va,0,[start_va])])
    seen={start_va:0}
    hits=[]
    while q and len(seen)<max_nodes:
        va,depth,path=q.popleft()
        if depth>=max_depth: continue
        for p,dst in direct_calls(d,va,ib,secs):
            if dst in target_set:
                hits.append((p,dst,depth+1,path+[dst]))
            if is_exec_va(dst,ib,secs) and (dst not in seen or seen[dst]>depth+1):
                seen[dst]=depth+1
                q.append((dst,depth+1,path+[dst]))
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        cur=d[off:off+len(exp)]
        if cur!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE61_GARAGE_SLOT110_OWNER"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE61-GARAGE-SLOT110-OWNER.txt"
    lines=[];w=lines.append

    w("="*90)
    w(" ReXtreme Phase 61 - GS_Garage / slot+0x110 owner bridge")
    w("="*90)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("GS_GarageVtable=0x%08X"%GS_GARAGE_VTABLE)
    w("BuildHandler=0x%08X"%BUILD_HANDLER)
    w("")

    slotfuncs,slothits=scan_slot110_functions(d,ib,secs)
    w("===== SLOT+0x110 CONTAINING FUNCTIONS =====")
    w("Count=%d"%len(slotfuncs))
    for va in slotfuncs:
        w(" 0x%08X"%va)
    w("")

    gvf=v2f(GS_GARAGE_VTABLE,ib,secs)
    if gvf is None: raise SystemExit("GS_Garage vtable not mapped")
    w("===== GS_GARAGE VTABLE METHODS =====")
    gs_methods=[]
    for idx in range(0,0x180//4):
        va=u32(d,gvf+idx*4)
        if not is_exec_va(va,ib,secs):
            w(f"stop at index={idx} slot=0x{idx*4:X} value=0x{va:08X}")
            break
        gs_methods.append((idx,idx*4,va))
        mark=" BUILD_HANDLER" if va==BUILD_HANDLER else ""
        w(f"index={idx:02d} slot=0x{idx*4:03X} VA=0x{va:08X}{mark}")
    w("")

    w("===== GS_GARAGE METHODS -> SLOT110 FUNCTIONS =====")
    anyhit=False
    targetset=set(slotfuncs)
    for idx,slot,va in gs_methods:
        # direct
        for p,dst in direct_calls(d,va,ib,secs):
            if dst in targetset:
                anyhit=True
                w(f"DIRECT gsSlot=0x{slot:X} method=0x{va:08X} callFile=0x{p:08X} -> slot110Fn=0x{dst:08X}")
        # recursive depth <=4
        hits=recursive_hits(d,va,targetset,ib,secs,4,1200)
        for p,dst,depth,path in hits[:20]:
            anyhit=True
            w(f"RECURSIVE depth={depth} gsSlot=0x{slot:X} method=0x{va:08X} -> slot110Fn=0x{dst:08X} path="+" -> ".join(f"0x{x:08X}" for x in path))
    if not anyhit:w("none")
    w("")

    w("===== FOCUS METHOD RTTI / VTABLE OWNERS =====")
    for name,va in FOCUS.items():
        w(f"[{name}] VA=0x{va:08X}")
        refs=candidate_vtables_for_method(d,va,ib,secs)
        w(f"RTTI_vtable_hits={len(refs)}")
        for vf,vva,idx,slot,rtti,hit in refs:
            w(f" vtableFile=0x{vf:08X} vtableVA=0x{vva:08X} RTTI={rtti!r} index={idx} slot=0x{slot:X} methodRefFile=0x{hit:08X}")
        callers=direct_callers(d,va,ib,secs)
        w(f"DirectCallers={len(callers)}")
        for c in callers[:100]:
            pr=guess_prologue(d,c)
            w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X} callerPrologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
            lines.extend(dump(d,c-64,c+112))
        st=v2f(va,ib,secs)
        if st is not None:
            en=next_prologue(d,st,0x1400)
            lines.extend(dump(d,st,en))
        w("")

    w("===== SLOT110 FUNCTIONS THAT ARE GS_GARAGE VTABLE METHODS =====")
    gsmethodset={va:(idx,slot) for idx,slot,va in gs_methods}
    common=sorted(set(slotfuncs)&set(gsmethodset))
    if common:
        for va in common:
            idx,slot=gsmethodset[va]
            w(f"VA=0x{va:08X} gsSlot=0x{slot:X} index={idx}")
    else:
        w("none")
    w("")

    w("===== SLOT110 FUNCTIONS CALLERS THAT ARE GS_GARAGE METHODS =====")
    for sf in slotfuncs:
        for c in direct_callers(d,sf,ib,secs):
            pr=guess_prologue(d,c)
            pva=f2v(pr,ib,secs) if pr is not None else None
            if pva in gsmethodset:
                idx,slot=gsmethodset[pva]
                w(f"slot110Fn=0x{sf:08X} calledFromGsMethod=0x{pva:08X} gsSlot=0x{slot:X} callFile=0x{c:08X}")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*90)
    print(" PHASE 61 GARAGE SLOT+0x110 OWNER MAP READY")
    print("="*90)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
