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

GS_VTABLE=0x0186A9CC
GS_CTOR=0x00E00B20
GS_BASE_CTOR=0x00B070C0
GS_SLOT_DC=0x00ABE7E0
BUILD_HANDLER=0x00A87960
TARGETS=(0x354,0x358)
NEAR=(0x34C,0x350,0x354,0x358,0x35C,0x360,0x364)
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8v(x): return x-256 if x>=128 else x
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

def exec_ranges(secs):
    return [(s["raw"],s["raw"]+s["rs"]) for s in secs if s["ch"]&0x20000000]

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    return any(a<=f<b for a,b in exec_ranges(secs))

def prev_prologue(d,near,section_start=0,limit=0x10000):
    lo=max(section_start,near-limit)
    p=near
    while p>=lo:
        if d[p:p+3]==b"\x55\x8B\xEC":return p
        p-=1
    return None

def next_prologue(d,start,section_end=None,limit=0x10000):
    z=min(len(d), start+limit, section_end if section_end is not None else len(d))
    p=d.find(b"\x55\x8B\xEC",start+3,z)
    return p if p>=0 else z

def section_bounds_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return s["raw"],s["raw"]+s["rs"]
    return 0,len(d_global)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8v(d[p+2]),3
    if mod==2 and p+6<=fe:return rm,i32(d,p+2),6
    return None

def classify(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    return "MEM"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def direct_callers(d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    pf=prev_prologue(d,p,s["raw"])
                    out.append((p,f2v(pf,ib,secs) if pf is not None else None,pf))
                    p+=5;continue
            p+=1
    return out

def all_gs_vtable_methods(d,ib,secs,max_slots=160):
    vf=v2f(GS_VTABLE,ib,secs)
    out=[]
    if vf is None:return out
    for i in range(max_slots):
        o=vf+i*4
        if o+4>len(d):break
        va=u32(d,o)
        if is_exec_va(va,ib,secs):
            out.append((i,i*4,va))
    return out

def scan_disp_refs(d,secs,target_disps):
    byfn=defaultdict(list)
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"]; end=min(len(d)-6,s["raw"]+s["rs"]-6)
        while p<=end:
            op=d[p]
            if op in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
                dec=decode_mem(d,p,end+1)
                if dec:
                    rm,disp,ln=dec
                    if disp in target_disps:
                        pf=prev_prologue(d,p,s["raw"])
                        pva=f2v(pf,ib_global,secs) if pf is not None else None
                        byfn[pva].append((p,disp,classify(op,d[p+1]),REGS[rm],op,d[p+1]))
                        p+=ln;continue
            p+=1
    return byfn

def function_direct_calls(d,fn_va,ib,secs):
    fs=v2f(fn_va,ib,secs)
    if fs is None:return []
    a,b=section_bounds_for_file(fs,secs)
    fe=next_prologue(d,fs,b,0x10000)
    out=[];p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:out.append((p,dst))
            p+=5;continue
        p+=1
    return out

def refs_imm32_in_function(d,fn_va,value,ib,secs):
    fs=v2f(fn_va,ib,secs)
    if fs is None:return []
    a,b=section_bounds_for_file(fs,secs)
    fe=next_prologue(d,fs,b,0x10000)
    pat=struct.pack("<I",value)
    out=[];pos=fs
    while True:
        j=d.find(pat,pos,fe)
        if j<0:break
        out.append(j);pos=j+1
    return out

def parent_chain_flags(d,start_va,gs_methods,ib,secs,max_depth=4,max_nodes=200):
    gsset={va for _,_,va in gs_methods}
    q=deque([(start_va,0,[start_va])]);seen=set();paths=[]
    while q and len(seen)<max_nodes:
        va,dep,path=q.popleft()
        if va in seen or dep>=max_depth:continue
        seen.add(va)
        for cp,pva,pf in direct_callers(d,va,ib,secs):
            flags=[]
            if pva in gsset:flags.append("GS_VMETHOD")
            if pva==GS_CTOR:flags.append("GS_CTOR")
            if pva==GS_BASE_CTOR:flags.append("GS_BASE_CTOR")
            if pva and refs_imm32_in_function(d,pva,GS_VTABLE,ib,secs):flags.append("REF_GS_VTABLE")
            paths.append((cp,pva,dep+1,path+[pva] if pva else path,flags))
            if pva is not None:q.append((pva,dep+1,path+[pva]))
    return paths

def callsite_this_evidence(d,caller_va,call_file,ib,secs):
    # Heuristic: identify if caller appears to preserve its this in ESI/EDI/EBX
    # and moves that register into ECX immediately before call.
    fs=v2f(caller_va,ib,secs)
    if fs is None:return []
    lo=max(fs,call_file-40)
    evid=[]
    for r in ("esi","edi","ebx","eax"):
        rid=REGS.index(r)
        for pat in (bytes([0x8B,0xC8|rid]),bytes([0x89,0xC1|(rid<<3)])):
            p=d.rfind(pat,lo,call_file)
            if p>=0:evid.append((p,f"mov ecx,{r}"))
    return sorted(evid)

def main():
    global d_global, ib_global
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes();d_global=d

    for n,o,e in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d);ib_global=ib
    gs_methods=all_gs_vtable_methods(d,ib,secs,160)
    refs=scan_disp_refs(d,secs,set(NEAR))

    candidates=[]
    for fn,rows in refs.items():
        if fn is None:continue
        target=[r for r in rows if r[1] in TARGETS and r[2] in ("WRITE","READ_WRITE","ADDRESS")]
        if not target:continue
        fields=set(r[1] for r in rows)
        kinds=defaultdict(set)
        for r in rows:kinds[r[1]].add(r[2])
        score=0;why=[]
        if 0x354 in fields and 0x358 in fields:
            score+=40;why.append("PAIR_354_358")
        if any(r[2]=="WRITE" for r in target):
            score+=25;why.append("WRITE")
        if any(r[2]=="ADDRESS" for r in target):
            score+=15;why.append("ADDRESS")
        if 0x35C in fields or 0x360 in fields:
            score+=15;why.append("NEAR_GBBW_FIELDS")
        if fn in {va for _,_,va in gs_methods}:
            score+=50;why.append("GS_VMETHOD")
        if refs_imm32_in_function(d,fn,GS_VTABLE,ib,secs):
            score+=25;why.append("REF_GS_VTABLE")
        chains=parent_chain_flags(d,fn,gs_methods,ib,secs,4,200)
        chainflags=set(flag for x in chains for flag in x[4])
        if "GS_VMETHOD" in chainflags:
            score+=35;why.append("CALLED_FROM_GS_VMETHOD")
        if "GS_CTOR" in chainflags or "GS_BASE_CTOR" in chainflags:
            score+=20;why.append("CALLED_FROM_GS_CTOR_CHAIN")
        if "REF_GS_VTABLE" in chainflags:
            score+=10;why.append("ANCESTOR_REF_GS_VTABLE")
        candidates.append((score,fn,rows,target,why,chains))

    candidates.sort(key=lambda x:(-x[0],x[1]))

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE82_OWNER_PAIR_POSTINIT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE82-OWNER-PAIR-POSTINIT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*122)
    w(" ReXtreme Phase 82 - post-constructor setters for GS_Garage+0x354/+0x358")
    w("="*122)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Phase81 proved +0x354/+0x358 are zero-initialized in base ctor 0x00A722A0.")
    w("This phase finds later WRITE/ADDRESS users and ranks them by typed GS_Garage evidence.")
    w(f"GS vtable executable entries scanned={len(gs_methods)}")
    w("")

    w("===== RANKED POST-INIT CANDIDATES =====")
    w(f"Count={len(candidates)}")
    for rank,(score,fn,rows,target,why,chains) in enumerate(candidates[:120],1):
        fs=v2f(fn,ib,secs); a,b=section_bounds_for_file(fs,secs);fe=next_prologue(d,fs,b,0x10000)
        w(f"#{rank} score={score} fn=0x{fn:08X} file=0x{fs:08X} end=0x{fe:08X} why={','.join(why) if why else '-'}")
        for p,disp,kind,base,op,mr in rows:
            if disp in TARGETS or disp in (0x35C,0x360):
                w(f"  {kind} +0x{disp:X} file=0x{p:08X} VA=0x{f2v(p,ib,secs):08X} base={base}")
                lines.extend(dump(d,p-56,p+104))
        c=direct_callers(d,fn,ib,secs)
        w(f"  directCallers={len(c)}")
        for cp,pva,pf in c[:40]:
            ev=callsite_this_evidence(d,pva,cp,ib,secs) if pva else []
            tags=[]
            if pva in {va for _,_,va in gs_methods}:tags.append("GS_VMETHOD")
            if pva==GS_CTOR:tags.append("GS_CTOR")
            if pva==GS_BASE_CTOR:tags.append("GS_BASE_CTOR")
            if pva and refs_imm32_in_function(d,pva,GS_VTABLE,ib,secs):tags.append("REF_GS_VTABLE")
            w(f"   callerFile=0x{cp:08X} callerFn={('0x%08X'%pva) if pva else 'N/A'} tags={','.join(tags) if tags else '-'} thisEvidence={';'.join(x[1] for x in ev) if ev else '-'}")
        typed=[x for x in chains if x[4]]
        w(f"  typedAncestorPaths={len(typed)}")
        for cp,pva,dep,path,flags in typed[:30]:
            w(f"   depth={dep} viaCaller={('0x%08X'%pva) if pva else 'N/A'} flags={','.join(flags)} path="+" <- ".join(f"0x{x:08X}" for x in path if x))
        w("")
        if rank<=20:
            lines.extend(dump(d,fs,min(fe,fs+0x900)))
            w("")

    # Strong shortlist: pair functions with typed GS ancestry, excluding known zero-init ctor.
    shortlist=[]
    for score,fn,rows,target,why,chains in candidates:
        if fn==0x00A722A0:continue
        if score>=50 or "GS_VMETHOD" in why or "CALLED_FROM_GS_VMETHOD" in why or "REF_GS_VTABLE" in why:
            shortlist.append((score,fn,why))
    w("===== STRONG SHORTLIST =====")
    w(f"Count={len(shortlist)}")
    for score,fn,why in shortlist[:80]:
        w(f"score={score} fn=0x{fn:08X} why={','.join(why)}")
    w("")

    obj={
      "phase":"82-owner-pair-postinit",
      "ams_sha256":cursha,
      "candidate_count":len(candidates),
      "strong_shortlist":[
        {"score":score,"function_va":f"0x{fn:08X}","why":why}
        for score,fn,why in shortlist[:100]
      ],
      "top_candidates":[
        {
          "score":score,"function_va":f"0x{fn:08X}","why":why,
          "target_refs":[
            {"file":f"0x{r[0]:08X}","field":f"0x{r[1]:X}","kind":r[2],"base":r[3]}
            for r in target
          ]
        } for score,fn,rows,target,why,chains in candidates[:30]
      ],
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*122)
    print(" PHASE 82 OWNER PAIR POST-INIT MAP READY")
    print("="*122)
    print("Candidates:",len(candidates))
    print("Strong shortlist:",len(shortlist))
    if candidates:
        x=candidates[0]
        print("TOP:",hex(x[1]),"score",x[0],",".join(x[4]) if x[4] else "-")
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
