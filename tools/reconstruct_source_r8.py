#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,struct,hashlib
from pathlib import Path
from collections import deque,defaultdict

from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

CALLBACK=0x00AA4D00
OWN_CAR_CANDIDATE=0x00AC9D60
KNOWN_ERROR_CODES=[0x1389,0x1771,0x1396,0x177E,0x1397,0x177F]
COMPARE_CODES=[0,1,2,0x1389,0x1771,0x1396,0x177E,0x1397,0x177F]

KEYWORDS={
 "ownership":("own_car","owned","ownership","unlock"),
 "blueprint":("blueprint","bp_","need_blueprints"),
 "profile":("profile","save","serialize"),
 "sync":("inventory","sync","server_items"),
 "economy":("credits","hardcurrency","price_"),
 "ui":("button","widget","garage","template","container","label_","movie_")
}

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
        if s["raw"]<=off<s["raw"]+s["rs"]:return ib+s["va"]+(off-s["raw"])
    return None

def is_exec(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:return bool(s["ch"]&0x20000000)
    return False

def next_prologue(d,start,secs,limit=0x40000):
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

def direct_target(x):
    if x.mnemonic not in ("call","jmp","je","jne","jz","jnz","ja","jae","jb","jbe","jg","jge","jl","jle"):return None
    if len(x.operands)!=1 or x.operands[0].type!=X86_OP_IMM:return None
    return x.operands[0].imm&0xffffffff

def insrow(x):
    return {"va":f"0x{x.address:08X}","bytes":x.bytes.hex(" ").upper(),"mnemonic":x.mnemonic,"op_str":x.op_str}

def strings_near(sx,va,radius=0x300):
    out=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if abs(fn-va)<=radius:
            t=r.get("string","")
            if t and t not in seen:
                seen.add(t);out.append(t)
    return out

def classify_strings(ss):
    tags=defaultdict(list)
    for s in ss:
        lo=s.lower()
        for k,words in KEYWORDS.items():
            if any(w in lo for w in words):tags[k].append(s)
    return {k:list(dict.fromkeys(v)) for k,v in tags.items()}

def regname(md,op):
    return md.reg_name(op.reg) if op.type==X86_OP_REG else None

def mem_is_arg0(md,op):
    if op.type!=X86_OP_MEM:return False
    m=op.mem
    return bool(m.base and md.reg_name(m.base)=="ebp" and not m.index and m.disp==8)

def eval_operand(md,op,regs,status):
    if op.type==X86_OP_IMM:return op.imm&0xffffffff
    if op.type==X86_OP_REG:return regs.get(md.reg_name(op.reg))
    if mem_is_arg0(md,op):return status&0xffffffff
    return None

def set_reg(md,regs,op,val):
    if op.type==X86_OP_REG:
        r=md.reg_name(op.reg)
        if val is None:regs.pop(r,None)
        else:regs[r]=val&0xffffffff

def flags_cmp(a,b):
    if a is None or b is None:return None
    a&=0xffffffff;b&=0xffffffff
    res=(a-b)&0xffffffff
    zf=(res==0);cf=(a<b)
    sf=bool(res&0x80000000)
    of=bool(((a^b)&(a^res)&0x80000000))
    return {"zf":zf,"cf":cf,"sf":sf,"of":of}

def flags_test(a,b):
    if a is None or b is None:return None
    res=(a&b)&0xffffffff
    return {"zf":res==0,"cf":False,"sf":bool(res&0x80000000),"of":False}

def decide_jcc(mn,fl):
    if fl is None:return None
    zf=fl["zf"];cf=fl["cf"];sf=fl["sf"];of=fl["of"]
    if mn in ("je","jz"):return zf
    if mn in ("jne","jnz"):return not zf
    if mn=="jb":return cf
    if mn=="jae":return not cf
    if mn=="jbe":return cf or zf
    if mn=="ja":return (not cf) and (not zf)
    if mn=="jl":return sf!=of
    if mn=="jge":return sf==of
    if mn=="jle":return zf or (sf!=of)
    if mn=="jg":return (not zf) and (sf==of)
    return None

def concrete_trace(md,d,va,ib,secs,status,max_states=50000):
    fx=func(md,d,va,ib,secs)
    if not fx:return None
    fs,fe,ins=fx
    amap={x.address:x for x in ins}
    nextmap={}
    for i,x in enumerate(ins[:-1]):nextmap[x.address]=ins[i+1].address
    endset={x.address for x in ins}

    q=deque([(va,{},None,[])])
    seen=set();calls=[];vis=[];branches=[];rets=0
    while q and len(seen)<max_states:
        pc,regs,flags,path=q.popleft()
        key=(pc,tuple(sorted(regs.items())),None if flags is None else tuple(sorted(flags.items())))
        if key in seen:continue
        seen.add(key)
        x=amap.get(pc)
        if x is None:continue
        vis.append(pc)
        m=x.mnemonic;ops=x.operands
        nr=dict(regs);nf=flags
        fall=nextmap.get(pc)

        if m=="mov" and len(ops)==2:
            val=eval_operand(md,ops[1],nr,status)
            set_reg(md,nr,ops[0],val)
        elif m=="lea" and len(ops)==2 and ops[0].type==X86_OP_REG:
            # only track LEA if base register is known and no index.
            mem=ops[1].mem if ops[1].type==X86_OP_MEM else None
            val=None
            if mem and mem.base and not mem.index:
                base=nr.get(md.reg_name(mem.base))
                if base is not None:val=(base+mem.disp)&0xffffffff
            set_reg(md,nr,ops[0],val)
        elif m=="xor" and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_REG and ops[0].reg==ops[1].reg:
            set_reg(md,nr,ops[0],0);nf=flags_test(0,0)
        elif m in ("add","sub") and len(ops)==2 and ops[0].type==X86_OP_REG:
            a=eval_operand(md,ops[0],nr,status);b=eval_operand(md,ops[1],nr,status)
            val=None if a is None or b is None else ((a+b) if m=="add" else (a-b))&0xffffffff
            set_reg(md,nr,ops[0],val)
            if a is not None and b is not None:nf=flags_cmp(val,0)
        elif m=="cmp" and len(ops)==2:
            nf=flags_cmp(eval_operand(md,ops[0],nr,status),eval_operand(md,ops[1],nr,status))
        elif m=="test" and len(ops)==2:
            nf=flags_test(eval_operand(md,ops[0],nr,status),eval_operand(md,ops[1],nr,status))

        if m=="call":
            dst=direct_target(x)
            if dst is not None:
                calls.append({"callsite":f"0x{x.address:08X}","target":f"0x{dst:08X}","path_tail":[f"0x{p:08X}" for p in path[-20:]]})
            # x86 caller-saved clobber.
            for r in ("eax","ecx","edx"):nr.pop(r,None)
            if fall:q.append((fall,nr,nf,path+[pc]))
            continue

        if m=="jmp":
            dst=direct_target(x)
            if dst in amap:q.append((dst,nr,nf,path+[pc]))
            continue

        if m.startswith("j") and m!="jmp":
            dst=direct_target(x)
            decision=decide_jcc(m,nf)
            branches.append({"va":f"0x{x.address:08X}","mnemonic":m,"target":f"0x{dst:08X}" if dst else None,
                             "decision":decision,"status":status,"context":insrow(x)})
            if decision is True:
                if dst in amap:q.append((dst,nr,nf,path+[pc]))
            elif decision is False:
                if fall:q.append((fall,nr,nf,path+[pc]))
            else:
                if dst in amap:q.append((dst,dict(nr),nf,path+[pc]))
                if fall:q.append((fall,nr,nf,path+[pc]))
            continue

        if m.startswith("ret"):
            rets+=1;continue

        if fall:q.append((fall,nr,nf,path+[pc]))

    # unique callsites
    uniq=[];seen_c=set()
    for c in calls:
        k=(c["callsite"],c["target"])
        if k not in seen_c:seen_c.add(k);uniq.append(c)
    return {"status":status,"state_count":len(seen),"queue_exhausted":not q,"visited":[f"0x{x:08X}" for x in sorted(set(vis))],
            "calls":uniq,"branches":branches,"returns":rets}

def reachable_graph(md,d,ib,secs,sx,roots,max_depth=6,max_nodes=3500):
    q=deque((name,va,0,[f"{name}:0x{va:08X}"]) for name,va in roots.items())
    seen=set();nodes=[];edges=[]
    while q and len(seen)<max_nodes:
        name,va,depth,path=q.popleft()
        key=(name,va)
        if key in seen or depth>max_depth or not is_exec(va,ib,secs):continue
        seen.add(key)
        fx=func(md,d,va,ib,secs)
        if not fx:continue
        fs,fe,ins=fx
        ss=strings_near(sx,va)
        tags=classify_strings(ss)
        calls=[]
        for x in ins:
            if x.mnemonic=="call":
                dst=direct_target(x)
                if dst is not None and is_exec(dst,ib,secs):calls.append((x.address,dst))
        nodes.append({"root":name,"va":f"0x{va:08X}","depth":depth,"path":path,"tags":tags,
                      "file_start":f"0x{fs:08X}","file_end":f"0x{fe:08X}",
                      "calls":[f"0x{x[1]:08X}" for x in calls]})
        for cp,dst in calls:
            edges.append({"root":name,"src":f"0x{va:08X}","call":f"0x{cp:08X}","dst":f"0x{dst:08X}"})
            if depth<max_depth:q.append((name,dst,depth+1,path+[f"0x{dst:08X}"]))
    return nodes,edges

def xrefs_for_string(sx,text):
    out=[]
    for r in sx:
        if (r.get("string") or "")==text:out.append(r)
    return out

def asm_dump(md,d,va,ib,secs):
    fx=func(md,d,va,ib,secs)
    if not fx:return ""
    fs,fe,ins=fx
    lines=[f"; VA 0x{va:08X} FILE 0x{fs:08X}..0x{fe:08X} SIZE {fe-fs}"]
    for x in ins:lines.append(f"0x{x.address:08X}  {x.bytes.hex(' ').upper():<30}  {x.mnemonic} {x.op_str}".rstrip())
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True);ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe";atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX";src=root/"src-reconstructed"
    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")
    if not atlas.is_dir():raise SystemExit("FULL GAME ATLAS MAX nao encontrado")
    if not src.is_dir():raise SystemExit("src-reconstructed nao encontrado")
    d=ams.read_bytes()
    if sha(d)!=STABLE_SHA:raise SystemExit("AMS SHA inesperado: "+sha(d))
    ib,secs=parse_pe(d);sx=read_csv(atlas/"STRING_XREFS.csv")
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    out=src/"reverse"/"r8";asm=out/"asm";asm.mkdir(parents=True,exist_ok=True)

    print("[R8 1/9] Concrete-slicing callback por status...",flush=True)
    traces={}
    for st in COMPARE_CODES:
        tr=concrete_trace(md,d,CALLBACK,ib,secs,st)
        traces[f"0x{st:X}"]=tr
        print(f"          status=0x{st:X}: states={tr['state_count']} calls={len(tr['calls'])}",flush=True)

    print("[R8 2/9] Separando calls success-only...",flush=True)
    success={(c["callsite"],c["target"]) for c in traces["0x0"]["calls"]}
    errors=set()
    for st in KNOWN_ERROR_CODES:
        for c in traces[f"0x{st:X}"]["calls"]:errors.add((c["callsite"],c["target"]))
    success_only=sorted(success-errors)
    common=sorted(success&errors)
    error_only=sorted(errors-success)
    print("          success-only:",len(success_only),"common:",len(common),"error-only:",len(error_only),flush=True)
    for cs,t in success_only:print("          SUCCESS",cs,"->",t,flush=True)

    print("[R8 3/9] Verificando 0x009C51E0 no ramo success...",flush=True)
    target_9c="0x009C51E0"
    ninec=[x for x in traces["0x0"]["calls"] if x["target"]==target_9c]
    ninec_error=[]
    for st in KNOWN_ERROR_CODES:
        ninec_error += [x for x in traces[f"0x{st:X}"]["calls"] if x["target"]==target_9c]
    ninec_status="SUCCESS_ONLY" if ninec and not ninec_error else ("COMMON" if ninec and ninec_error else "NOT_REACHED")
    print("          0x009C51E0:",ninec_status,flush=True)

    print("[R8 4/9] Grafo somente de calls exclusivas do sucesso...",flush=True)
    roots={}
    for i,(cs,t) in enumerate(success_only):
        va=int(t,16)
        if is_exec(va,ib,secs):roots[f"success_{i}_{cs}"]=va
    nodes,edges=reachable_graph(md,d,ib,secs,sx,roots,7,5000)
    relevant=[]
    for n in nodes:
        strong=[k for k in ("ownership","profile","blueprint","sync","economy") if n["tags"].get(k)]
        if strong:
            relevant.append({**n,"strong_tags":strong})
    relevant.sort(key=lambda n:(n["depth"],-sum(len(n["tags"].get(k,[])) for k in n["strong_tags"]),n["va"]))
    print("          graph nodes=",len(nodes),"relevant=",len(relevant),flush=True)

    print("[R8 5/9] Classificando 0x00AC9D60 / own_car...",flush=True)
    own_fx=func(md,d,OWN_CAR_CANDIDATE,ib,secs)
    own_meta={}
    if own_fx:
        ofs,ofe,oins=own_fx
        own_strings=strings_near(sx,OWN_CAR_CANDIDATE,0x400)
        own_tags=classify_strings(own_strings)
        own_calls=[]
        for x in oins:
            if x.mnemonic=="call":
                dst=direct_target(x)
                if dst is not None:own_calls.append({"from":f"0x{x.address:08X}","to":f"0x{dst:08X}"})
        own_meta={"file_start":f"0x{ofs:08X}","file_end":f"0x{ofe:08X}","size":ofe-ofs,
                  "tags":own_tags,"calls":own_calls,"own_car_xrefs":xrefs_for_string(sx,"own_car")}
        # UI-heavy if UI tag evidence and direct calls to known Garage UI functions.
        ui_targets={"0x0096DF80","0x009768A0","0x00978C80"}
        ui_hits=[c for c in own_calls if c["to"] in ui_targets]
        own_meta["ui_helper_hits"]=ui_hits
        own_meta["classification"]="GARAGE_UI_REFRESH_OR_ACTION_ROUTER" if len(ui_hits)>=2 else "UNRESOLVED"
        print("          classification:",own_meta["classification"],"ui helper hits=",len(ui_hits),flush=True)

    print("[R8 6/9] Procurando primeiro mutation candidate ANTES do UI refresh...",flush=True)
    # If 0x009C51E0 is success-only, inspect direct call chain to ownership/UI and rank shallow non-UI functions.
    mutation=[]
    for n in relevant:
        if n["va"]==f"0x{OWN_CAR_CANDIDATE:08X}":continue
        if "ui" in n["tags"] and len(n["tags"]["ui"])>=len(sum([n["tags"].get(k,[]) for k in ("ownership","profile","blueprint","sync")],[])):
            continue
        score=0
        if n["tags"].get("ownership"):score+=20
        if n["tags"].get("profile"):score+=15
        if n["tags"].get("sync"):score+=10
        if n["tags"].get("blueprint"):score+=8
        if n["tags"].get("economy"):score+=4
        score-=n["depth"]
        mutation.append({**n,"mutation_score":score})
    mutation.sort(key=lambda x:(-x["mutation_score"],x["depth"],x["va"]))
    for x in mutation[:20]:print("          ",x["va"],"score",x["mutation_score"],"depth",x["depth"],x["strong_tags"],flush=True)

    print("[R8 7/9] Gravando ASM decisivo...",flush=True)
    dump=[CALLBACK,OWN_CAR_CANDIDATE,0x009C51E0]
    dump += [int(t,16) for _,t in success_only if is_exec(int(t,16),ib,secs)]
    dump += [int(x["va"],16) for x in mutation[:30]]
    for va in list(dict.fromkeys(dump))[:100]:
        txt=asm_dump(md,d,va,ib,secs)
        if txt:(asm/f"fn_{va:08X}.asm.txt").write_text(txt,encoding="utf-8")

    print("[R8 8/9] Gerando decision model...",flush=True)
    # runtime patch is safe to PREPARE only if there is at least one success-only call
    # and a shallow non-UI ownership/profile/sync candidate.
    top=mutation[0] if mutation else None
    can_prepare=bool(success_only and top and top["depth"]<=4 and top["mutation_score"]>=10)
    model={
      "phase":"R8",
      "callback":"0x00AA4D00",
      "status_traces":traces,
      "success_only_calls":[{"callsite":a,"target":b} for a,b in success_only],
      "common_calls":[{"callsite":a,"target":b} for a,b in common],
      "error_only_calls":[{"callsite":a,"target":b} for a,b in error_only],
      "call_0x009C51E0_status":ninec_status,
      "success_graph":{"roots":roots,"node_count":len(nodes),"edge_count":len(edges)},
      "relevant_success_nodes":relevant[:300],
      "own_car_candidate":own_meta,
      "mutation_candidates":mutation[:200],
      "decision":{
        "can_prepare_runtime_patch":can_prepare,
        "top_candidate":top,
        "reason":"requires success-only callback edge plus shallow non-UI ownership/profile/sync evidence"
      },
      "no_binary_changes":True
    }
    (out/"STATUS0_SUCCESS_SLICE.json").write_text(json.dumps(model,indent=2),encoding="utf-8")

    doc=src/"docs"/"R8-STATUS0-SUCCESS-SLICE.md"
    lines=[
      "# R8 Craft callback status=0 success slice","",
      "## Core question","",
      "Which direct calls from GS_Garage craft callback 0x00AA4D00 are reachable for normalized status 0 but not for known error codes?",
      "",
      "## Result","",
      f"- success-only calls: {len(success_only)}",
      f"- common calls: {len(common)}",
      f"- error-only calls: {len(error_only)}",
      f"- 0x009C51E0 classification: {ninec_status}",
      f"- own_car function 0x00AC9D60 classification: {own_meta.get('classification','UNRESOLVED')}",
      "",
      "## Success-only calls",""
    ]
    for a,b in success_only:lines.append("- "+a+" -> "+b)
    lines+=["","## Top mutation candidates",""]
    for x in mutation[:20]:
        lines.append("- "+x["va"]+" depth="+str(x["depth"])+" score="+str(x["mutation_score"])+" tags="+",".join(x["strong_tags"]))
    lines+=["","## Decision","",f"- can_prepare_runtime_patch = {can_prepare}"]
    doc.write_text("\n".join(lines)+"\n",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R8"
    manifest["r8_status0_slice"]="reverse/r8/STATUS0_SUCCESS_SLICE.json"
    manifest["r8_success_only_call_count"]=len(success_only)
    manifest["r8_0x009C51E0_status"]=ninec_status
    manifest["r8_own_car_classification"]=own_meta.get("classification","UNRESOLVED")
    manifest["r8_can_prepare_runtime_patch"]=can_prepare
    manifest["r8_top_mutation_candidates"]=mutation[:20]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R8 9/9] SOURCE RECONSTRUCTION R8 OK",flush=True)
    print("Success-only calls:",len(success_only),flush=True)
    print("0x009C51E0:",ninec_status,flush=True)
    print("own_car classification:",own_meta.get("classification","UNRESOLVED"),flush=True)
    if top:print("Top mutation candidate:",top["va"],"score",top["mutation_score"],flush=True)
    print("Can prepare runtime patch:",can_prepare,flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
