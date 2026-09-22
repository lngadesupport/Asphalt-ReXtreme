#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict, deque

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

# Stable chain guards.
P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

CALLBACKS = {
    "build_button_cb": 0x00973C90,
    "sibling_cb_00973D20": 0x00973D20,
    "sibling_cb_00973E40": 0x00973E40,
    "sibling_cb_0097B7E0": 0x0097B7E0,
    "sibling_cb_00973ED0": 0x00973ED0,
}

KNOWN = {
    "GS_Garage_build_slot110": 0x00A87960,
    "CraftCar_unique_caller": 0x0099FF50,
    "CraftCar": 0x009A4BA0,
    "GlobalIsOnline": 0x00FAD9D0,
    "GarageBottomBarWidget_slot04": 0x00972B90,
    "GarageBottomBarWidget_ready": 0x00974480,
    "GarageBottomBarWidget_slot10": 0x009747F0,
    "GarageBottomBarWidget_slot14": 0x009740D0,
    "GarageBottomBarWidget_slot18": 0x00975040,
    "GarageBottomBarWidget_slot1C": 0x009743C0,
    "GarageBottomBarWidget_slot20": 0x00974A40,
    "GarageBottomBarWidget_slot24": 0x00974ED0,
    "dispatch_00970DD0":0x00970DD0,
    "dispatch_009714C0":0x009714C0,
    "dispatch_00971960":0x00971960,
    "dispatch_00972170":0x00972170,
    "dispatch_00972620":0x00972620,
    "dispatch_009728D0":0x009728D0,
}

BUILD_BUTTON_STRING=0x0153F0DC
GS_GARAGE_VTABLE=0x0186A9CC

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8(b,o):
    x=b[o]; return x-256 if x>=128 else x
def i32(b,o): return struct.unpack_from("<i",b,o)[0]
def sha(b): return hashlib.sha256(b).hexdigest()

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
    return bool(s and (s["ch"]&0x20000000))

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    return f is not None and is_exec_file(f,secs)

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p); p+=1

def prologue(d,near,back=0x5000):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def next_prologue(d,start,limit=0x3000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def direct_calls(d,fs,fe,ib,secs):
    out=[]; p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,dst,v2f(dst,ib,secs)))
            p+=5; continue
        if d[p]==0xE9:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,dst,v2f(dst,ib,secs)))
            p+=5; continue
        p+=1
    return out

def virtual_calls(d,fs,fe):
    out=[]; p=fs
    while p+2<=fe:
        if d[p]==0xFF:
            mr=d[p+1]; reg=(mr>>3)&7; mod=(mr>>6)&3; rm=mr&7
            if reg==2 and rm!=4:
                if mod==1 and p+3<=fe:
                    disp=i8(d,p+2)
                    out.append((p,disp,3,mr))
                    p+=3; continue
                if mod==2 and p+6<=fe:
                    disp=u32(d,p+2)
                    out.append((p,disp,6,mr))
                    p+=6; continue
                if mod==0:
                    out.append((p,0,2,mr))
        p+=1
    return out

def branches(d,fs,fe,ib,secs):
    out=[];p=fs
    while p+6<=fe:
        sva=f2v(p,ib,secs)
        if sva is None: p+=1; continue
        op=d[p]
        if 0x70<=op<=0x7F:
            dst=(sva+2+i8(d,p+1))&0xffffffff
            out.append((p,f"{op:02X}",dst,v2f(dst,ib,secs)))
            p+=2;continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            dst=(sva+6+i32(d,p+2))&0xffffffff
            out.append((p,f"0F{d[p+1]:02X}",dst,v2f(dst,ib,secs)))
            p+=6;continue
        p+=1
    return out

def direct_call_index(d,ib,secs):
    callers=defaultdict(list); outgoing=defaultdict(list)
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        cur=None
        while p<=end:
            if d[p:p+3]==b"\x55\x8B\xEC": cur=f2v(p,ib,secs)
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None:
                    dst=(sva+5+i32(d,p+1))&0xffffffff
                    if is_exec_va(dst,ib,secs):
                        fn=cur
                        callers[dst].append((p,fn))
                        if fn is not None: outgoing[fn].append((p,dst))
                p+=5;continue
            p+=1
    return callers,outgoing

def recursive_forward(seeds,outgoing,max_depth=5,max_nodes=2500):
    q=deque((name,va,0,[va]) for name,va in seeds.items())
    seen={}
    hits=[]
    while q and len(seen)<max_nodes:
        name,va,dep,path=q.popleft()
        key=(name,va)
        if key in seen and seen[key]<=dep: continue
        seen[key]=dep
        for p,dst in outgoing.get(va,[]):
            tag=next((k for k,v in KNOWN.items() if v==dst),None)
            if tag:
                hits.append((name,dep+1,p,dst,tag,path+[dst]))
            if dep<max_depth and dst not in path:
                q.append((name,dst,dep+1,path+[dst]))
    return hits

def ascii_z(d,off,limit=300):
    if off is None or not(0<=off<len(d)):return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("ascii","replace")
    except:return ""
    return s if s and sum(0x20<=ord(c)<0x7f for c in s)>=max(1,int(len(s)*.9)) else ""

def rtti_name(d,vtable_va,ib,secs):
    vf=v2f(vtable_va,ib,secs)
    if vf is None or vf<4:return None
    col=v2f(u32(d,vf-4),ib,secs)
    if col is None or col+20>len(d):return None
    td=v2f(u32(d,col+12),ib,secs)
    return ascii_z(d,td+8,300) if td is not None else None

def scan_immediate_refs(d,va,secs):
    pat=struct.pack("<I",va)
    return [p for p in find_all(d,pat) if is_exec_file(p,secs)]

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
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        cur=d[off:off+len(exp)]
        if cur!=exp: raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")
    cursha=sha(d)
    if cursha!=STABLE_SHA: raise SystemExit(f"Unexpected AMS SHA256: {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    callers,outgoing=direct_call_index(d,ib,secs)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE67_BUILD_BUTTON_CALLBACK_ROOT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE67-BUILD-BUTTON-CALLBACK-ROOT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*100)
    w(" ReXtreme Phase 67 - dedicated build_button callback root")
    w("="*100)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")

    w("===== CALLBACK REGISTRATION IDENTITY =====")
    w(f"build_button_string=0x{BUILD_BUTTON_STRING:08X}")
    w(f"build_button_callback=0x{CALLBACKS['build_button_cb']:08X}")
    refs=scan_immediate_refs(d,CALLBACKS["build_button_cb"],secs)
    w(f"CallbackImmediateExecutableRefs={len(refs)}")
    for p in refs:
        fs=prologue(d,p); fva=f2v(fs,ib,secs) if fs is not None else None
        w(f" refFile=0x{p:08X} refVA=0x{f2v(p,ib,secs):08X} containingFn={('0x%08X'%fva) if fva else 'N/A'}")
        lines.extend(dump(d,p-96,p+160))
    w("")

    w("===== CALLBACK BODIES =====")
    callback_meta={}
    for name,va in CALLBACKS.items():
        fs=v2f(va,ib,secs)
        if fs is None:
            w(f"[{name}] VA=0x{va:08X} file=N/A");continue
        fe=next_prologue(d,fs,0x1800)
        callback_meta[name]={"va":va,"file":fs,"end":fe}
        w(f"[{name}] VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X} len=0x{fe-fs:X}")
        lines.extend(dump(d,fs,fe))
        w("-- direct calls/jmps --")
        for p,dst,dfo in direct_calls(d,fs,fe,ib,secs):
            tag=next((k for k,v in KNOWN.items() if v==dst),"")
            w(f" EDGE file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'} {tag}")
        w("-- virtual calls --")
        for p,slot,n,mr in virtual_calls(d,fs,fe):
            w(f" VCALL file=0x{p:08X} slot={('0x%X'%slot) if slot>=0 else str(slot)} modrm=0x{mr:02X}")
        w("-- branches --")
        for p,op,dst,dfo in branches(d,fs,fe,ib,secs):
            w(f" JCC {op} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'}")
        cs=callers.get(va,[])
        w(f"DirectRelativeCallers={len(cs)}")
        for cp,cfn in cs[:80]:
            w(f" callerCallFile=0x{cp:08X} callerFn={('0x%08X'%cfn) if cfn else 'N/A'}")
        w("")

    w("===== CALLBACK FORWARD GRAPH TO KNOWN GARAGE/BACKEND TARGETS =====")
    hits=recursive_forward(CALLBACKS,outgoing,6,5000)
    w(f"KnownTargetHits={len(hits)}")
    for name,dep,p,dst,tag,path in hits:
        w(f"callback={name} depth={dep} callFile=0x{p:08X} -> {tag} 0x{dst:08X}")
        w(" path="+" -> ".join(f"0x{x:08X}" for x in path))
    w("")

    w("===== COMPARISON: BUILD CALLBACK VS SIBLINGS =====")
    bva=CALLBACKS["build_button_cb"]; bfs=v2f(bva,ib,secs); bfe=next_prologue(d,bfs,0x1800)
    bdirect={dst for _,dst,_ in direct_calls(d,bfs,bfe,ib,secs)}
    bslots={slot for _,slot,_,_ in virtual_calls(d,bfs,bfe)}
    w("build_direct="+",".join(f"0x{x:08X}" for x in sorted(bdirect)))
    w("build_vslots="+",".join(f"0x{x:X}" for x in sorted(x for x in bslots if x>=0)))
    for name,va in CALLBACKS.items():
        if name=="build_button_cb":continue
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x1800)
        ds={dst for _,dst,_ in direct_calls(d,fs,fe,ib,secs)}
        vs={slot for _,slot,_,_ in virtual_calls(d,fs,fe)}
        w(f"[{name}] unique_direct="+",".join(f"0x{x:08X}" for x in sorted(ds-bdirect)))
        w(f"[{name}] missing_from_sibling="+",".join(f"0x{x:08X}" for x in sorted(bdirect-ds)))
        w(f"[{name}] unique_vslots="+",".join(f"0x{x:X}" for x in sorted(x for x in (vs-bslots) if x>=0)))
        w(f"[{name}] build_only_vslots="+",".join(f"0x{x:X}" for x in sorted(x for x in (bslots-vs) if x>=0)))
    w("")

    w("===== BUILD CALLBACK IMMEDIATE REFERENCES TO GARAGE VTABLE/TARGETS =====")
    for label,va in [("GS_Garage_vtable",GS_GARAGE_VTABLE)]+list(KNOWN.items()):
        refs=scan_immediate_refs(d,va,secs)
        near=[]
        for p in refs:
            fs=prologue(d,p); fva=f2v(fs,ib,secs) if fs is not None else None
            if fva==bva: near.append(p)
        if near:
            w(f"{label}=0x{va:08X} refs_in_build_callback="+",".join(f"0x{x:08X}" for x in near))
    w("")

    obj={
        "phase":"67-build-button-callback-root",
        "ams_sha256":cursha,
        "build_button_callback":"0x00973C90",
        "callback_registration_refs":[f"0x{x:08X}" for x in refs],
        "known_target_hits":len(hits),
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*100)
    print(" PHASE 67 BUILD_BUTTON CALLBACK ROOT READY")
    print("="*100)
    print("Build callback: 0x00973C90")
    print("Known backend/garage hits:",len(hits))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
