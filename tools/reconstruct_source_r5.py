#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,struct,hashlib,re
from pathlib import Path
from collections import defaultdict,deque

from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

ROOTS={
    "CraftCar_Result":0x009A48A0,
    "CraftCar_ResultApply":0x009A4440,
    "CraftCar_CallerCallback":0x0099E710,
    "CraftCar_Caller":0x0099FF50,
    "GS_Garage_BuildCar":0x00A87960,
}
GS_CTOR=0x00E00B20
GS_LISTENER_OFF=0x298
GS_ACTIVE_OP_OFF=0x3AC

PROFILE_WORDS=(
    "profile","save","owned","ownership","unlock","unlocked","garage","car","vehicle",
    "blueprint","bp_","inventory","credits","hardcurrency","prokits","career","reward",
    "sync","serialize","player","progress"
)

RESULT_GLOBAL_NAMES={
    0x0183DFF4:"prokits_inventory_full_sync",
    0x0183DFCC:"credits_partial_sync",
    0x0183DFC4:"hardcurrency_partial_sync",
    0x0183DFF8:"prokits_inventory_partial_sync",
    0x0183DFC8:"credits_full_sync",
    0x0183E004:None,
}

def u16(b,o):return struct.unpack_from("<H",b,o)[0]
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def i32(b,o):return struct.unpack_from("<i",b,o)[0]
def sha(b):return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0":raise RuntimeError("invalid PE")
    n=u16(d,pe+6);optsz=u16(d,pe+20);opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28);so=opt+optsz;secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({"name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),"vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),"raw":u32(d,o+20),"ch":u32(d,o+36)})
    return ib,secs

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"]<=rva<s["va"]+max(s["vs"],s["rs"]):
            f=s["raw"]+(rva-s["va"])
            if s["raw"]<=f<s["raw"]+s["rs"]:return f
    return None

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:return ib+s["va"]+(off-s["raw"])
    return None

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:return bool(s["ch"]&0x20000000)
    return False

def next_prologue(d,start,secs,limit=0x30000):
    end=min(len(d),start+limit)
    for s in secs:
        if s["raw"]<=start<s["raw"]+s["rs"]:
            end=min(end,s["raw"]+s["rs"]);break
    p=d.find(b"\x55\x8B\xEC",start+3,end)
    return p if p>=0 else end

def func(md,d,va,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,secs)
    return fs,fe,list(md.disasm(d[fs:fe],va))

def read_csv(path):
    if not path.is_file():return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def direct_calls(ins):
    out=[]
    for x in ins:
        if x.mnemonic!="call":continue
        if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
            out.append((x.address,x.operands[0].imm&0xffffffff))
    return out

def direct_jmps(ins):
    out=[]
    for x in ins:
        if x.mnemonic not in ("jmp","je","jne","jz","jnz","ja","jb","jae","jbe","jg","jl","jge","jle"):continue
        if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
            out.append((x.address,x.operands[0].imm&0xffffffff,x.mnemonic))
    return out

def abs_refs(ins):
    out=[]
    for x in ins:
        for op in x.operands:
            va=None
            if op.type==X86_OP_IMM:va=op.imm&0xffffffff
            elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index:va=op.mem.disp&0xffffffff
            if va is not None:out.append((x.address,va,x.mnemonic+" "+x.op_str))
    return out

def strings_for_va(sx,va,radius=0x500):
    out=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if abs(fn-va)<=radius:
            t=r.get("string","")
            if t and t not in seen:
                seen.add(t);out.append(t)
    return out[:100]

def profile_score(strings):
    score=0;hits=[]
    for s in strings:
        lo=s.lower()
        for w in PROFILE_WORDS:
            if w in lo:
                score+=1;hits.append(s);break
    return score,list(dict.fromkeys(hits))

def function_start_index(functions):
    rows=[]
    for r in functions:
        try:va=int(r.get("va",""),16);fs=int(r.get("file_start",""),16)
        except:continue
        rows.append((va,fs,r))
    rows.sort()
    return rows

def nearest_function(rows,va):
    # exact first; then previous by VA
    exact=[x for x in rows if x[0]==va]
    if exact:return exact[0][2]
    prev=None
    for x in rows:
        if x[0]>va:break
        prev=x
    return prev[2] if prev else None

def detect_listener_vtable_writes(md,d,ib,secs):
    hits=[]
    # Search all executable functions for literal +0x298 memory refs.
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);sva=ib+s["va"]
        for x in md.disasm(d[a:b],sva):
            for op in x.operands:
                if op.type!=X86_OP_MEM:continue
                if op.mem.disp!=GS_LISTENER_OFF:continue
                base=md.reg_name(op.mem.base) if op.mem.base else ""
                hits.append({"va":f"0x{x.address:08X}","mnemonic":x.mnemonic,"op_str":x.op_str,"base":base})
    return hits

def find_vtable_immediates_near_listener(md,d,ib,secs,listener_hits):
    out=[]
    for h in listener_hits:
        va=int(h["va"],16)
        f=v2f(va,ib,secs)
        if f is None:continue
        start=max(0,f-0x80);end=min(len(d),f+0x180)
        code_va=f2v(start,ib,secs)
        if code_va is None:continue
        ins=list(md.disasm(d[start:end],code_va))
        for i,x in enumerate(ins):
            if x.address!=va:continue
            lo=max(0,i-20);hi=min(len(ins),i+35)
            candidates=[]
            for y in ins[lo:hi]:
                # Immediate that points to data whose first entries look executable => possible vtable.
                for op in y.operands:
                    if op.type!=X86_OP_IMM:continue
                    imm=op.imm&0xffffffff
                    ff=v2f(imm,ib,secs)
                    if ff is None or ff+8>len(d):continue
                    a0=u32(d,ff);a1=u32(d,ff+4)
                    if is_exec_va(a0,ib,secs) and is_exec_va(a1,ib,secs):
                        candidates.append({
                            "near_va":f"0x{y.address:08X}","vtable_va":f"0x{imm:08X}",
                            "slot0":f"0x{a0:08X}","slot4":f"0x{a1:08X}"
                        })
            out.append({"listener_ref":h,"vtable_candidates":candidates})
            break
    return out

def scan_vtables_for_listener_methods(d,ib,secs,known_methods,max_tables=20000):
    known=set(known_methods)
    rows=[]
    # Look through readable non-exec regions for tables containing known code methods.
    for s in secs:
        if s["ch"]&0x20000000:continue
        a=s["raw"];b=min(len(d),a+s["rs"]);p=(a+3)&~3
        while p+8<=b and len(rows)<max_tables:
            v0=u32(d,p);v1=u32(d,p+4)
            if is_exec_va(v0,ib,secs) and is_exec_va(v1,ib,secs):
                vals=[];q=p
                while q+4<=b and len(vals)<64:
                    v=u32(d,q)
                    if not is_exec_va(v,ib,secs):break
                    vals.append(v);q+=4
                if any(v in known for v in vals):
                    rows.append({"vtable_va":f"0x{f2v(p,ib,secs):08X}","entries":[f"0x{x:08X}" for x in vals]})
                    p=q;continue
            p+=4
    return rows

def collect_reachable(md,d,ib,secs,sx,roots,max_depth=8,max_nodes=5000):
    q=deque((name,va,0,[f"{name}:0x{va:08X}"]) for name,va in roots.items())
    seen=set();nodes=[];edges=[]
    while q and len(seen)<max_nodes:
        name,va,depth,path=q.popleft()
        if va in seen or depth>max_depth or not is_exec_va(va,ib,secs):continue
        seen.add(va)
        fx=func(md,d,va,ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        ss=strings_for_va(sx,va,0x600)
        pscore,phits=profile_score(ss)
        calls=direct_calls(ins)
        refs=abs_refs(ins)
        nodes.append({
            "root_name":name,"va":f"0x{va:08X}","depth":depth,
            "file_start":f"0x{fs:08X}","file_end":f"0x{fe:08X}","size":fe-fs,
            "strings":ss,"profile_score":pscore,"profile_hits":phits,
            "path":path,"direct_calls":[f"0x{x[1]:08X}" for x in calls],
            "absolute_refs":[{"from":f"0x{a:08X}","to":f"0x{b:08X}","insn":c} for a,b,c in refs[:200]]
        })
        for cp,dst in calls:
            edges.append({"src":f"0x{va:08X}","call":f"0x{cp:08X}","dst":f"0x{dst:08X}"})
            if depth<max_depth and dst not in seen:
                q.append((name,dst,depth+1,path+[f"0x{dst:08X}"]))
    return nodes,edges

def find_profile_global_writes(md,d,nodes,ib,secs):
    out=[]
    for n in nodes:
        va=int(n["va"],16)
        fx=func(md,d,va,ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        writes=[]
        for x in ins:
            if not x.operands:continue
            dst=x.operands[0]
            if dst.type==X86_OP_MEM and not dst.mem.base and not dst.mem.index:
                addr=dst.mem.disp&0xffffffff
                if x.mnemonic.startswith("mov") or x.mnemonic in ("add","sub","inc","dec","and","or","xor"):
                    writes.append({"va":f"0x{x.address:08X}","global":f"0x{addr:08X}","insn":x.mnemonic+" "+x.op_str})
        if writes:
            out.append({"function_va":n["va"],"profile_score":n["profile_score"],"writes":writes})
    return out

def disasm_text(md,d,va,ib,secs,maxbytes=0x2000):
    fx=func(md,d,va,ib,secs)
    if not fx:return ""
    fs,fe,ins=fx
    lines=[f"; VA 0x{va:08X} FILE 0x{fs:08X}..0x{fe:08X}"]
    for x in ins:
        lines.append(f"0x{x.address:08X}  {x.bytes.hex(' ').upper():<30}  {x.mnemonic} {x.op_str}".rstrip())
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ap.add_argument("--max-depth",type=int,default=10)
    ap.add_argument("--max-nodes",type=int,default=10000)
    ns=ap.parse_args()

    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX"
    src=root/"src-reconstructed"
    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")
    if not atlas.is_dir():raise SystemExit("FULL GAME ATLAS MAX nao encontrado")
    if not src.is_dir():raise SystemExit("src-reconstructed nao encontrado")

    d=ams.read_bytes()
    if sha(d)!=STABLE_SHA:raise SystemExit("AMS SHA inesperado: "+sha(d))
    ib,secs=parse_pe(d)
    sx=read_csv(atlas/"STRING_XREFS.csv")
    funcs=read_csv(atlas/"FUNCTIONS.csv")
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True

    out=src/"reverse"/"r5"
    asm=out/"asm";asm.mkdir(parents=True,exist_ok=True)

    print("[R5 1/9] Confirmando nomes de sync do result handler...",flush=True)
    result_keys=[]
    for va,name in RESULT_GLOBAL_NAMES.items():
        ff=v2f(va,ib,secs)
        raw=u32(d,ff) if ff is not None and ff+4<=len(d) else None
        resolved=name
        if resolved is None and raw is not None:
            sf=v2f(raw,ib,secs)
            if sf is not None:
                end=d.find(b"\0",sf,min(len(d),sf+300))
                if end>sf:
                    try:
                        s=d[sf:end].decode("ascii")
                        if len(s)>=3 and all(32<=ord(c)<=126 for c in s):resolved=s
                    except:pass
        result_keys.append({"global":f"0x{va:08X}","dword":f"0x{raw:08X}" if raw is not None else None,"name":resolved})
        print(f"          0x{va:08X} -> {resolved or 'UNRESOLVED'}",flush=True)

    print("[R5 2/9] Mapeando referencias a GS_Garage+0x298...",flush=True)
    listener_refs=detect_listener_vtable_writes(md,d,ib,secs)
    print("          refs:",len(listener_refs),flush=True)

    print("[R5 3/9] Procurando vtable do listener/subobjeto...",flush=True)
    listener_vtable_evidence=find_vtable_immediates_near_listener(md,d,ib,secs,listener_refs)
    candidates={}
    for e in listener_vtable_evidence:
        for c in e["vtable_candidates"]:
            candidates[c["vtable_va"]]=c
    print("          candidate vtables:",len(candidates),flush=True)

    # Methods that are likely involved even if listener vtable was not found.
    known_methods={ROOTS["CraftCar_CallerCallback"],ROOTS["CraftCar_ResultApply"]}
    for c in candidates.values():
        known_methods.add(int(c["slot0"],16));known_methods.add(int(c["slot4"],16))
    matching_tables=scan_vtables_for_listener_methods(d,ib,secs,known_methods,20000)
    print("          matching vtable runs:",len(matching_tables),flush=True)

    print("[R5 4/9] Construindo success callback graph...",flush=True)
    graph_roots=dict(ROOTS)
    # Seed slot0/slot4 of candidate listener vtables too.
    for idx,c in enumerate(candidates.values()):
        graph_roots[f"ListenerVtable{idx}_slot0"]=int(c["slot0"],16)
        graph_roots[f"ListenerVtable{idx}_slot4"]=int(c["slot4"],16)

    nodes,edges=collect_reachable(md,d,ib,secs,sx,graph_roots,ns.max_depth,ns.max_nodes)
    nodes_sorted=sorted(nodes,key=lambda n:(-n["profile_score"],n["depth"],n["va"]))
    print(f"          nodes={len(nodes)} edges={len(edges)}",flush=True)
    if nodes_sorted:
        print("          TOP profile candidate:",nodes_sorted[0]["va"],"score",nodes_sorted[0]["profile_score"],flush=True)

    print("[R5 5/9] Detectando writers de estado/profile no grafo...",flush=True)
    global_writes=find_profile_global_writes(md,d,nodes,ib,secs)
    profile_nodes=[n for n in nodes_sorted if n["profile_score"]>0]
    print(f"          profile-tagged={len(profile_nodes)} functions-with-global-writes={len(global_writes)}",flush=True)

    print("[R5 6/9] Gerando ASM dos candidatos principais...",flush=True)
    dump_vas=[]
    for n in profile_nodes[:40]:
        dump_vas.append(int(n["va"],16))
    dump_vas += [ROOTS["CraftCar_CallerCallback"],ROOTS["CraftCar_ResultApply"]]
    for c in candidates.values():
        dump_vas += [int(c["slot0"],16),int(c["slot4"],16)]
    for va in list(dict.fromkeys(dump_vas))[:80]:
        txt=disasm_text(md,d,va,ib,secs)
        if txt:(asm/f"fn_{va:08X}.asm.txt").write_text(txt,encoding="utf-8")

    print("[R5 7/9] Gerando modelo de ownership/save...",flush=True)
    # R5 is evidence-first: do not claim a concrete ownership mutation until a reachable function supports it.
    mutation_candidates=[]
    for n in profile_nodes:
        why=[]
        for s in n["profile_hits"]:
            lo=s.lower()
            if "owned" in lo or "unlock" in lo:why.append("ownership-string")
            if "save" in lo or "serialize" in lo:why.append("persistence-string")
            if "blueprint" in lo or "bp_" in lo:why.append("blueprint-string")
            if "inventory" in lo or "sync" in lo:why.append("sync-string")
        mutation_candidates.append({
            "function_va":n["va"],"depth":n["depth"],"profile_score":n["profile_score"],
            "why":sorted(set(why)),"strings":n["profile_hits"],"path":n["path"]
        })

    model={
        "phase":"R5",
        "result_sync_keys":result_keys,
        "listener_offset":"GS_Garage+0x298",
        "active_operation_offset":"GS_Garage+0x3AC",
        "listener_refs":listener_refs,
        "listener_vtable_evidence":listener_vtable_evidence,
        "matching_vtables":matching_tables,
        "graph":{
            "roots":{k:f"0x{v:08X}" for k,v in graph_roots.items()},
            "nodes":nodes,
            "edges":edges
        },
        "mutation_candidates":mutation_candidates[:250],
        "global_write_candidates":global_writes[:250],
        "confidence_note":"A function is not labeled as the ownership mutation unless the reachable code/string evidence supports it.",
        "no_binary_changes":True
    }
    (out/"SUCCESS_CALLBACK_GRAPH.json").write_text(json.dumps(model,indent=2),encoding="utf-8")

    print("[R5 8/9] Atualizando source/docs...",flush=True)
    inc=src/"include"/"rextreme"/"game"/"garage"
    gsrc=src/"src"/"game"/"garage"
    inc.mkdir(parents=True,exist_ok=True);gsrc.mkdir(parents=True,exist_ok=True)

    (inc/"CraftCarSuccessFlow.hpp").write_text('''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

class GS_Garage;

struct CraftCarSuccessFlow {
    // Original CraftCar caller callback constant: 0x0099E710
    static void CallerCallback();

    // Lower-level request result application helper: 0x009A4440
    static void ApplyResult();

    // GS_Garage registers subobject this+0x298 into active operation this+0x3AC.
    // Exact listener vtable/callback is filled from R5 evidence.
};

}
''',encoding="utf-8")

    top=mutation_candidates[0] if mutation_candidates else None
    cxx='''#include "rextreme/game/garage/CraftCarSuccessFlow.hpp"

namespace rextreme::game::garage {

void CraftCarSuccessFlow::CallerCallback() {
    // Original callback function: 0x0099E710.
    // R5 traces its reachable graph toward the operation/listener layer.
}

void CraftCarSuccessFlow::ApplyResult() {
    // Original helper: 0x009A4440.
    // This remains evidence-driven until exact profile ownership writes are proven.
}

}
'''
    if top:
        cxx += "\n// Highest-ranked R5 mutation candidate: "+top["function_va"]+"\n"
    (gsrc/"CraftCarSuccessFlow.cpp").write_text(cxx,encoding="utf-8")

    lines=[
        "# R5 CraftCar success callback and profile mutation trace","",
        "## Confirmed before R5","",
        "- GS_Garage stores the active build operation at +0x3AC/+0x3B0.",
        "- GS_Garage inserts the listener rooted at +0x298 into operation +0x04..+0x08.",
        "- The operation virtual +0x04 is called with that listener.",
        "- CraftCar request fields are car_id, bp_id, bp_balance and bp_price.",
        "",
        "## Result synchronization keys",""
    ]
    for x in result_keys:lines.append("- "+x["global"]+" -> "+str(x["name"]))
    lines+=["","## R5 callback graph","",
            f"- Reachable nodes: {len(nodes)}",
            f"- Edges: {len(edges)}",
            f"- Listener vtable candidates: {len(candidates)}",
            f"- Profile-tagged reachable functions: {len(profile_nodes)}",
            "",
            "## Highest-ranked mutation candidates",""]
    for x in mutation_candidates[:20]:
        lines.append("- "+x["function_va"]+" score="+str(x["profile_score"])+" why="+",".join(x["why"])+" strings="+" | ".join(x["strings"][:8]))
    lines+=["","## Next step","",
            "If R5 resolves the listener callback and a concrete ownership/profile mutation, R6 can implement the local craft transaction and persistence path. Otherwise R6 will broaden the clean-room reconstruction around the top reachable candidates."]
    (src/"docs"/"R5-CRAFTCAR-SUCCESS-PROFILE.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R5"
    manifest["r5_success_graph"]="reverse/r5/SUCCESS_CALLBACK_GRAPH.json"
    manifest["r5_result_sync_keys"]=result_keys
    manifest["r5_listener_vtable_candidate_count"]=len(candidates)
    manifest["r5_graph_nodes"]=len(nodes)
    manifest["r5_graph_edges"]=len(edges)
    manifest["r5_profile_candidate_count"]=len(profile_nodes)
    manifest["r5_top_mutation_candidates"]=mutation_candidates[:20]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R5 9/9] SOURCE RECONSTRUCTION R5 OK",flush=True)
    print("Graph nodes:",len(nodes),flush=True)
    print("Listener vtable candidates:",len(candidates),flush=True)
    print("Profile candidates:",len(profile_nodes),flush=True)
    print("Output:",out/"SUCCESS_CALLBACK_GRAPH.json",flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
