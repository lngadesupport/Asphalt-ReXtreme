#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict, deque

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

GBBW_VTABLE=0x01831854
RESEARCH_VTABLE=0x01837A5C
GS_GARAGE_VTABLE=0x0186A9CC
BUILD_CALLBACK=0x00973C90
REGISTER_HELPER=0x0096E4B0
INVOKE_HELPER=0x00936BE0
BUTTON_REGISTRY=0x00972B90
READY_UI=0x00974480
BUILD_HANDLER=0x00A87960
CRAFTCALLER=0x0099FF50
CRAFTCAR=0x009A4BA0

FIELDS=[0x34,0x3C,0x44,0x4C,0x54,0x5C,0x64]
TARGET_FIELD=0x44

KNOWN={
    "build_callback":BUILD_CALLBACK,
    "register_helper":REGISTER_HELPER,
    "invoke_helper":INVOKE_HELPER,
    "button_registry":BUTTON_REGISTRY,
    "ready_ui":READY_UI,
    "build_handler":BUILD_HANDLER,
    "craftcaller":CRAFTCALLER,
    "craftcar":CRAFTCAR,
}

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

def prologue(d,near,back=0x6000):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def next_prologue(d,start,limit=0x5000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def find_all(d,pat):
    out=[];p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p);p+=1

def vtable_methods(d,vva,ib,secs,count=24):
    vf=v2f(vva,ib,secs)
    out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        if not is_exec_va(va,ib,secs): break
        out.append((i,i*4,va))
    return out

def direct_call_index(d,ib,secs):
    callers=defaultdict(list); outgoing=defaultdict(list)
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-5,s["raw"]+s["rs"]-5)
        cur=None
        while p<=end:
            if d[p:p+3]==b"\x55\x8B\xEC": cur=f2v(p,ib,secs)
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None:
                    dst=(sva+5+i32(d,p+1))&0xffffffff
                    if is_exec_va(dst,ib,secs):
                        callers[dst].append((p,cur))
                        if cur is not None: outgoing[cur].append((p,dst))
                p+=5;continue
            p+=1
    return callers,outgoing

REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def classify(op,mr):
    # Direction for common memory instructions.
    reg=(mr>>3)&7
    if op==0x8B: return "READ"
    if op==0x89: return "WRITE"
    if op in (0xC6,0xC7): return "WRITE"
    if op==0x8D: return "ADDRESS"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7): return "READ"
    if op==0xFF:
        if reg==2: return "CALL_MEM"
        if reg in (0,1): return "READ_WRITE"
        if reg==6: return "READ"
        return "MEM"
    return "MEM"

def scan_field_accesses(d,ib,secs,fields):
    rows=[]
    fsset=set(fields)
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d),s["raw"]+s["rs"])
        while p+3<=end:
            op=d[p]
            if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
                p+=1;continue
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
            if rm==4:
                p+=1;continue
            disp=None;inslen=None;form=None
            if mod==1:
                disp=d[p+2]
                inslen=3;form="disp8"
            elif mod==2 and p+6<=end:
                disp=u32(d,p+2)
                inslen=6;form="disp32"
            if disp not in fsset:
                p+=1;continue
            f=prologue(d,p);fva=f2v(f,ib,secs) if f is not None else None
            rows.append(dict(
                file=p,va=f2v(p,ib,secs),fn_file=f,fn_va=fva,field=disp,
                op=op,modrm=mr,base=REGS[rm],kind=classify(op,mr),form=form
            ))
            p+=inslen or 1
    return rows

def function_direct_refs(d,fs,fe,values):
    out=[]
    for label,val in values.items():
        pat=struct.pack("<I",val)
        pos=fs
        while True:
            j=d.find(pat,pos,fe)
            if j<0:break
            out.append((j,label,val))
            pos=j+1
    return out

def reverse_distance(starts,callers,max_depth=4):
    dist={s:0 for s in starts};q=deque(starts)
    while q:
        va=q.popleft();dep=dist[va]
        if dep>=max_depth:continue
        for _,pva in callers.get(va,[]):
            if pva is not None and pva not in dist:
                dist[pva]=dep+1;q.append(pva)
    return dist

def forward_distance(starts,outgoing,max_depth=4):
    dist={s:0 for s in starts};q=deque(starts)
    while q:
        va=q.popleft();dep=dist[va]
        if dep>=max_depth:continue
        for _,dst in outgoing.get(va,[]):
            if dst not in dist:
                dist[dst]=dep+1;q.append(dst)
    return dist

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
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
        if cur!=exp:raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    callers,outgoing=direct_call_index(d,ib,secs)
    gmethods=vtable_methods(d,GBBW_VTABLE,ib,secs)
    rmethods=vtable_methods(d,RESEARCH_VTABLE,ib,secs)
    gset={va for _,_,va in gmethods}
    rset={va for _,_,va in rmethods}

    accesses=scan_field_accesses(d,ib,secs,FIELDS)
    writes44=[x for x in accesses if x["field"]==TARGET_FIELD and x["kind"] in ("WRITE","READ_WRITE")]
    reads44=[x for x in accesses if x["field"]==TARGET_FIELD and x["kind"] in ("READ","CALL_MEM","ADDRESS","MEM")]

    # Relatedness to GarageBottomBarWidget graph.
    rev=reverse_distance(gset|{BUTTON_REGISTRY,READY_UI,BUILD_CALLBACK},callers,4)
    fwd=forward_distance(gset|{BUTTON_REGISTRY,READY_UI,BUILD_CALLBACK},outgoing,4)

    candidates=[]
    for x in writes44:
        fn=x["fn_va"]
        score=0;why=[]
        if fn in gset: score+=100;why.append("GBBW_VTABLE_METHOD")
        if fn in rset: score-=20;why.append("RESEARCH_METHOD")
        if fn in rev: score+=30-max(0,rev[fn])*4;why.append(f"CALLS_INTO_GBBW_GRAPH_d{rev[fn]}")
        if fn in fwd: score+=25-max(0,fwd[fn])*3;why.append(f"CALLED_FROM_GBBW_GRAPH_d{fwd[fn]}")
        if fn and 0x00960000<=fn<=0x00980000: score+=15;why.append("GARAGE_UI_REGION")
        if fn:
            ff=v2f(fn,ib,secs)
            if ff is not None:
                fe=next_prologue(d,ff,0x3000)
                refs=function_direct_refs(d,ff,fe,{
                    "build_callback":BUILD_CALLBACK,
                    "register_helper":REGISTER_HELPER,
                    "invoke_helper":INVOKE_HELPER,
                    "gbbw_vtable":GBBW_VTABLE,
                    "gs_garage_vtable":GS_GARAGE_VTABLE,
                    "build_handler":BUILD_HANDLER,
                })
                for _,lab,_ in refs:
                    score+=35;why.append("REF_"+lab)
        candidates.append((score,x,why))
    candidates.sort(key=lambda t:(-t[0],t[1]["file"]))

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE69_BUILD_ACTION_FIELD44"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE69-BUILD-ACTION-FIELD44.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*104)
    w(" ReXtreme Phase 69 - exact GarageBottomBarWidget +0x44 writer map (disp8 + disp32)")
    w("="*104)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Phase68 correction: x86 short displacement accesses (e.g. 8B 49 44) are now included.")
    w("")

    w("===== GARAGE BOTTOM BAR VTABLE METHODS =====")
    for idx,slot,va in gmethods:
        w(f"slot=0x{slot:02X} index={idx:02d} VA=0x{va:08X}")
    w("")

    w("===== ALL CALLBACK FIELD ACCESS COUNTS =====")
    for fld in FIELDS:
        rr=[x for x in accesses if x["field"]==fld]
        bykind=defaultdict(int)
        for x in rr:bykind[x["kind"]]+=1
        w(f"field=0x{fld:X} total={len(rr)} "+ " ".join(f"{k}={v}" for k,v in sorted(bykind.items())))
    w("")

    w("===== EXACT +0x44 WRITES =====")
    w(f"Count={len(writes44)}")
    for x in writes44:
        w(f"file=0x{x['file']:08X} VA=0x{x['va']:08X} fn={('0x%08X'%x['fn_va']) if x['fn_va'] else 'N/A'} kind={x['kind']} op=0x{x['op']:02X} modrm=0x{x['modrm']:02X} base={x['base']} form={x['form']}")
        lines.extend(dump(d,x["file"]-48,x["file"]+96))
    w("")

    w("===== EXACT +0x44 READS / ADDRESS USES =====")
    w(f"Count={len(reads44)}")
    for x in reads44[:400]:
        w(f"file=0x{x['file']:08X} VA=0x{x['va']:08X} fn={('0x%08X'%x['fn_va']) if x['fn_va'] else 'N/A'} kind={x['kind']} op=0x{x['op']:02X} modrm=0x{x['modrm']:02X} base={x['base']} form={x['form']}")
    w("")

    w("===== RANKED +0x44 WRITER CANDIDATES =====")
    for rank,(score,x,why) in enumerate(candidates[:120],1):
        fn=x["fn_va"]
        w(f"#{rank} score={score} writeFile=0x{x['file']:08X} fn={('0x%08X'%fn) if fn else 'N/A'} base={x['base']} kind={x['kind']} why={';'.join(why) if why else 'none'}")
        if fn:
            ff=v2f(fn,ib,secs)
            if ff is not None:
                fe=next_prologue(d,ff,0x2000)
                w(f" functionFile=0x{ff:08X} end=0x{fe:08X}")
                lines.extend(dump(d,ff,min(fe,ff+0x900)))
                ups=callers.get(fn,[])
                w(f" directCallers={len(ups)}")
                for cp,parent in ups[:80]:
                    w(f"  callerFile=0x{cp:08X} parentFn={('0x%08X'%parent) if parent else 'N/A'}")
        w("")

    # Functions that both access +0x44 and another callback field; useful for constructors/setters.
    fnfields=defaultdict(set)
    fnrows=defaultdict(list)
    for x in accesses:
        if x["fn_va"] is not None:
            fnfields[x["fn_va"]].add(x["field"])
            fnrows[x["fn_va"]].append(x)
    multi=sorted([(fn,fs) for fn,fs in fnfields.items() if TARGET_FIELD in fs and len(fs)>=2],
                 key=lambda z:(-len(z[1]),z[0]))

    w("===== FUNCTIONS TOUCHING +0x44 AND OTHER CALLBACK FIELDS =====")
    w(f"Count={len(multi)}")
    for fn,fs in multi[:160]:
        w(f"fn=0x{fn:08X} fields="+",".join(f"0x{x:X}" for x in sorted(fs)))
        ff=v2f(fn,ib,secs)
        if ff is not None:
            lines.extend(dump(d,ff,min(next_prologue(d,ff,0x2000),ff+0x900)))
    w("")

    w("===== BUILD CALLBACK CONFIRMATION =====")
    bf=v2f(BUILD_CALLBACK,ib,secs)
    lines.extend(dump(d,bf,next_prologue(d,bf,0x300)))
    w("Expected first member read: 8B 49 44")
    w("")

    strong=[(score,x,why) for score,x,why in candidates if score>=50]
    w("===== STRONG CANDIDATES =====")
    w(f"Count={len(strong)}")
    for score,x,why in strong[:40]:
        w(f"score={score} writeFile=0x{x['file']:08X} fn={('0x%08X'%x['fn_va']) if x['fn_va'] else 'N/A'} why={';'.join(why)}")

    obj={
        "phase":"69-build-action-field44",
        "ams_sha256":cursha,
        "field44_write_count":len(writes44),
        "field44_read_count":len(reads44),
        "strong_candidates":[
            {
                "score":score,
                "write_file":f"0x{x['file']:08X}",
                "function_va":f"0x{x['fn_va']:08X}" if x["fn_va"] else None,
                "why":why,
            } for score,x,why in strong[:50]
        ],
        "top_candidates":[
            {
                "score":score,
                "write_file":f"0x{x['file']:08X}",
                "function_va":f"0x{x['fn_va']:08X}" if x["fn_va"] else None,
                "base":x["base"],
                "kind":x["kind"],
                "why":why,
            } for score,x,why in candidates[:50]
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")
    print("="*104)
    print(" PHASE 69 FIELD +0x44 WRITER MAP READY")
    print("="*104)
    print("Writes to +0x44:",len(writes44))
    print("Strong candidates:",len(strong))
    if candidates:
        print("Top candidate:",f"fn={candidates[0][1]['fn_va'] and hex(candidates[0][1]['fn_va'])}",f"write={hex(candidates[0][1]['file'])}",f"score={candidates[0][0]}")
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
