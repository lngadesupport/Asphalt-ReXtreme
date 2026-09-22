#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json, bisect, time
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
TARGETS=(0x354,0x358)
NEAR=(0x34C,0x350,0x354,0x358,0x35C,0x360,0x364)
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

OPS={0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF}

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
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

def exec_sections(secs):
    return [s for s in secs if s["ch"]&0x20000000]

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if (s["ch"]&0x20000000) and s["raw"]<=f<s["raw"]+s["rs"]:
            return True
    return False

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

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

def build_prologue_index(d,secs,ib):
    files=[]
    vas=[]
    section_for=[]
    for s in exec_sections(secs):
        start=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
        pos=start
        while True:
            p=d.find(b"\x55\x8B\xEC",pos,end)
            if p<0:break
            files.append(p)
            vas.append(f2v(p,ib,secs))
            section_for.append((start,end))
            pos=p+3
    order=sorted(range(len(files)),key=files.__getitem__)
    files=[files[i] for i in order]
    vas=[vas[i] for i in order]
    section_for=[section_for[i] for i in order]
    return files,vas,section_for

def fn_for_file(off,pro_files,pro_vas,pro_secs):
    i=bisect.bisect_right(pro_files,off)-1
    if i<0:return None
    a,b=pro_secs[i]
    if not(a<=off<b):return None
    return pro_vas[i]

def fn_bounds(fn_va,pro_files,pro_vas,pro_secs,ib,secs):
    fs=v2f(fn_va,ib,secs)
    if fs is None:return None,None
    i=bisect.bisect_left(pro_files,fs)
    if i>=len(pro_files) or pro_files[i]!=fs:
        return fs,min(len(d_global),fs+0x10000)
    sec_a,sec_b=pro_secs[i]
    if i+1<len(pro_files) and pro_files[i+1]<sec_b:
        return fs,pro_files[i+1]
    return fs,sec_b

def build_call_index(d,secs,ib,pro_files,pro_vas,pro_secs):
    callers=defaultdict(list)
    total=0
    for s in exec_sections(secs):
        start=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        pos=start
        while True:
            p=d.find(b"\xE8",pos,end+1)
            if p<0:break
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,ib,secs):
                    caller=fn_for_file(p,pro_files,pro_vas,pro_secs)
                    callers[dst].append((p,caller))
                    total+=1
            pos=p+1
    return callers,total

def build_vtable_ref_functions(d,secs,ib,pro_files,pro_vas,pro_secs):
    funcs=set()
    pat=struct.pack("<I",GS_VTABLE)
    for s in exec_sections(secs):
        start=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
        pos=start
        while True:
            p=d.find(pat,pos,end)
            if p<0:break
            fn=fn_for_file(p,pro_files,pro_vas,pro_secs)
            if fn is not None: funcs.add(fn)
            pos=p+1
    return funcs

def build_disp_refs(d,secs,ib,pro_files,pro_vas,pro_secs):
    byfn=defaultdict(list)
    # Fast path: search the little-endian disp32 bytes, then validate opcode/modrm immediately before it.
    for disp in NEAR:
        pat=struct.pack("<I",disp)
        for s in exec_sections(secs):
            start=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
            pos=start
            while True:
                q=d.find(pat,pos,end)
                if q<0:break
                p=q-2
                if p>=start:
                    op=d[p]; mr=d[p+1]
                    mod=(mr>>6)&3; rm=mr&7
                    if op in OPS and mod==2 and rm!=4:
                        fn=fn_for_file(p,pro_files,pro_vas,pro_secs)
                        if fn is not None:
                            byfn[fn].append((p,disp,classify(op,mr),REGS[rm],op,mr))
                pos=q+1
    return byfn

def all_gs_vtable_methods(d,ib,secs,max_slots=160):
    vf=v2f(GS_VTABLE,ib,secs);out=[]
    if vf is None:return out
    for i in range(max_slots):
        o=vf+i*4
        if o+4>len(d):break
        va=u32(d,o)
        if is_exec_va(va,ib,secs):
            out.append((i,i*4,va))
    return out

def parent_chain(start_va,callers_index,gsset,vtable_ref_funcs,max_depth=4,max_nodes=250):
    q=deque([(start_va,0,[start_va])]);seen=set();paths=[]
    while q and len(seen)<max_nodes:
        va,dep,path=q.popleft()
        if va in seen or dep>=max_depth:continue
        seen.add(va)
        for cp,pva in callers_index.get(va,()):
            flags=[]
            if pva in gsset:flags.append("GS_VMETHOD")
            if pva==GS_CTOR:flags.append("GS_CTOR")
            if pva==GS_BASE_CTOR:flags.append("GS_BASE_CTOR")
            if pva in vtable_ref_funcs:flags.append("REF_GS_VTABLE")
            npath=path+[pva] if pva else path
            paths.append((cp,pva,dep+1,npath,flags))
            if pva is not None:q.append((pva,dep+1,npath))
    return paths

def callsite_this_evidence(d,caller_va,call_file,ib,secs,pro_files,pro_vas,pro_secs):
    if caller_va is None:return []
    fs,fe=fn_bounds(caller_va,pro_files,pro_vas,pro_secs,ib,secs)
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
    global d_global
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes();d_global=d

    print("[1/7] Verificando AMS.exe e guards...",flush=True)
    for n,o,e in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)

    print("[2/7] Indexando prologos de funcoes...",flush=True)
    pro_files,pro_vas,pro_secs=build_prologue_index(d,secs,ib)
    print(f"      funcoes indexadas: {len(pro_files)}",flush=True)

    print("[3/7] Indexando CALLs do executavel (uma unica passada)...",flush=True)
    callers_index,total_calls=build_call_index(d,secs,ib,pro_files,pro_vas,pro_secs)
    print(f"      CALLs indexados: {total_calls}",flush=True)

    print("[4/7] Indexando referencias a GS_Garage vtable...",flush=True)
    vtable_ref_funcs=build_vtable_ref_functions(d,secs,ib,pro_files,pro_vas,pro_secs)
    gs_methods=all_gs_vtable_methods(d,ib,secs,160)
    gsset={va for _,_,va in gs_methods}
    print(f"      metodos GS: {len(gs_methods)}; funcoes com ref vtable: {len(vtable_ref_funcs)}",flush=True)

    print("[5/7] Localizando +0x354/+0x358 e campos vizinhos...",flush=True)
    refs=build_disp_refs(d,secs,ib,pro_files,pro_vas,pro_secs)
    print(f"      funcoes candidatas por offset: {len(refs)}",flush=True)

    print("[6/7] Ranqueando setters pos-construcao...",flush=True)
    candidates=[]
    for fn,rows in refs.items():
        target=[r for r in rows if r[1] in TARGETS and r[2] in ("WRITE","READ_WRITE","ADDRESS")]
        if not target:continue
        fields={r[1] for r in rows}
        score=0;why=[]
        if 0x354 in fields and 0x358 in fields:
            score+=40;why.append("PAIR_354_358")
        if any(r[2]=="WRITE" for r in target):
            score+=25;why.append("WRITE")
        if any(r[2]=="ADDRESS" for r in target):
            score+=15;why.append("ADDRESS")
        if 0x35C in fields or 0x360 in fields:
            score+=15;why.append("NEAR_GBBW_FIELDS")
        if fn in gsset:
            score+=50;why.append("GS_VMETHOD")
        if fn in vtable_ref_funcs:
            score+=25;why.append("REF_GS_VTABLE")
        chains=parent_chain(fn,callers_index,gsset,vtable_ref_funcs,4,250)
        chainflags={flag for x in chains for flag in x[4]}
        if "GS_VMETHOD" in chainflags:
            score+=35;why.append("CALLED_FROM_GS_VMETHOD")
        if "GS_CTOR" in chainflags or "GS_BASE_CTOR" in chainflags:
            score+=20;why.append("CALLED_FROM_GS_CTOR_CHAIN")
        if "REF_GS_VTABLE" in chainflags:
            score+=10;why.append("ANCESTOR_REF_GS_VTABLE")
        candidates.append((score,fn,rows,target,why,chains))
    candidates.sort(key=lambda x:(-x[0],x[1]))

    shortlist=[]
    for score,fn,rows,target,why,chains in candidates:
        if fn==0x00A722A0:continue
        if score>=50 or "GS_VMETHOD" in why or "CALLED_FROM_GS_VMETHOD" in why or "REF_GS_VTABLE" in why:
            shortlist.append((score,fn,why))

    print(f"      candidatos: {len(candidates)}; shortlist forte: {len(shortlist)}",flush=True)
    if candidates:
        print(f"      TOP: 0x{candidates[0][1]:08X} score={candidates[0][0]} {','.join(candidates[0][4])}",flush=True)

    print("[7/7] Gravando relatorio...",flush=True)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE82_OWNER_PAIR_POSTINIT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE82-OWNER-PAIR-POSTINIT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*122)
    w(" ReXtreme Phase 82 FAST - post-constructor setters for GS_Garage+0x354/+0x358")
    w("="*122)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Optimized version: function/call indexes are built once; no repeated full-binary caller scans.")
    w(f"FunctionPrologues={len(pro_files)} IndexedCalls={total_calls}")
    w(f"GSMethods={len(gs_methods)} VtableRefFunctions={len(vtable_ref_funcs)}")
    w("")

    w("===== RANKED POST-INIT CANDIDATES =====")
    w(f"Count={len(candidates)}")
    for rank,(score,fn,rows,target,why,chains) in enumerate(candidates[:120],1):
        fs,fe=fn_bounds(fn,pro_files,pro_vas,pro_secs,ib,secs)
        w(f"#{rank} score={score} fn=0x{fn:08X} file={('0x%08X'%fs) if fs is not None else 'N/A'} end={('0x%08X'%fe) if fe is not None else 'N/A'} why={','.join(why) if why else '-'}")
        for p,disp,kind,base,op,mr in rows:
            if disp in TARGETS or disp in (0x35C,0x360):
                w(f"  {kind} +0x{disp:X} file=0x{p:08X} VA=0x{f2v(p,ib,secs):08X} base={base}")
                lines.extend(dump(d,p-48,p+96))
        c=callers_index.get(fn,())
        w(f"  directCallers={len(c)}")
        for cp,pva in c[:40]:
            ev=callsite_this_evidence(d,pva,cp,ib,secs,pro_files,pro_vas,pro_secs)
            tags=[]
            if pva in gsset:tags.append("GS_VMETHOD")
            if pva==GS_CTOR:tags.append("GS_CTOR")
            if pva==GS_BASE_CTOR:tags.append("GS_BASE_CTOR")
            if pva in vtable_ref_funcs:tags.append("REF_GS_VTABLE")
            w(f"   callerFile=0x{cp:08X} callerFn={('0x%08X'%pva) if pva else 'N/A'} tags={','.join(tags) if tags else '-'} thisEvidence={';'.join(x[1] for x in ev) if ev else '-'}")
        typed=[x for x in chains if x[4]]
        w(f"  typedAncestorPaths={len(typed)}")
        for cp,pva,dep,path,flags in typed[:30]:
            w(f"   depth={dep} viaCaller={('0x%08X'%pva) if pva else 'N/A'} flags={','.join(flags)} path="+" <- ".join(f"0x{x:08X}" for x in path if x))
        w("")
        if rank<=12 and fs is not None and fe is not None:
            lines.extend(dump(d,fs,min(fe,fs+0x700)))
            w("")

    w("===== STRONG SHORTLIST =====")
    w(f"Count={len(shortlist)}")
    for score,fn,why in shortlist[:100]:
        w(f"score={score} fn=0x{fn:08X} why={','.join(why)}")
    w("")

    obj={
      "phase":"82-owner-pair-postinit-fast",
      "ams_sha256":cursha,
      "function_prologues":len(pro_files),
      "indexed_calls":total_calls,
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

    print("PHASE 82 OK",flush=True)
    print("Report:",report,flush=True)
    print("Summary:",summary,flush=True)

if __name__=="__main__":
    main()
