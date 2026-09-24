#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path
from collections import deque

SEEDS = {
    "dispatch_00972620":0x00972620,
    "dispatch_00972170":0x00972170,
    "dispatch_00970DD0":0x00970DD0,
    "dispatch_00971960":0x00971960,
    "dispatch_00970840":0x00970840,
    "helper_00964D90":0x00964D90,
    "helper_00964C40":0x00964C40,
}
KNOWN = {
    "build_request_handler":0x00A87960,
    "craftcar_unique_caller":0x0099FF50,
    "craftcar_start":0x009A4BA0,
    "global_isonline":0x00FAD9D0,
}
BUILD_REQ=0x00A87960

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8(b,o):
    x=b[o]
    return x-256 if x>=128 else x
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

def ascii_z(d,off,limit=256):
    if off is None or off<0 or off>=len(d): return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("ascii","replace")
    except:return ""
    if not s:return ""
    printable=sum(0x20<=ord(c)<0x7f for c in s)
    return s if printable >= max(1,int(len(s)*0.9)) else ""

def rtti_name_for_vtable_file(d,vf,ib,secs):
    if vf<4:return None,{}
    col_va=u32(d,vf-4)
    col_f=v2f(col_va,ib,secs)
    info={"vtable_file":vf,"vtable_va":f2v(vf,ib,secs),"col_va":col_va,"col_file":col_f}
    if col_f is None or col_f+20>len(d):return None,info
    sig,off,cd,td_va,chd_va=struct.unpack_from("<IIIII",d,col_f)
    info.update(sig=sig,offset=off,cdOffset=cd,type_desc_va=td_va,class_hierarchy_va=chd_va)
    td_f=v2f(td_va,ib,secs); info["type_desc_file"]=td_f
    name=ascii_z(d,td_f+8,300) if td_f is not None else None
    return name,info

def guess_func_start(d,off,back=0x1800):
    lo=max(0,off-back)
    # favor common MSVC prologue
    for p in range(off,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def func_bounds(d,va,ib,secs,limit=0x2000):
    fo=v2f(va,ib,secs)
    if fo is None:return None,None
    # if exact address isn't prologue, still use it as start (some thunks/leaf funcs)
    st=fo
    nxt=d.find(b"\x55\x8B\xEC",st+3,min(len(d),st+limit))
    if nxt<0:nxt=min(len(d),st+limit)
    return st,nxt

def decode_indirect_call(d,p,end):
    # Return textual operand form and slot displacement when obvious.
    # FF /2 with common modrm encodings:
    # 50 ib  -> call [eax+disp8], 51 [ecx+disp8], ... 52...
    # 90 id  -> call [eax+disp32], 91 [ecx+disp32], ...
    if p+1>=end or d[p]!=0xFF:return None
    modrm=d[p+1]
    reg=(modrm>>3)&7
    if reg!=2:return None
    mod=(modrm>>6)&3; rm=modrm&7
    regs=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]
    if mod==1 and p+2<end:
        disp=i8(d,p+2)
        return f"[{regs[rm]}{disp:+#x}]", disp & 0xffffffff, 3
    if mod==2 and p+5<end:
        disp=u32(d,p+2)
        return f"[{regs[rm]}+0x{disp:X}]", disp, 6
    if mod==0:
        if rm==5 and p+5<end:
            addr=u32(d,p+2)
            return f"[0x{addr:X}]", None, 6
        if rm!=4:
            return f"[{regs[rm]}]",0,2
    return f"[modrm=0x{modrm:02X}]",None,2

def scan_function(d,va,ib,secs):
    st,en=func_bounds(d,va,ib,secs)
    if st is None:return [],[],[]
    direct=[]; indirect=[]; branches=[]
    p=st
    while p<en-6:
        srcva=f2v(p,ib,secs)
        if srcva is None: p+=1; continue
        op=d[p]
        if op==0xE8:
            dst=(srcva+5+i32(d,p+1))&0xffffffff
            direct.append((p,dst,v2f(dst,ib,secs)))
            p+=5; continue
        if op==0xFF:
            dec=decode_indirect_call(d,p,en)
            if dec:
                operand,slot,n=dec
                indirect.append((p,operand,slot))
                p+=n; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            dst=(srcva+6+i32(d,p+2))&0xffffffff
            branches.append((p,f"0F{d[p+1]:02X}",dst))
            p+=6; continue
        if 0x70<=op<=0x7F:
            dst=(srcva+2+i8(d,p+1))&0xffffffff
            branches.append((p,f"{op:02X}",dst))
            p+=2; continue
        p+=1
    return direct,indirect,branches

def recursive_graph(d,seeds,ib,secs,max_depth=4,max_nodes=500):
    q=deque((name,va,0,[name]) for name,va in seeds.items())
    seen={}
    edges=[]
    while q and len(seen)<max_nodes:
        root,va,depth,path=q.popleft()
        if va in seen and seen[va]<=depth: continue
        seen[va]=depth
        direct,indirect,_=scan_function(d,va,ib,secs)
        for p,dst,dfo in direct:
            tag=next((k for k,v in KNOWN.items() if v==dst),None)
            edges.append((va,p,dst,depth,tag))
            if depth<max_depth and is_exec_va(dst,ib,secs):
                q.append((root,dst,depth+1,path+[f"0x{dst:08X}"]))
    return seen,edges

def candidate_vtable_starts(d,hit,ib,secs):
    # Search backward by dword up to 0x600 for a valid RTTI COL at table[-1].
    cands=[]
    lo=max(4,hit-0x600)
    for vf in range(hit,lo-1,-4):
        name,info=rtti_name_for_vtable_file(d,vf,ib,secs)
        if name and name.startswith(".?A"):
            idx=(hit-vf)//4
            # verify every dword between start and hit looks executable often enough
            vals=[]
            ok=0
            for p in range(vf,min(hit+4,vf+0x800),4):
                val=u32(d,p)
                vals.append(val)
                if is_exec_va(val,ib,secs):ok+=1
                else: break
            if hit>=vf and hit<vf+4*len(vals) and ok>=idx+1:
                cands.append((vf,idx,name,info))
    # dedupe by vf
    out=[]; seen=set()
    for x in cands:
        if x[0] not in seen:
            seen.add(x[0]); out.append(x)
    return out

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
        if cur!=exp:raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE59_VIRTUAL_DISPATCH_BRIDGE"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE59-VIRTUAL-DISPATCH-BRIDGE.txt"
    lines=[];w=lines.append

    w("="*86)
    w(" ReXtreme Phase 59 - UI command -> virtual build-request bridge")
    w("="*86)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    w("===== SEED DISPATCHER BODIES / VIRTUAL CALL SLOTS =====")
    all_slots={}
    for name,va in SEEDS.items():
        st,en=func_bounds(d,va,ib,secs)
        w(f"[{name}] VA=0x{va:08X} file={('0x%08X'%st) if st is not None else 'N/A'} end={('0x%08X'%en) if en is not None else 'N/A'}")
        if st is None: continue
        lines.extend(dump(d,st,en))
        direct,indirect,branches=scan_function(d,va,ib,secs)
        w("-- direct calls --")
        for p,dst,dfo in direct:
            tag=next((k for k,v in KNOWN.items() if v==dst),"")
            w(f" CALL file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'} {tag}")
        w("-- indirect virtual-like calls --")
        for p,operand,slot in indirect:
            w(f" CALL file=0x{p:08X} operand={operand} slot={('0x%X'%slot) if slot is not None else 'N/A'}")
            if slot is not None: all_slots.setdefault(slot,[]).append((name,p))
        w("")

    w("===== RECURSIVE DIRECT CALL GRAPH (depth<=4) =====")
    seen,edges=recursive_graph(d,SEEDS,ib,secs,4,800)
    w(f"Nodes={len(seen)} Edges={len(edges)}")
    for src,p,dst,depth,tag in edges:
        if tag or dst in SEEDS.values() or depth<=1:
            w(f"depth={depth} src=0x{src:08X} callFile=0x{p:08X} -> 0x{dst:08X} tag={tag or ''}")
    hits=[e for e in edges if e[4]]
    w("KnownTargetEdges="+str(len(hits)))
    for src,p,dst,depth,tag in hits:
        w(f" HIT depth={depth} src=0x{src:08X} callFile=0x{p:08X} -> {tag} 0x{dst:08X}")
    w("")

    w("===== BUILD-REQUEST HANDLER VTABLE OCCURRENCES =====")
    refs=find_all(d,struct.pack("<I",BUILD_REQ))
    w(f"AbsoluteDwordRefs={len(refs)}")
    slot_summary={}
    for hit in refs:
        s=sec_for_file(hit,secs)
        if s and (s["ch"]&0x20000000):
            continue
        w(f"hitFile=0x{hit:08X} hitVA={('0x%08X'%f2v(hit,ib,secs)) if f2v(hit,ib,secs) else 'N/A'} section={(s or {}).get('name','NOSEC')}")
        cands=candidate_vtable_starts(d,hit,ib,secs)
        if not cands:
            w(" no RTTI-backed vtable start found within 0x600")
        for vf,idx,rtti,info in cands[:12]:
            slot=idx*4
            slot_summary.setdefault(slot,[]).append((vf,rtti,hit))
            w(f" vtableFile=0x{vf:08X} vtableVA=0x{f2v(vf,ib,secs):08X} RTTI={rtti!r} index={idx} slot=0x{slot:X}")
        lines.extend(dump(d,hit-32,hit+48))
        w("")

    w("===== VIRTUAL SLOT INTERSECTION =====")
    w("UI-seen virtual slots:")
    for slot,uses in sorted(all_slots.items()):
        w(f" slot=0x{slot:X} uses="+", ".join(f"{n}@0x{p:08X}" for n,p in uses))
    w("Build-request vtable slots:")
    for slot,uses in sorted(slot_summary.items()):
        w(f" slot=0x{slot:X} tables="+", ".join(f"{rtti}@0x{vf:08X}" for vf,rtti,_ in uses[:10]))
    common=sorted(set(all_slots)&set(slot_summary))
    w("COMMON_SLOTS="+(",".join(f"0x{x:X}" for x in common) if common else "none"))
    w("")

    # Also map callers of the build request handler's unique direct CraftCar caller.
    w("===== BUILD REQUEST HANDLER BODY / VIRTUAL CALLS =====")
    st,en=func_bounds(d,BUILD_REQ,ib,secs)
    if st is not None:
        lines.extend(dump(d,st,en))
        direct,indirect,_=scan_function(d,BUILD_REQ,ib,secs)
        for p,dst,dfo in direct:
            tag=next((k for k,v in KNOWN.items() if v==dst),"")
            w(f" CALL file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'} {tag}")
        for p,operand,slot in indirect:
            w(f" VCALL file=0x{p:08X} operand={operand} slot={('0x%X'%slot) if slot is not None else 'N/A'}")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*86)
    print(" PHASE 59 VIRTUAL-DISPATCH BRIDGE MAP READY")
    print("="*86)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
