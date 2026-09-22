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
GBBW_CTOR=0x0096EB10
GBBW_DTOR=0x0096EDF0
BUILD_CALLBACK=0x00973C90
TARGET_EFFECTIVE=0x44
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
            vs=u32(d,o+8),va=u32(d,o+12),rs=u32(d,o+16),raw=u32(d,o+20),ch=u32(d,o+36)
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

def next_prologue(d,start,limit=0x6000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

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

def decode_disp(d,p,fe):
    if p+2>=fe:return None
    mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7
    if rm==4:return None
    if mod==0:return (rm,0,2)
    if mod==1 and p+3<=fe:return (rm,i8(d,p+2),3)
    if mod==2 and p+6<=fe:return (rm,i32(d,p+2),6)
    return None

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def first_object_reg(d,fs,fe,mode):
    lim=min(fe,fs+0x90)
    if mode=="ecx":
        # Prefer the first persistent register assigned from ECX.
        for p in range(fs,lim-1):
            if d[p]==0x8B:
                mr=d[p+1]; mod=(mr>>6)&3; src=mr&7; dst=(mr>>3)&7
                if mod==3 and src==1 and dst not in (4,5):
                    return REGS[dst]
        return "ecx"
    if mode=="arg1":
        # mov reg,[ebp+8]
        for p in range(fs,lim-2):
            if d[p]==0x8B:
                mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; dst=(mr>>3)&7
                if mod==1 and rm==5 and d[p+2]==0x08 and dst not in (4,5):
                    return REGS[dst]
        return None
    return None

def analyze_function(d,va,mode,origin_off,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,0x6000)
    obj=first_object_reg(d,fs,fe,mode)
    if obj is None:return (fs,fe,None,[],[],[])

    # Taint: register -> effective offset relative to original GBBW base.
    taint={obj:origin_off}
    memhits=[]
    derived=[]
    calls=[]

    p=fs
    while p<fe:
        op=d[p]

        # mov reg,reg
        if op==0x8B and p+2<=fe:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm]; t=REGS[dst]
                if s in taint: taint[t]=taint[s]
                elif t in taint: taint.pop(t,None)
                p+=2; continue

            dec=decode_disp(d,p,fe)
            if dec:
                rm,disp,ln=dec
                base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    memhits.append((p,eff,classify_mem(op,mr),base,disp,op,mr))
                    # mov reg,[tainted+disp] loads VALUE, not pointer-to-member. kill pointer taint.
                    taint.pop(REGS[dst],None)
                p+=ln; continue

        # lea reg,[tainted+disp] => derived pointer
        if op==0x8D and p+2<=fe:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; dst=(mr>>3)&7
            dec=decode_disp(d,p,fe)
            if dec:
                rm,disp,ln=dec; base=REGS[rm]; t=REGS[dst]
                if base in taint:
                    taint[t]=taint[base]+disp
                    derived.append((p,t,taint[t],base,disp))
                else:
                    taint.pop(t,None)
                p+=ln; continue

        # mov [tainted+disp],reg / cmp / arithmetic / call [mem] etc.
        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=fe:
            mr=d[p+1]; dec=decode_disp(d,p,fe)
            if dec:
                rm,disp,ln=dec; base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    memhits.append((p,eff,classify_mem(op,mr),base,disp,op,mr))
                p+=ln; continue

        # add/sub tainted reg, immediate (83 /0 or /5, 81 /0 or /5)
        if op in (0x83,0x81) and p+3<=fe:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; ext=(mr>>3)&7
            r=REGS[rm]
            if mod==3 and r in taint and ext in (0,5):
                if op==0x83:
                    imm=i8(d,p+2); ln=3
                else:
                    if p+6>fe: break
                    imm=i32(d,p+2); ln=6
                if ext==5: imm=-imm
                taint[r]+=imm
                derived.append((p,r,taint[r],r,imm))
                p+=ln; continue

        # direct call. Look backwards for ECX loaded from a tainted register or a tainted register pushed.
        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                lo=max(fs,p-32)
                candidates=[]
                # mov ecx,reg / mov ecx,[?] not followed here
                for r,off in list(taint.items()):
                    rid=REGS.index(r)
                    pat1=bytes([0x8B,0xC8|rid])   # mov ecx,r
                    pat2=bytes([0x89,0xC1|(rid<<3)]) # mov ecx,r
                    q=max(d.rfind(pat1,lo,p),d.rfind(pat2,lo,p))
                    if q>=0:candidates.append((q,"ecx",off,r))
                    if rid<=7:
                        q2=d.rfind(bytes([0x50+rid]),lo,p)
                        if q2>=0:candidates.append((q2,"arg1",off,r))
                if candidates:
                    candidates.sort(reverse=True)
                    q0,nmode,noff,nreg=candidates[0]
                    calls.append((p,dst,nmode,noff,nreg,q0))
            p+=5; continue

        p+=1

    return fs,fe,obj,memhits,derived,calls

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for n,o,e in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    q=deque()
    for name,va in SEEDS.items():
        q.append((name,va,"ecx",0,0,[f"{name}:0x{va:08X}+0x0"]))
    seen={}
    edges=[]
    hits=[]
    derivations=[]

    MAX_DEPTH=7
    MAX_NODES=1800
    while q and len(seen)<MAX_NODES:
        rootname,va,mode,origin,depth,path=q.popleft()
        key=(va,mode,origin)
        if key in seen and seen[key]<=depth:continue
        seen[key]=depth
        a=analyze_function(d,va,mode,origin,ib,secs)
        if not a:continue
        fs,fe,obj,memhits,derived,calls=a
        for row in memhits:
            p,eff,kind,base,disp,op,mr=row
            if eff==TARGET_EFFECTIVE:
                hits.append(dict(root=rootname,va=va,mode=mode,origin=origin,depth=depth,
                    path=path,file=p,kind=kind,objreg=obj,base=base,disp=disp,op=op,modrm=mr))
        for row in derived:
            p,r,eff,base,disp=row
            if -0x200<=eff<=0x300:
                derivations.append((rootname,va,depth,p,r,eff,base,disp,path))
        if depth>=MAX_DEPTH:continue
        for cp,dst,nmode,noff,nreg,prep in calls:
            if -0x200<=noff<=0x300:
                edges.append((rootname,va,mode,origin,obj,cp,dst,nmode,noff,nreg,prep))
                q.append((rootname,dst,nmode,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}({nmode})"]))

    scoremap={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":25,"CALL_MEM":15,"MEM":5}
    ranked=sorted(hits,key=lambda x:(-scoremap.get(x["kind"],0),x["depth"],x["file"]))
    strong=[x for x in ranked if x["kind"] in ("WRITE","READ_WRITE","ADDRESS")]

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE73_GBBW_SUBOBJECT_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE73-GBBW-SUBOBJECT-FLOW.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*112)
    w(" ReXtreme Phase 73 - GBBW derived/subobject pointer flow to effective +0x44")
    w("="*112)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Phase72 found no direct-this setter. This phase tracks derived pointers such as this+0x34,")
    w("then follows helpers using that subobject pointer and sums effective offsets back to GBBW base.")
    w("")

    w("===== SUBOBJECT FLOW EDGES =====")
    w(f"Count={len(edges)}")
    for e in edges[:2600]:
        rootname,src,mode,origin,obj,cp,dst,nmode,noff,nreg,prep=e
        w(f"root={rootname} src=0x{src:08X}+0x{origin:X} mode={mode} objreg={obj} prepFile=0x{prep:08X} callFile=0x{cp:08X} -> dst=0x{dst:08X}+0x{noff:X} nextMode={nmode} viaReg={nreg}")
    w("")

    w("===== DERIVED POINTERS NEAR GBBW SIGNAL AREA =====")
    w(f"Count={len(derivations)}")
    for rootname,va,dep,p,r,eff,base,disp,path in derivations[:2600]:
        if 0x20<=eff<=0x80:
            w(f"root={rootname} depth={dep} fn=0x{va:08X} file=0x{p:08X} {r}=GBBW+0x{eff:X} from={base} delta={disp:+#x}")
    w("")

    w("===== EFFECTIVE GBBW +0x44 HITS =====")
    w(f"Count={len(ranked)}")
    for x in ranked:
        w(f"kind={x['kind']} root={x['root']} depth={x['depth']} fn=0x{x['va']:08X} origin=0x{x['origin']:X} mode={x['mode']} objreg={x['objreg']} baseReg={x['base']} localDisp={x['disp']:+#x} file=0x{x['file']:08X} VA=0x{f2v(x['file'],ib,secs):08X}")
        w(" path="+" -> ".join(x["path"]))
        lines.extend(dump(d,x["file"]-72,x["file"]+144))
    w("")

    w("===== STRONG EFFECTIVE +0x44 SETTER CANDIDATES =====")
    w(f"Count={len(strong)}")
    for x in strong:
        w(f"{x['kind']} fn=0x{x['va']:08X} file=0x{x['file']:08X} origin=0x{x['origin']:X} localDisp={x['disp']:+#x} depth={x['depth']} root={x['root']}")
        w(" path="+" -> ".join(x["path"]))
    w("")

    w("===== CONTROL CHECKS =====")
    w("Known direct constructor zero write:")
    cf=v2f(GBBW_CTOR,ib,secs)
    lines.extend(dump(d,cf+0x60,cf+0x90))
    w("Known callback read:")
    bf=v2f(BUILD_CALLBACK,ib,secs)
    lines.extend(dump(d,bf+0x20,bf+0x50))
    w("")

    obj={
        "phase":"73-gbbw-subobject-flow",
        "ams_sha256":cursha,
        "nodes":len(seen),
        "edges":len(edges),
        "derived_pointers":len(derivations),
        "effective_field44_hits":len(ranked),
        "strong_candidates":[
            {
                "kind":x["kind"],"function_va":f"0x{x['va']:08X}",
                "file":f"0x{x['file']:08X}","origin":f"0x{x['origin']:X}",
                "local_disp":x["disp"],"depth":x["depth"],"root":x["root"],"path":x["path"]
            } for x in strong[:120]
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*112)
    print(" PHASE 73 GBBW SUBOBJECT FLOW READY")
    print("="*112)
    print("Nodes:",len(seen))
    print("Edges:",len(edges))
    print("Derived pointers:",len(derivations))
    print("Effective +0x44 hits:",len(ranked))
    print("Strong setter candidates:",len(strong))
    if strong:
        x=strong[0]
        print("TOP:",x["kind"],hex(x["va"]),hex(x["file"]),"origin",hex(x["origin"]),"disp",hex(x["disp"]))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
