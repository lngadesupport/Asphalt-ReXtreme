#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, struct, hashlib
from pathlib import Path
from collections import deque, defaultdict

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

GS_CTOR=0x00E00B20
GS_BUILD=0x00A87960
GS_VTABLE=0x0186A9CC
LISTENER_OFF=0x298
ACTIVE_OP_OFF=0x3AC

CRAFT_CALLER=0x0099FF50
CRAFT_CALLER_CB=0x0099E710
CRAFT_RESULT=0x009A48A0
CRAFT_RESULT_APPLY=0x009A4440

RESULT_KEYS={
    0x0183DFF4:"prokits_inventory_full_sync",
    0x0183DFCC:"credits_partial_sync",
    0x0183DFC4:"hardcurrency_partial_sync",
    0x0183E004:"server_items_partial_sync",
    0x0183DFF8:"prokits_inventory_partial_sync",
    0x0183DFC8:"credits_full_sync",
}

PROFILE_WORDS=(
    "own_","owned","ownership","unlock","blueprint","bp_","inventory",
    "profile","save","serialize","sync","credits","hardcurrency","car_id",
    "vehicle","garage","server_items"
)

REG_NAMES=("eax","ecx","edx","ebx","esp","ebp","esi","edi")

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
        secs.append({
            "name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
            "raw":u32(d,o+20),"ch":u32(d,o+36)
        })
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

def strings_near_function(sx,va,radius=0x500):
    out=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if abs(fn-va)<=radius:
            t=r.get("string","")
            if t and t not in seen:
                seen.add(t);out.append(t)
    return out

def direct_target(x):
    if x.mnemonic not in ("call","jmp"):return None
    if len(x.operands)!=1 or x.operands[0].type!=X86_OP_IMM:return None
    return x.operands[0].imm & 0xffffffff

def read_vtable(d,vt,ib,secs,max_slots=128):
    f=v2f(vt,ib,secs)
    if f is None:return []
    out=[]
    for i in range(max_slots):
        if f+i*4+4>len(d):break
        t=u32(d,f+i*4)
        if not is_exec_va(t,ib,secs):break
        out.append({"slot":i*4,"target":t})
    return out

def possible_vtable(d,va,ib,secs,min_entries=2):
    f=v2f(va,ib,secs)
    if f is None:return False
    n=0
    for i in range(16):
        if f+i*4+4>len(d):break
        t=u32(d,f+i*4)
        if not is_exec_va(t,ib,secs):break
        n+=1
    return n>=min_entries

def ins_dict(md,x,base_va=None):
    return {
        "va":f"0x{x.address:08X}",
        "bytes":x.bytes.hex(" ").upper(),
        "mnemonic":x.mnemonic,
        "op_str":x.op_str
    }

def track_typed_this(md,d,entry_va,ib,secs,max_depth=12,max_states=30000):
    """
    Interprocedural lightweight this-flow:
    state origin=offset from original GS this.
    Follows ECX and explicit register aliases, stack argument passing,
    and calls where ECX carries a GS-derived pointer.
    """
    q=deque([{
        "va":entry_va,"mode":"ecx","origin":0,"depth":0,
        "path":[f"0x{entry_va:08X}"]
    }])
    seen=set();states=[];subobject_calls=[];field_hits=[];vtable_writes=[]

    while q and len(seen)<max_states:
        st=q.popleft()
        key=(st["va"],st["mode"],st["origin"])
        if key in seen or st["depth"]>max_depth:continue
        seen.add(key)
        fx=func(md,d,st["va"],ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        regs={}
        locals_={}
        if st["mode"]=="ecx":
            regs["ecx"]=st["origin"]
        elif st["mode"].startswith("arg"):
            # seed is picked up from [ebp+8+4*n] lazily
            pass
        states.append({"va":st["va"],"origin":st["origin"],"depth":st["depth"],"path":st["path"]})

        recent_push=[]
        for idx,x in enumerate(ins):
            m=x.mnemonic
            ops=x.operands

            # mov reg,reg
            if m=="mov" and len(ops)==2 and ops[0].type==X86_OP_REG:
                dst=md.reg_name(ops[0].reg)
                if ops[1].type==X86_OP_REG:
                    src=md.reg_name(ops[1].reg)
                    if src in regs:regs[dst]=regs[src]
                    else:regs.pop(dst,None)
                elif ops[1].type==X86_OP_MEM:
                    mem=ops[1].mem
                    base=md.reg_name(mem.base) if mem.base else ""
                    disp=mem.disp
                    if base=="ebp" and st["mode"].startswith("arg"):
                        try:n=int(st["mode"][3:])
                        except:n=-99
                        if disp==8+4*(n-1):
                            regs[dst]=st["origin"]
                        else:
                            regs.pop(dst,None)
                    elif base=="ebp" and disp in locals_:
                        regs[dst]=locals_[disp]
                    else:
                        regs.pop(dst,None)

            # lea reg,[derived+disp]
            if m=="lea" and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_MEM:
                dst=md.reg_name(ops[0].reg);mem=ops[1].mem
                base=md.reg_name(mem.base) if mem.base else ""
                if base in regs and not mem.index:
                    regs[dst]=regs[base]+mem.disp
                    eff=regs[dst]
                    if eff==LISTENER_OFF:
                        field_hits.append({
                            "function":f"0x{st['va']:08X}","insn":ins_dict(md,x),
                            "effective_offset":f"0x{eff:X}","path":st["path"]
                        })
                else:regs.pop(dst,None)

            # mov [mem],reg/imm
            if m=="mov" and len(ops)==2 and ops[0].type==X86_OP_MEM:
                mem=ops[0].mem;base=md.reg_name(mem.base) if mem.base else ""
                if base=="ebp" and ops[1].type==X86_OP_REG:
                    src=md.reg_name(ops[1].reg)
                    if src in regs:locals_[mem.disp]=regs[src]
                elif base in regs and not mem.index:
                    eff=regs[base]+mem.disp
                    if eff==LISTENER_OFF:
                        field_hits.append({
                            "function":f"0x{st['va']:08X}","insn":ins_dict(md,x),
                            "effective_offset":f"0x{eff:X}","path":st["path"]
                        })
                    if ops[1].type==X86_OP_IMM:
                        imm=ops[1].imm&0xffffffff
                        if possible_vtable(d,imm,ib,secs):
                            vtable_writes.append({
                                "function":f"0x{st['va']:08X}","insn":ins_dict(md,x),
                                "object_origin":f"0x{regs[base]:X}",
                                "effective_field":f"0x{eff:X}",
                                "vtable":f"0x{imm:08X}","path":st["path"]
                            })

            # push derived pointer
            if m=="push" and len(ops)==1:
                origin=None;via=None
                if ops[0].type==X86_OP_REG:
                    r=md.reg_name(ops[0].reg)
                    if r in regs:origin=regs[r];via=r
                elif ops[0].type==X86_OP_MEM:
                    mem=ops[0].mem;base=md.reg_name(mem.base) if mem.base else ""
                    if base in regs and not mem.index:
                        origin=regs[base]+mem.disp;via=f"[{base}+0x{mem.disp:X}]"
                recent_push.append((x.address,origin,via))
                recent_push=recent_push[-12:]

            if m=="call":
                dst=direct_target(x)
                if dst is not None and is_exec_va(dst,ib,secs):
                    # thiscall propagation
                    if "ecx" in regs:
                        origin=regs["ecx"]
                        q.append({"va":dst,"mode":"ecx","origin":origin,"depth":st["depth"]+1,
                                  "path":st["path"]+[f"0x{dst:08X}(ecx=+0x{origin:X})"]})
                        if origin==LISTENER_OFF:
                            subobject_calls.append({
                                "caller":f"0x{st['va']:08X}","callsite":f"0x{x.address:08X}",
                                "callee":f"0x{dst:08X}","origin":"0x298","path":st["path"]
                            })
                    # stack args: last push = arg1
                    for argn,(p,origin,via) in enumerate(reversed(recent_push[-8:]),1):
                        if origin is None:continue
                        q.append({"va":dst,"mode":f"arg{argn}","origin":origin,"depth":st["depth"]+1,
                                  "path":st["path"]+[f"0x{dst:08X}(arg{argn}=+0x{origin:X})"]})
                        if origin==LISTENER_OFF:
                            subobject_calls.append({
                                "caller":f"0x{st['va']:08X}","callsite":f"0x{x.address:08X}",
                                "callee":f"0x{dst:08X}","origin":"0x298","via":via,"path":st["path"]
                            })
                recent_push=[]
                for r in ("eax","ecx","edx"):regs.pop(r,None)

    return {
        "states":states,
        "field_hits":field_hits,
        "subobject_calls":subobject_calls,
        "vtable_writes":vtable_writes,
        "queue_exhausted":not q
    }

def find_ctor_vtable(md,d,ctor_va,ib,secs):
    fx=func(md,d,ctor_va,ib,secs)
    if not fx:return []
    fs,fe,ins=fx
    out=[]
    # Constructors normally begin with ecx=this; follow simple aliases.
    regs={"ecx":0}
    for x in ins:
        if x.mnemonic=="mov" and len(x.operands)==2 and x.operands[0].type==X86_OP_REG:
            dst=md.reg_name(x.operands[0].reg)
            if x.operands[1].type==X86_OP_REG:
                src=md.reg_name(x.operands[1].reg)
                if src in regs:regs[dst]=regs[src]
                else:regs.pop(dst,None)
        if x.mnemonic=="mov" and len(x.operands)==2 and x.operands[0].type==X86_OP_MEM and x.operands[1].type==X86_OP_IMM:
            mem=x.operands[0].mem;base=md.reg_name(mem.base) if mem.base else ""
            if base in regs and not mem.index:
                imm=x.operands[1].imm&0xffffffff
                if possible_vtable(d,imm,ib,secs):
                    out.append({"insn":ins_dict(md,x),"vtable":f"0x{imm:08X}","field":f"0x{regs[base]+mem.disp:X}"})
    return out

def success_reachable(md,d,ib,secs,sx,start_va,max_depth=7,max_nodes=2500):
    """
    Branch-aware-ish reachability for status==0:
    we keep direct calls, but score only functions close to result/apply and
    preserve path provenance. This is intentionally narrower than R5.
    """
    q=deque([(start_va,0,[f"0x{start_va:08X}"])])
    seen=set();nodes=[];edges=[]
    while q and len(seen)<max_nodes:
        va,depth,path=q.popleft()
        if va in seen or depth>max_depth or not is_exec_va(va,ib,secs):continue
        seen.add(va)
        fx=func(md,d,va,ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        strings=strings_near_function(sx,va,0x280)
        hits=[]
        for s in strings:
            lo=s.lower()
            if any(w in lo for w in PROFILE_WORDS):hits.append(s)
        calls=[]
        for x in ins:
            dst=direct_target(x)
            if x.mnemonic=="call" and dst is not None and is_exec_va(dst,ib,secs):
                calls.append((x.address,dst))
        nodes.append({
            "va":f"0x{va:08X}","depth":depth,"path":path,
            "file_start":f"0x{fs:08X}","file_end":f"0x{fe:08X}",
            "profile_hits":list(dict.fromkeys(hits)),
            "direct_calls":[f"0x{x[1]:08X}" for x in calls]
        })
        for cp,dst in calls:
            edges.append({"src":f"0x{va:08X}","call":f"0x{cp:08X}","dst":f"0x{dst:08X}"})
            if depth<max_depth:q.append((dst,depth+1,path+[f"0x{dst:08X}"]))
    return nodes,edges

def exact_immediate_xrefs(md,d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);sva=ib+s["va"]
        for x in md.disasm(d[a:b],sva):
            found=False
            for op in x.operands:
                if op.type==X86_OP_IMM and (op.imm&0xffffffff)==target:found=True
                elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index and (op.mem.disp&0xffffffff)==target:found=True
            if found:out.append(ins_dict(md,x))
    return out

def asm_dump(md,d,va,ib,secs):
    fx=func(md,d,va,ib,secs)
    if not fx:return ""
    fs,fe,ins=fx
    lines=[f"; VA 0x{va:08X} FILE 0x{fs:08X}..0x{fe:08X} SIZE {fe-fs}"]
    for x in ins:lines.append(f"0x{x.address:08X}  {x.bytes.hex(' ').upper():<30}  {x.mnemonic} {x.op_str}".rstrip())
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

    out=src/"reverse"/"r6";asm=out/"asm";asm.mkdir(parents=True,exist_ok=True)

    print("[R6 1/10] Validando sync keys R5...",flush=True)
    for va,name in RESULT_KEYS.items():print(f"          0x{va:08X} -> {name}",flush=True)

    print("[R6 2/10] Refazendo typed flow do GS_Garage ctor...",flush=True)
    typed=track_typed_this(md,d,GS_CTOR,ib,secs,max_depth=14,max_states=50000)
    print("          states=",len(typed["states"]),"listener hits=",len(typed["field_hits"]),"subobject calls=",len(typed["subobject_calls"]),flush=True)

    print("[R6 3/10] Identificando ctor/vtable do listener +0x298...",flush=True)
    listener_ctors=[]
    for c in typed["subobject_calls"]:
        va=int(c["callee"],16)
        vts=find_ctor_vtable(md,d,va,ib,secs)
        if vts:
            listener_ctors.append({"call":c,"ctor":c["callee"],"vtable_writes":vts})
    unique_vts={}
    for x in listener_ctors:
        for v in x["vtable_writes"]:
            unique_vts[v["vtable"]]=v
    print("          listener ctors=",len(listener_ctors),"vtables=",len(unique_vts),flush=True)

    print("[R6 4/10] Lendo slots das vtables tipadas...",flush=True)
    typed_vtables=[]
    listener_methods=set()
    for vt in unique_vts:
        entries=read_vtable(d,int(vt,16),ib,secs,64)
        typed_vtables.append({"vtable":vt,"entries":[{"slot":f"0x{x['slot']:X}","target":f"0x{x['target']:08X}"} for x in entries]})
        for x in entries:listener_methods.add(x["target"])
    print("          listener methods=",len(listener_methods),flush=True)

    print("[R6 5/10] Procurando usos exatos das vtables/callbacks...",flush=True)
    method_xrefs={}
    for va in sorted(listener_methods)[:128]:
        method_xrefs[f"0x{va:08X}"]=exact_immediate_xrefs(md,d,va,ib,secs)[:100]
    cb_xrefs=exact_immediate_xrefs(md,d,CRAFT_CALLER_CB,ib,secs)
    print("          callback 0x0099E710 xrefs=",len(cb_xrefs),flush=True)

    print("[R6 6/10] Construindo grafo estreito do caminho de sucesso...",flush=True)
    success_roots=[CRAFT_RESULT_APPLY,CRAFT_CALLER_CB]
    for va in listener_methods:success_roots.append(va)
    success_sets=[]
    all_nodes=[];all_edges=[]
    for rva in list(dict.fromkeys(success_roots)):
        ns,es=success_reachable(md,d,ib,secs,sx,rva,7,3000)
        success_sets.append({"root":f"0x{rva:08X}","node_count":len(ns),"edge_count":len(es)})
        for n in ns:
            n=dict(n);n["root"]=f"0x{rva:08X}";all_nodes.append(n)
        for e in es:
            e=dict(e);e["root"]=f"0x{rva:08X}";all_edges.append(e)

    # Rank only by actual strings on narrow graph.
    candidates=[]
    seen_c=set()
    for n in all_nodes:
        if not n["profile_hits"]:continue
        key=(n["root"],n["va"])
        if key in seen_c:continue
        seen_c.add(key)
        weight=0;why=[]
        for s in n["profile_hits"]:
            lo=s.lower()
            if "owned" in lo or "own_" in lo or "unlock" in lo:weight+=8;why.append("ownership")
            if "blueprint" in lo or "bp_" in lo:weight+=6;why.append("blueprint")
            if "save" in lo or "serialize" in lo:weight+=6;why.append("persistence")
            if "sync" in lo or "inventory" in lo or "server_items" in lo:weight+=4;why.append("sync")
            if "credits" in lo or "hardcurrency" in lo:weight+=2;why.append("economy")
            if "car_id" in lo or "vehicle" in lo:weight+=2;why.append("car")
        candidates.append({
            "root":n["root"],"va":n["va"],"depth":n["depth"],"score":weight,
            "why":sorted(set(why)),"strings":n["profile_hits"],"path":n["path"]
        })
    candidates.sort(key=lambda x:(-x["score"],x["depth"],x["va"]))
    print("          narrow candidates=",len(candidates),flush=True)
    if candidates:print("          TOP",candidates[0]["va"],"score",candidates[0]["score"],flush=True)

    print("[R6 7/10] Detectando semantica do callback 0x0099E710...",flush=True)
    cb_fx=func(md,d,CRAFT_CALLER_CB,ib,secs)
    cb_sem={"clears_slots":[],"direct_calls":[]}
    if cb_fx:
        fs,fe,ins=cb_fx
        for x in ins:
            if x.mnemonic=="mov" and len(x.operands)==2 and x.operands[0].type==X86_OP_MEM and x.operands[1].type==X86_OP_IMM and (x.operands[1].imm&0xffffffff)==0:
                mem=x.operands[0].mem;base=md.reg_name(mem.base) if mem.base else ""
                if base and 0<=mem.disp<=0x200:
                    cb_sem["clears_slots"].append({"base":base,"offset":f"0x{mem.disp:X}","insn":ins_dict(md,x)})
            dst=direct_target(x)
            if x.mnemonic=="call" and dst is not None:cb_sem["direct_calls"].append(f"0x{dst:08X}")
    # Known R5 observation: clears +0x90/+0x94, so classify cleanup unless contrary evidence.
    offs={x["offset"] for x in cb_sem["clears_slots"]}
    cb_sem["classification"]="operation-slot cleanup callback" if {"0x90","0x94"}.issubset(offs) and not cb_sem["direct_calls"] else "unresolved"

    print("[R6 8/10] Gravando ASM dos pontos decisivos...",flush=True)
    dump_vas=[GS_CTOR,GS_BUILD,CRAFT_RESULT,CRAFT_RESULT_APPLY,CRAFT_CALLER_CB]
    dump_vas+=list(listener_methods)
    dump_vas += [int(x["va"],16) for x in candidates[:30]]
    for va in list(dict.fromkeys(dump_vas))[:100]:
        txt=asm_dump(md,d,va,ib,secs)
        if txt:(asm/f"fn_{va:08X}.asm.txt").write_text(txt,encoding="utf-8")

    print("[R6 9/10] Gerando modelo de transacao local...",flush=True)
    model={
        "phase":"R6",
        "corrections":{
            "r5_listener_scan":"discarded: R5 +0x298 refs were ESP-relative stack accesses, not typed GS_Garage accesses"
        },
        "result_sync_keys":[{"global":f"0x{k:08X}","name":v} for k,v in RESULT_KEYS.items()],
        "typed_gs_ctor_flow":{
            "state_count":len(typed["states"]),
            "queue_exhausted":typed["queue_exhausted"],
            "listener_hits":typed["field_hits"],
            "subobject_calls":typed["subobject_calls"],
            "vtable_writes":typed["vtable_writes"]
        },
        "listener_constructors":listener_ctors,
        "listener_vtables":typed_vtables,
        "listener_method_xrefs":method_xrefs,
        "craft_caller_callback_xrefs":cb_xrefs,
        "craft_caller_callback_semantics":cb_sem,
        "success_graph_roots":[f"0x{x:08X}" for x in success_roots],
        "success_sets":success_sets,
        "top_success_mutation_candidates":candidates[:250],
        "decision":{
            "can_implement_binary_local_transaction": bool(unique_vts and candidates and candidates[0]["score"]>=8),
            "reason":"requires typed listener callback plus success-path mutation evidence"
        },
        "no_binary_changes":True
    }
    (out/"LOCAL_CRAFT_TRANSACTION.json").write_text(json.dumps(model,indent=2),encoding="utf-8")

    # Source scaffold
    inc=src/"include"/"rextreme"/"game"/"garage";cpp=src/"src"/"game"/"garage"
    inc.mkdir(parents=True,exist_ok=True);cpp.mkdir(parents=True,exist_ok=True)
    (inc/"LocalCraftTransaction.hpp").write_text('''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

struct LocalCraftTransaction {
    std::int32_t carId = 0;
    std::int32_t blueprintId = 0;
    std::int32_t blueprintBalance = 0;
    std::int32_t blueprintPrice = 0;

    bool Apply();
};

}
''',encoding="utf-8")
    top=candidates[0] if candidates else None
    cxx='''#include "rextreme/game/garage/LocalCraftTransaction.hpp"

namespace rextreme::game::garage {

bool LocalCraftTransaction::Apply() {
    // R6 intentionally does not mutate profile data until the exact typed
    // success listener and ownership/save function are proven.
    return false;
}

}
'''
    if top:cxx+="\n// R6 highest-ranked narrow success candidate: "+top["va"]+"\n"
    (cpp/"LocalCraftTransaction.cpp").write_text(cxx,encoding="utf-8")

    lines=[
        "# R6 Typed listener and local craft transaction",
        "",
        "## R5 correction",
        "",
        "R5 listener-vtable discovery is discarded because its +0x298 references were ESP-relative stack accesses, not GS_Garage-relative accesses.",
        "",
        "## Typed GS_Garage constructor flow",
        "",
        f"- States: {len(typed['states'])}",
        f"- Listener +0x298 hits: {len(typed['field_hits'])}",
        f"- Calls receiving typed +0x298: {len(typed['subobject_calls'])}",
        f"- Listener constructors with vtable evidence: {len(listener_ctors)}",
        f"- Distinct listener vtables: {len(unique_vts)}",
        "",
        "## Craft caller callback 0x0099E710",
        "",
        "- Classification: "+cb_sem["classification"],
        "- Cleared slots: "+", ".join(x["offset"] for x in cb_sem["clears_slots"]),
        "",
        "## Narrow success candidates",
        ""
    ]
    for x in candidates[:25]:
        lines.append("- "+x["va"]+" score="+str(x["score"])+" depth="+str(x["depth"])+" why="+",".join(x["why"])+" strings="+" | ".join(x["strings"][:8]))
    lines += [
        "",
        "## Decision",
        "",
        "Binary/local transaction implementation is enabled only when a typed listener vtable and a strong success-path mutation candidate are both recovered.",
        "See reverse/r6/LOCAL_CRAFT_TRANSACTION.json for the exact machine-readable evidence."
    ]
    (src/"docs"/"R6-LOCAL-CRAFT-TRANSACTION.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R6"
    manifest["r6_local_transaction"]="reverse/r6/LOCAL_CRAFT_TRANSACTION.json"
    manifest["r6_listener_ctor_count"]=len(listener_ctors)
    manifest["r6_listener_vtable_count"]=len(unique_vts)
    manifest["r6_callback_classification"]=cb_sem["classification"]
    manifest["r6_top_success_candidates"]=candidates[:25]
    manifest["r6_can_implement_binary_local_transaction"]=model["decision"]["can_implement_binary_local_transaction"]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R6 10/10] SOURCE RECONSTRUCTION R6 OK",flush=True)
    print("Listener constructors:",len(listener_ctors),flush=True)
    print("Listener vtables:",len(unique_vts),flush=True)
    print("Callback classification:",cb_sem["classification"],flush=True)
    print("Narrow mutation candidates:",len(candidates),flush=True)
    print("Can implement local transaction:",model["decision"]["can_implement_binary_local_transaction"],flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
