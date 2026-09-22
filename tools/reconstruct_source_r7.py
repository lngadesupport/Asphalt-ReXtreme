#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct,hashlib
from pathlib import Path
from collections import deque

from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

GS_CTOR=0x00E00B20
GS_BUILD=0x00A87960
LISTENER_OFF=0x298
FINAL_LISTENER_VT=0x0186AC70
CRAFT_RESULT=0x009A48A0
RESULT_APPLY=0x009A4440

PROFILE_WORDS=(
    "own_","owned","ownership","unlock","blueprint","bp_","inventory","profile",
    "save","serialize","sync","credits","hardcurrency","server_items","car_id",
    "cars","vehicle","garage","purchase","buy_a_car"
)

def u16(b,o):return struct.unpack_from("<H",b,o)[0]
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def sha(b):return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0":raise RuntimeError("invalid PE")
    n=u16(d,pe+6);optsz=u16(d,pe+20);opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28);so=opt+optsz;secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({"name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
                     "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
                     "raw":u32(d,o+20),"ch":u32(d,o+36)})
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
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
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

def read_vtable(d,vt,ib,secs,max_slots=32):
    f=v2f(vt,ib,secs)
    if f is None:return []
    out=[]
    for i in range(max_slots):
        if f+i*4+4>len(d):break
        t=u32(d,f+i*4)
        if not is_exec_va(t,ib,secs):break
        out.append({"slot":i*4,"target":t})
    return out

def direct_target(x):
    if x.mnemonic not in ("call","jmp"):return None
    if len(x.operands)!=1 or x.operands[0].type!=X86_OP_IMM:return None
    return x.operands[0].imm&0xffffffff

def insrow(x):
    return {"va":f"0x{x.address:08X}","bytes":x.bytes.hex(" ").upper(),
            "mnemonic":x.mnemonic,"op_str":x.op_str}

def resolve_adjustor(md,d,va,ib,secs,max_hops=8):
    chain=[]
    cur=va
    total_adjust=0
    for hop in range(max_hops):
        fx=func(md,d,cur,ib,secs)
        if not fx:break
        fs,fe,ins=fx
        small=ins[:12]
        chain.append({"va":f"0x{cur:08X}","preview":[insrow(x) for x in small]})
        next_va=None
        # Recognize common x86 this-adjusting thunks.
        for x in small:
            if x.mnemonic in ("sub","add") and len(x.operands)==2 and x.operands[0].type==X86_OP_REG:
                r=md.reg_name(x.operands[0].reg)
                if r=="ecx" and x.operands[1].type==X86_OP_IMM:
                    imm=x.operands[1].imm
                    total_adjust += (-imm if x.mnemonic=="sub" else imm)
            elif x.mnemonic=="lea" and len(x.operands)==2 and x.operands[0].type==X86_OP_REG and x.operands[1].type==X86_OP_MEM:
                if md.reg_name(x.operands[0].reg)=="ecx":
                    m=x.operands[1].mem
                    if m.base and md.reg_name(m.base)=="ecx" and not m.index:
                        total_adjust += m.disp
            if x.mnemonic=="jmp":
                dst=direct_target(x)
                if dst is not None and is_exec_va(dst,ib,secs):
                    next_va=dst
                break
            # a real call/body means stop treating as pure thunk
            if x.mnemonic=="call" or x.mnemonic in ("ret","retn"):
                break
        if next_va is None or next_va==cur:break
        cur=next_va
    return {"entry":f"0x{va:08X}","resolved":f"0x{cur:08X}","this_adjust":total_adjust,"chain":chain}

def strings_near(sx,va,radius=0x350):
    out=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if abs(fn-va)<=radius:
            t=r.get("string","")
            if t and t not in seen:
                seen.add(t);out.append(t)
    return out[:120]

def score_strings(strings):
    score=0;hits=[];why=[]
    for s in strings:
        lo=s.lower()
        if any(w in lo for w in PROFILE_WORDS):
            hits.append(s)
            if "own_" in lo or "owned" in lo or "ownership" in lo or "unlock" in lo:
                score+=10;why.append("ownership")
            elif "blueprint" in lo or "bp_" in lo:
                score+=8;why.append("blueprint")
            elif "save" in lo or "serialize" in lo:
                score+=8;why.append("persistence")
            elif "sync" in lo or "inventory" in lo or "server_items" in lo:
                score+=5;why.append("sync")
            elif "credits" in lo or "hardcurrency" in lo:
                score+=3;why.append("economy")
            else:score+=1
    return score,list(dict.fromkeys(hits)),sorted(set(why))

def calls_from(ins):
    out=[]
    for x in ins:
        if x.mnemonic!="call":continue
        dst=direct_target(x)
        if dst is not None:out.append((x.address,dst))
    return out

def branch_tests(md,ins):
    out=[]
    for i,x in enumerate(ins):
        if x.mnemonic not in ("cmp","test"):continue
        txt=x.op_str.lower()
        if "0" not in txt and ", 0" not in txt:continue
        ctx=[insrow(y) for y in ins[max(0,i-3):min(len(ins),i+6)]]
        out.append({"test":insrow(x),"context":ctx})
    return out

def success_graph(md,d,ib,secs,sx,roots,max_depth=8,max_nodes=5000):
    q=deque((name,va,0,[f"{name}:0x{va:08X}"]) for name,va in roots.items())
    seen=set();nodes=[];edges=[]
    while q and len(seen)<max_nodes:
        name,va,depth,path=q.popleft()
        key=(name,va)
        if key in seen or depth>max_depth or not is_exec_va(va,ib,secs):continue
        seen.add(key)
        fx=func(md,d,va,ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        ss=strings_near(sx,va)
        score,hits,why=score_strings(ss)
        calls=calls_from(ins)
        nodes.append({"root":name,"va":f"0x{va:08X}","depth":depth,"file_start":f"0x{fs:08X}",
                      "file_end":f"0x{fe:08X}","score":score,"why":why,"strings":hits,
                      "zero_tests":branch_tests(md,ins),"path":path,
                      "calls":[f"0x{x[1]:08X}" for x in calls]})
        for cp,dst in calls:
            edges.append({"root":name,"src":f"0x{va:08X}","call":f"0x{cp:08X}","dst":f"0x{dst:08X}"})
            if depth<max_depth and is_exec_va(dst,ib,secs):
                q.append((name,dst,depth+1,path+[f"0x{dst:08X}"]))
    return nodes,edges

def callback_dispatch_context(md,d,va,ib,secs):
    fx=func(md,d,va,ib,secs)
    if not fx:return []
    fs,fe,ins=fx
    out=[]
    for i,x in enumerate(ins):
        # indirect virtual call [reg+4]
        if x.mnemonic=="call" and len(x.operands)==1 and x.operands[0].type==X86_OP_MEM:
            m=x.operands[0].mem
            if m.disp==4:
                out.append({"call":insrow(x),"context":[insrow(y) for y in ins[max(0,i-12):min(len(ins),i+8)]]})
    return out

def asm_dump(md,d,va,ib,secs):
    fx=func(md,d,va,ib,secs)
    if not fx:return ""
    fs,fe,ins=fx
    lines=[f"; VA 0x{va:08X} FILE 0x{fs:08X}..0x{fe:08X} SIZE {fe-fs}"]
    for x in ins:
        lines.append(f"0x{x.address:08X}  {x.bytes.hex(' ').upper():<30}  {x.mnemonic} {x.op_str}".rstrip())
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
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
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True

    out=src/"reverse"/"r7";asm=out/"asm";asm.mkdir(parents=True,exist_ok=True)

    print("[R7 1/9] Lendo vtable FINAL de GS_Garage+0x298...",flush=True)
    entries=read_vtable(d,FINAL_LISTENER_VT,ib,secs,32)
    if len(entries)<2:raise SystemExit("vtable 0x0186AC70 invalida/curta")
    for e in entries:print(f"          slot +0x{e['slot']:X} -> 0x{e['target']:08X}",flush=True)

    print("[R7 2/9] Resolvendo slot +0x04 / adjustor thunk...",flush=True)
    slot4=next((e for e in entries if e["slot"]==4),None)
    if not slot4:raise SystemExit("slot +0x04 ausente")
    slot0=next((e for e in entries if e["slot"]==0),None)
    slot4_res=resolve_adjustor(md,d,slot4["target"],ib,secs)
    slot0_res=resolve_adjustor(md,d,slot0["target"],ib,secs) if slot0 else None
    handler=int(slot4_res["resolved"],16)
    print("          slot+4 entry=0x%08X resolved=0x%08X adjust=%d"%(slot4["target"],handler,slot4_res["this_adjust"]),flush=True)

    print("[R7 3/9] Validando callsite virtual +0x04 no result pipeline...",flush=True)
    dispatch=callback_dispatch_context(md,d,CRAFT_RESULT,ib,secs)
    print("          virtual +4 callsites:",len(dispatch),flush=True)

    print("[R7 4/9] Analisando handler real do listener...",flush=True)
    fx=func(md,d,handler,ib,secs)
    if not fx:raise SystemExit("handler do listener nao desassemblavel")
    hfs,hfe,hins=fx
    hstrings=strings_near(sx,handler,0x500)
    hscore,hhits,hwhy=score_strings(hstrings)
    hcalls=calls_from(hins)
    hzero=branch_tests(md,hins)
    handler_meta={
        "entry":slot4_res["entry"],"resolved":slot4_res["resolved"],
        "this_adjust":slot4_res["this_adjust"],
        "file_start":f"0x{hfs:08X}","file_end":f"0x{hfe:08X}","size":hfe-hfs,
        "profile_score":hscore,"why":hwhy,"strings":hhits,
        "calls":[{"from":f"0x{a:08X}","to":f"0x{b:08X}"} for a,b in hcalls],
        "zero_tests":hzero
    }
    print(f"          handler size={hfe-hfs} direct calls={len(hcalls)} profileScore={hscore}",flush=True)

    print("[R7 5/9] Seguindo grafo APENAS a partir do callback real...",flush=True)
    roots={"GS_Garage_CraftListener_slot4":handler}
    nodes,edges=success_graph(md,d,ib,secs,sx,roots,9,7000)
    ranked=sorted([n for n in nodes if n["score"]>0],key=lambda x:(-x["score"],x["depth"],x["va"]))
    print(f"          nodes={len(nodes)} edges={len(edges)} ranked={len(ranked)}",flush=True)
    if ranked:print("          TOP",ranked[0]["va"],"score",ranked[0]["score"],ranked[0]["why"],flush=True)

    print("[R7 6/9] Isolando candidatos de ownership/persistence...",flush=True)
    decisive=[]
    for n in ranked:
        if any(w in n["why"] for w in ("ownership","persistence","blueprint","sync")):
            decisive.append(n)
    # prefer shallow candidates
    decisive.sort(key=lambda x:(x["depth"],-x["score"],x["va"]))
    for n in decisive[:20]:
        print(f"          {n['va']} depth={n['depth']} score={n['score']} why={','.join(n['why'])}",flush=True)

    print("[R7 7/9] Gravando ASM dos pontos decisivos...",flush=True)
    dump=[slot4["target"],handler,CRAFT_RESULT,RESULT_APPLY]
    dump += [int(x["va"],16) for x in decisive[:30]]
    for va in list(dict.fromkeys(dump))[:80]:
        txt=asm_dump(md,d,va,ib,secs)
        if txt:(asm/f"fn_{va:08X}.asm.txt").write_text(txt,encoding="utf-8")

    print("[R7 8/9] Gerando modelo de callback/local transaction...",flush=True)
    strong=bool(decisive and decisive[0]["depth"]<=4 and decisive[0]["score"]>=8)
    model={
        "phase":"R7",
        "final_listener_subobject":"GS_Garage+0x298",
        "final_listener_vtable":"0x0186AC70",
        "vtable_entries":[{"slot":f"0x{x['slot']:X}","target":f"0x{x['target']:08X}"} for x in entries],
        "slot0":slot0_res,
        "slot4_callback":slot4_res,
        "result_virtual_dispatch_context":dispatch,
        "resolved_handler":handler_meta,
        "callback_graph":{"node_count":len(nodes),"edge_count":len(edges)},
        "ranked_candidates":ranked[:300],
        "decisive_candidates":decisive[:100],
        "decision":{
            "typed_listener_resolved":True,
            "strong_profile_mutation_candidate":strong,
            "can_prepare_runtime_patch":strong,
            "note":"No AMS bytes changed by R7."
        }
    }
    (out/"TYPED_LISTENER_CALLBACK.json").write_text(json.dumps(model,indent=2),encoding="utf-8")

    # Update source scaffold with the now-known vtable.
    inc=src/"include"/"rextreme"/"game"/"garage";cpp=src/"src"/"game"/"garage"
    inc.mkdir(parents=True,exist_ok=True);cpp.mkdir(parents=True,exist_ok=True)
    (inc/"GarageCraftListener.hpp").write_text(f'''#pragma once
#include <cstdint>

namespace rextreme::game::garage {{

class GarageCraftListener {{
public:
    // Embedded at GS_Garage+0x298.
    // Final vtable: 0x0186AC70.
    // Slot +0x04 entry: 0x{slot4["target"]:08X}.
    // Resolved handler: 0x{handler:08X}.
    void OnCraftResult();
}};

}}
''',encoding="utf-8")
    (cpp/"GarageCraftListener.cpp").write_text(f'''#include "rextreme/game/garage/GarageCraftListener.hpp"

namespace rextreme::game::garage {{

// Original callback entry: 0x{slot4["target"]:08X}
// Resolved body:          0x{handler:08X}
// this adjustment:        {slot4_res["this_adjust"]}
void GarageCraftListener::OnCraftResult() {{
    // R7 recovered the exact virtual callback target.
    // Branch/body translation is driven by reverse/r7/TYPED_LISTENER_CALLBACK.json.
}}

}}
''',encoding="utf-8")

    lines=[
        "# R7 Typed GS_Garage craft listener callback","",
        "## Key correction","",
        "GS_Garage+0x298 is an embedded polymorphic subobject. It receives vtable values directly during base/derived construction; a separate subobject constructor call is not required.",
        "",
        "## Final vtable","",
        "- GS_Garage+0x298 final vtable: 0x0186AC70.",
        f"- Slot +0x04 entry: 0x{slot4['target']:08X}.",
        f"- Resolved callback body: 0x{handler:08X}.",
        f"- this adjustment: {slot4_res['this_adjust']}.",
        "",
        "## Callback graph","",
        f"- Reachable nodes from real callback: {len(nodes)}.",
        f"- Edges: {len(edges)}.",
        f"- Ranked profile candidates: {len(ranked)}.",
        f"- Decisive ownership/blueprint/save/sync candidates: {len(decisive)}.",
        "",
        "## Top decisive candidates",""
    ]
    for x in decisive[:20]:
        lines.append("- "+x["va"]+" depth="+str(x["depth"])+" score="+str(x["score"])+" why="+",".join(x["why"])+" strings="+" | ".join(x["strings"][:8]))
    lines+=["","## Runtime decision","",f"- can_prepare_runtime_patch = {strong}"]
    (src/"docs"/"R7-TYPED-CRAFT-LISTENER.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R7"
    manifest["r7_final_listener_vtable"]="0x0186AC70"
    manifest["r7_listener_slot4_entry"]=f"0x{slot4['target']:08X}"
    manifest["r7_listener_resolved_handler"]=f"0x{handler:08X}"
    manifest["r7_listener_this_adjust"]=slot4_res["this_adjust"]
    manifest["r7_callback_graph_nodes"]=len(nodes)
    manifest["r7_decisive_candidate_count"]=len(decisive)
    manifest["r7_can_prepare_runtime_patch"]=strong
    manifest["r7_top_decisive_candidates"]=decisive[:20]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R7 9/9] SOURCE RECONSTRUCTION R7 OK",flush=True)
    print("Final listener vtable: 0x0186AC70",flush=True)
    print("Slot +0x04: 0x%08X"%slot4["target"],flush=True)
    print("Resolved handler: 0x%08X"%handler,flush=True)
    print("This adjust:",slot4_res["this_adjust"],flush=True)
    print("Decisive candidates:",len(decisive),flush=True)
    print("Can prepare runtime patch:",strong,flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
