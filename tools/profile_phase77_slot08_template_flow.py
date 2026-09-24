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

SLOT08=0x0096F380
TEMPLATE_BUILD=0x0096F3B0
READY_UI=0x00974480
BUILD_CALLBACK=0x00973C90
TARGETS=[0x34,0x3C,0x44,0x4C,0x54,0x5C,0x64]
UI_FIELDS=[0x88,0x8C,0x90,0x94,0x98,0x9C,0xA0,0xA4,0xA8,0xAC]
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
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
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

def next_prologue(d,start,limit=0x7000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def detect_this_reg(d,fs,fe,mode):
    lim=min(fe,fs+0x90)
    if mode=="ecx":
        pats=[(b"\x8B\xD9","ebx"),(b"\x8B\xF1","esi"),(b"\x8B\xF9","edi"),(b"\x8B\xC1","eax")]
        best=None
        for pat,r in pats:
            p=d.find(pat,fs,lim)
            if p>=0 and (best is None or p<best[0]):best=(p,r)
        return best[1] if best else "ecx"
    if mode=="arg1":
        for p in range(fs,lim-2):
            if d[p]==0x8B:
                mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
                if mod==1 and rm==5 and d[p+2]==0x08 and dst not in (4,5):
                    return REGS[dst]
    return None

def classify(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    return "MEM"

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8(d,p+2),3
    if mod==2 and p+6<=fe:return rm,i32(d,p+2),6
    return None

def analyze(d,va,mode,origin,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,0x7000)
    obj=detect_this_reg(d,fs,fe,mode)
    if obj is None:return (fs,fe,None,[],[],[])

    taint={obj:origin}
    hits=[]
    calls=[]
    derived=[]
    p=fs
    while p<fe:
        op=d[p]

        if op==0x8B and p+2<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint: taint[t]=taint[s]
                elif t in taint: taint.pop(t,None)
                p+=2;continue
            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in TARGETS or eff in UI_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp,op,mr))
                    taint.pop(REGS[dst],None)
                p+=ln;continue

        if op==0x8D and p+2<=fe:
            mr=d[p+1];dst=(mr>>3)&7
            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    taint[t]=taint[base]+disp
                    derived.append((p,t,taint[t],base,disp))
                    if taint[t] in TARGETS:
                        hits.append((p,taint[t],"ADDRESS",base,disp,op,mr))
                else:
                    taint.pop(t,None)
                p+=ln;continue

        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=fe:
            mr=d[p+1];dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in TARGETS or eff in UI_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp,op,mr))
                p+=ln;continue

        if op in (0x83,0x81) and p+3<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;ext=(mr>>3)&7
            r=REGS[rm]
            if mod==3 and r in taint and ext in (0,5):
                if op==0x83:
                    imm=i8(d,p+2);ln=3
                else:
                    if p+6>fe:break
                    imm=i32(d,p+2);ln=6
                if ext==5:imm=-imm
                taint[r]+=imm
                derived.append((p,r,taint[r],r,imm))
                p+=ln;continue

        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                lo=max(fs,p-36)
                candidates=[]
                for r,off in list(taint.items()):
                    rid=REGS.index(r)
                    pat1=bytes([0x8B,0xC8|rid])
                    pat2=bytes([0x89,0xC1|(rid<<3)])
                    q=max(d.rfind(pat1,lo,p),d.rfind(pat2,lo,p))
                    if q>=0:candidates.append((q,"ecx",off,r))
                    q2=d.rfind(bytes([0x50+rid]),lo,p)
                    if q2>=0:candidates.append((q2,"arg1",off,r))
                if candidates:
                    candidates.sort(reverse=True)
                    prep,nmode,noff,nreg=candidates[0]
                    calls.append((p,dst,nmode,noff,nreg,prep))
            p+=5;continue

        p+=1
    return fs,fe,obj,hits,derived,calls

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
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
    seeds={
        "slot08_init":SLOT08,
        "template_build":TEMPLATE_BUILD,
        "ready_ui":READY_UI,
    }
    q=deque((name,va,"ecx",0,0,[f"{name}:0x{va:08X}+0x0"]) for name,va in seeds.items())
    seen={}
    edges=[]
    hits=[]
    deriv=[]
    MAX_DEPTH=7
    MAX_NODES=1800

    while q and len(seen)<MAX_NODES:
        rootname,va,mode,origin,depth,path=q.popleft()
        key=(va,mode,origin)
        if key in seen and seen[key]<=depth:continue
        seen[key]=depth
        a=analyze(d,va,mode,origin,ib,secs)
        if not a:continue
        fs,fe,obj,fh,dr,calls=a
        for row in fh:
            p,eff,kind,base,disp,op,mr=row
            hits.append(dict(root=rootname,va=va,mode=mode,origin=origin,depth=depth,path=path,
                             file=p,eff=eff,kind=kind,obj=obj,base=base,disp=disp,op=op,mr=mr))
        for row in dr:
            deriv.append((rootname,va,depth,*row,path))
        if depth>=MAX_DEPTH:continue
        for cp,dst,nmode,noff,nreg,prep in calls:
            if -0x200<=noff<=0x300:
                edges.append((rootname,va,mode,origin,obj,cp,dst,nmode,noff,nreg,prep))
                q.append((rootname,dst,nmode,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}({nmode})"]))

    score={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":20,"CALL_MEM":10,"MEM":5}
    callback_hits=[x for x in hits if x["eff"] in TARGETS]
    ui_hits=[x for x in hits if x["eff"] in UI_FIELDS]
    strong44=[x for x in callback_hits if x["eff"]==0x44 and x["kind"] in ("WRITE","READ_WRITE","ADDRESS")]
    ranked44=sorted([x for x in callback_hits if x["eff"]==0x44],
                    key=lambda x:(-score.get(x["kind"],0),x["depth"],x["file"]))

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE77_SLOT08_TEMPLATE_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE77-SLOT08-TEMPLATE-FLOW.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*114)
    w(" ReXtreme Phase 77 - GarageBottomBarWidget slot+0x08/template initialization flow")
    w("="*114)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w(f"slot08_init=0x{SLOT08:08X}")
    w(f"template_build=0x{TEMPLATE_BUILD:08X}")
    w(f"ready_ui=0x{READY_UI:08X}")
    w("callback_fields="+",".join(f"+0x{x:X}" for x in TARGETS))
    w("ui_fields="+",".join(f"+0x{x:X}" for x in UI_FIELDS))
    w("")

    for name,va in seeds.items():
        fs=v2f(va,ib,secs);fe=next_prologue(d,fs,0x7000)
        w(f"===== SEED {name} =====")
        w(f"VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X}")
        lines.extend(dump(d,fs,fe))
        w("")

    w("===== THIS/SUBOBJECT FLOW EDGES =====")
    w(f"Count={len(edges)}")
    for e in edges[:2600]:
        root,src,mode,origin,obj,cp,dst,nmode,noff,nreg,prep=e
        w(f"root={root} src=0x{src:08X}+0x{origin:X} mode={mode} objreg={obj} prep=0x{prep:08X} call=0x{cp:08X} -> dst=0x{dst:08X}+0x{noff:X} next={nmode} via={nreg}")
    w("")

    w("===== CALLBACK-FIELD HITS =====")
    w(f"Count={len(callback_hits)}")
    for x in sorted(callback_hits,key=lambda x:(x["eff"],-score.get(x["kind"],0),x["depth"],x["file"])):
        w(f"field=+0x{x['eff']:X} kind={x['kind']} root={x['root']} depth={x['depth']} fn=0x{x['va']:08X} origin=0x{x['origin']:X} file=0x{x['file']:08X}")
        w(" path="+" -> ".join(x["path"]))
        if x["eff"]==0x44 or x["kind"] in ("WRITE","READ_WRITE","ADDRESS"):
            lines.extend(dump(d,x["file"]-64,x["file"]+128))
    w("")

    w("===== UI-FIELD HITS =====")
    w(f"Count={len(ui_hits)}")
    for x in sorted(ui_hits,key=lambda x:(x["eff"],x["depth"],x["file"]))[:1200]:
        w(f"field=+0x{x['eff']:X} kind={x['kind']} root={x['root']} depth={x['depth']} fn=0x{x['va']:08X} file=0x{x['file']:08X}")
    w("")

    w("===== +0x44 RANKED =====")
    w(f"Count={len(ranked44)}")
    for x in ranked44:
        w(f"{x['kind']} root={x['root']} depth={x['depth']} fn=0x{x['va']:08X} file=0x{x['file']:08X} origin=0x{x['origin']:X}")
        w(" path="+" -> ".join(x["path"]))
    w("")

    w("===== STRONG +0x44 INITIALIZATION CANDIDATES =====")
    w(f"Count={len(strong44)}")
    for x in strong44:
        w(f"{x['kind']} fn=0x{x['va']:08X} file=0x{x['file']:08X} root={x['root']} depth={x['depth']}")
        w(" path="+" -> ".join(x["path"]))
        lines.extend(dump(d,x["file"]-96,x["file"]+160))
    w("")

    objout={
        "phase":"77-slot08-template-flow",
        "ams_sha256":cursha,
        "nodes":len(seen),
        "edges":len(edges),
        "callback_field_hits":len(callback_hits),
        "ui_field_hits":len(ui_hits),
        "field44_hits":len(ranked44),
        "strong_field44_candidates":[
            {
                "kind":x["kind"],
                "function_va":f"0x{x['va']:08X}",
                "file":f"0x{x['file']:08X}",
                "root":x["root"],
                "depth":x["depth"],
                "path":x["path"]
            } for x in strong44[:100]
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(objout,indent=2),encoding="utf-8")

    print("="*114)
    print(" PHASE 77 SLOT08/TEMPLATE FLOW READY")
    print("="*114)
    print("Nodes:",len(seen))
    print("Edges:",len(edges))
    print("Callback-field hits:",len(callback_hits))
    print("UI-field hits:",len(ui_hits))
    print("+0x44 hits:",len(ranked44))
    print("Strong +0x44 candidates:",len(strong44))
    if strong44:
        x=strong44[0]
        print("TOP:",x["kind"],hex(x["va"]),hex(x["file"]),"root",x["root"],"depth",x["depth"])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
