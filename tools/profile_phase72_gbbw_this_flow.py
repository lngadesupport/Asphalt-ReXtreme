#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import deque, defaultdict

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

SEEDS={
    "slot04_register_buttons":0x00972B90,
    "ready_to_build_ui":0x00974480,
    "click_router":0x009747F0,
    "slot14":0x009740D0,
    "slot18":0x00975040,
    "slot1C":0x009743C0,
    "slot20":0x00974A40,
    "slot24":0x00974ED0,
}
BUILD_CALLBACK=0x00973C90
BUILD_HANDLER=0x00A87960
CRAFTCALLER=0x0099FF50
CRAFTCAR=0x009A4BA0
FIELD=0x44

REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

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
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:
        raise RuntimeError("expected x86 PE32")
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

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:
            return bool(s["ch"]&0x20000000)
    return False

def next_prologue(d,start,limit=0x5000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def direct_calls(d,fs,fe,ib,secs):
    out=[]; p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,ib,secs):
                    out.append((p,dst))
            p+=5; continue
        p+=1
    return out

def mov_reg_ecx_patterns():
    # destination register <- ecx via 8B /r, mod=11, rm=ecx
    out={}
    for dst in range(8):
        mr=0xC0 | (dst<<3) | 1
        out[bytes([0x8B,mr])]=REGS[dst]
    # mov r/m32,reg32 where destination is ecx is not useful here.
    return out

MOV_FROM_ECX=mov_reg_ecx_patterns()

def arg1_load_patterns():
    # mov reg,[ebp+08]
    out={}
    for dst in range(8):
        mr=0x40 | (dst<<3) | 5
        out[bytes([0x8B,mr,0x08])]=REGS[dst]
    return out

ARG1_LOADS=arg1_load_patterns()

def choose_obj_reg(d,fs,fe,mode):
    lim=min(fe,fs+0x90)
    if mode=="ecx":
        best=None
        for pat,reg in MOV_FROM_ECX.items():
            p=d.find(pat,fs,lim)
            if p>=0 and reg not in ("esp","ebp") and (best is None or p<best[0]):
                best=(p,reg)
        return best[1] if best else "ecx"
    if mode=="arg1":
        best=None
        for pat,reg in ARG1_LOADS.items():
            p=d.find(pat,fs,lim)
            if p>=0 and reg not in ("esp","ebp") and (best is None or p<best[0]):
                best=(p,reg)
        return best[1] if best else None
    return None

def classify_mem(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    return "MEM"

def field_hits(d,fs,fe,objreg):
    if objreg is None:return []
    rid=REGS.index(objreg)
    out=[]; p=fs
    while p+3<=fe:
        op=d[p]
        if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
            p+=1; continue
        mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7
        if rm!=rid or rm==4:
            p+=1; continue
        disp=None; ln=0
        if mod==1:
            disp=d[p+2]; ln=3
        elif mod==2 and p+6<=fe:
            disp=u32(d,p+2); ln=6
        if disp==FIELD:
            out.append((p,classify_mem(op,mr),op,mr))
        p+=ln if ln else 1
    return out

def explicit_ecx_from_obj_before(d,callp,objreg,back=24):
    if objreg is None:return False,None
    rid=REGS.index(objreg)
    # mov ecx,objreg using 8B /r with dest=ecx, src=objreg
    pat1=bytes([0x8B,0xC8|rid])
    # mov ecx,objreg using 89 /r: dest=ecx (rm=1), src=objreg
    pat2=bytes([0x89,0xC1|(rid<<3)])
    lo=max(0,callp-back)
    p1=d.rfind(pat1,lo,callp)
    p2=d.rfind(pat2,lo,callp)
    p=max(p1,p2)
    return (p>=0,p if p>=0 else None)

def pushed_obj_before(d,callp,objreg,back=18):
    if objreg is None:return False,None
    rid=REGS.index(objreg)
    if rid>7:return False,None
    pat=bytes([0x50+rid])
    lo=max(0,callp-back)
    p=d.rfind(pat,lo,callp)
    return (p>=0,p if p>=0 else None)

def function_info(d,va,mode,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,0x5000)
    objreg=choose_obj_reg(d,fs,fe,mode)
    return fs,fe,objreg

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
        if d[off:off+len(exp)]!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:
        raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE72_GBBW_THIS_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE72-GBBW-THIS-FLOW.txt"
    summary=outdir/"SUMMARY.json"

    q=deque()
    for name,va in SEEDS.items():
        q.append((name,va,"ecx",0,[f"{name}:0x{va:08X}"]))
    seen={}
    edges=[]
    hits=[]

    MAX_DEPTH=6
    MAX_NODES=1200

    while q and len(seen)<MAX_NODES:
        rootname,va,mode,depth,path=q.popleft()
        key=(va,mode)
        if key in seen and seen[key]<=depth:continue
        seen[key]=depth
        info=function_info(d,va,mode,ib,secs)
        if not info:continue
        fs,fe,objreg=info
        for p,kind,op,mr in field_hits(d,fs,fe,objreg):
            hits.append(dict(root=rootname,va=va,mode=mode,depth=depth,path=path,
                             file=p,kind=kind,objreg=objreg,op=op,modrm=mr))
        if depth>=MAX_DEPTH:continue
        for cp,dst in direct_calls(d,fs,fe,ib,secs):
            ok_ecx,prep=explicit_ecx_from_obj_before(d,cp,objreg,28)
            if ok_ecx:
                edges.append((rootname,va,mode,objreg,cp,dst,"ecx",prep))
                q.append((rootname,dst,"ecx",depth+1,path+[f"0x{dst:08X}(ecx)"]))
                continue
            ok_arg,prepa=pushed_obj_before(d,cp,objreg,20)
            if ok_arg:
                edges.append((rootname,va,mode,objreg,cp,dst,"arg1",prepa))
                q.append((rootname,dst,"arg1",depth+1,path+[f"0x{dst:08X}(arg1)"]))

    # Rank writes/address before reads.
    scoremap={"WRITE":100,"READ_WRITE":90,"ADDRESS":80,"READ":20,"CALL_MEM":10,"MEM":5}
    ranked=sorted(hits,key=lambda x:(-scoremap.get(x["kind"],0),x["depth"],x["file"]))

    lines=[];w=lines.append
    w("="*108)
    w(" ReXtreme Phase 72 - GarageBottomBarWidget explicit-this flow to +0x44")
    w("="*108)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Confirmed delegate context at build registration: EDI=this in 0x00972B90.")
    w("This phase follows only explicit this propagation (mov ecx,obj / push obj) into direct callees.")
    w("")

    w("===== THIS-FLOW EDGES =====")
    w(f"Count={len(edges)}")
    for rootname,src,mode,objreg,cp,dst,nmode,prep in edges[:2000]:
        w(f"root={rootname} src=0x{src:08X} mode={mode} objreg={objreg} prepFile=0x{prep:08X} callFile=0x{cp:08X} -> dst=0x{dst:08X} nextMode={nmode}")
    w("")

    w("===== +0x44 HITS ON PROPAGATED OBJECT =====")
    w(f"Count={len(hits)}")
    for x in ranked:
        w(f"kind={x['kind']} root={x['root']} depth={x['depth']} fn=0x{x['va']:08X} mode={x['mode']} objreg={x['objreg']} file=0x{x['file']:08X} VA=0x{f2v(x['file'],ib,secs):08X}")
        w(" path="+" -> ".join(x["path"]))
        lines.extend(dump(d,x["file"]-64,x["file"]+128))
    w("")

    strong=[x for x in ranked if x["kind"] in ("WRITE","READ_WRITE","ADDRESS")]
    w("===== STRONG SETTER CANDIDATES =====")
    w(f"Count={len(strong)}")
    for x in strong:
        w(f"{x['kind']} fn=0x{x['va']:08X} file=0x{x['file']:08X} depth={x['depth']} root={x['root']} path="+" -> ".join(x["path"]))
    w("")

    # Focus build registration callsite and callback context proof.
    w("===== BUILD DELEGATE CONTEXT PROOF =====")
    lines.extend(dump(d,0x00572270,0x005722B0))
    w("Expected:")
    w("  8D 45 E8                  lea eax,[ebp-18h]")
    w("  C7 45 E8 90 3C 97 00      [ebp-18h]=0x00973C90")
    w("  89 7D EC                  [ebp-14h]=edi")
    w("  prologue 0x00571FB? has 8B F9 => edi=this")
    w("")

    obj={
        "phase":"72-gbbw-this-flow",
        "ams_sha256":cursha,
        "nodes":len(seen),
        "edges":len(edges),
        "field44_hits":len(hits),
        "strong_candidates":[
            {
                "kind":x["kind"],
                "function_va":f"0x{x['va']:08X}",
                "file":f"0x{x['file']:08X}",
                "depth":x["depth"],
                "root":x["root"],
                "path":x["path"]
            } for x in strong[:100]
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*108)
    print(" PHASE 72 GBBW THIS-FLOW READY")
    print("="*108)
    print("This-flow nodes:",len(seen))
    print("Edges:",len(edges))
    print("+0x44 hits:",len(hits))
    print("Strong setter candidates:",len(strong))
    if strong:
        x=strong[0]
        print("TOP:",x["kind"],hex(x["va"]),hex(x["file"]),"depth",x["depth"],"root",x["root"])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
