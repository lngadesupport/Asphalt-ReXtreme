#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct,hashlib
from pathlib import Path
from collections import deque,defaultdict

from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

ROOTS={
    "SuccessRoot_ProfileA":0x00F6F320,
    "SuccessRoot_ProfileB":0x00F74EA0,
}
SAFE_PROFILE=0x00C1E2E0
CALLBACK=0x00AA4D00

MUTATION_WORDS=(
    "own_car","owned","ownership","unlock","blueprint","bp_","inventory",
    "profile","save","serialize","sync","credits","hardcurrency","server_items",
    "car_id","vehicle","garage","purchase","buy_a_car"
)

UI_WORDS=("button","widget","template","label_","movie_","container","bcn_")

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
    if x.mnemonic not in ("call","jmp"):return None
    if len(x.operands)!=1 or x.operands[0].type!=X86_OP_IMM:return None
    return x.operands[0].imm&0xffffffff

def insrow(x):
    return {"va":f"0x{x.address:08X}","bytes":x.bytes.hex(" ").upper(),"mnemonic":x.mnemonic,"op_str":x.op_str}

def strings_near(sx,va,radius=0x280):
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
    out={"mutation":[],"ui":[]}
    for s in ss:
        lo=s.lower()
        if any(w in lo for w in MUTATION_WORDS):out["mutation"].append(s)
        if any(w in lo for w in UI_WORDS):out["ui"].append(s)
    return {k:list(dict.fromkeys(v)) for k,v in out.items()}

def direct_calls(ins):
    out=[]
    for x in ins:
        if x.mnemonic=="call":
            dst=direct_target(x)
            if dst is not None:out.append({"from":f"0x{x.address:08X}","to":f"0x{dst:08X}"})
    return out

def memory_writes(md,ins):
    out=[]
    for x in ins:
        if not x.operands:continue
        dst=x.operands[0]
        if dst.type!=X86_OP_MEM:continue
        if x.mnemonic not in ("mov","add","sub","inc","dec","and","or","xor","xchg"):continue
        m=dst.mem
        base=md.reg_name(m.base) if m.base else ""
        index=md.reg_name(m.index) if m.index else ""
        out.append({
            "va":f"0x{x.address:08X}",
            "insn":x.mnemonic+" "+x.op_str,
            "base":base,"index":index,"disp":m.disp,
            "absolute":(not m.base and not m.index)
        })
    return out

def global_writes(md,ins):
    return [w for w in memory_writes(md,ins) if w["absolute"]]

def object_writes(md,ins):
    return [w for w in memory_writes(md,ins) if not w["absolute"] and w["base"] not in ("esp","ebp","")]

def classify_func(md,d,va,ib,secs,sx):
    fx=func(md,d,va,ib,secs)
    if not fx:return None
    fs,fe,ins=fx
    ss=strings_near(sx,va)
    cls=classify_strings(ss)
    calls=direct_calls(ins)
    gw=global_writes(md,ins)
    ow=object_writes(md,ins)
    # semantic score favors actual non-stack writes plus mutation strings, penalizes UI-heavy.
    score=len(gw)*8+len(ow)*3+len(cls["mutation"])*5-len(cls["ui"])*2
    return {
        "va":f"0x{va:08X}",
        "file_start":f"0x{fs:08X}","file_end":f"0x{fe:08X}","size":fe-fs,
        "strings":ss,"classification":cls,"calls":calls,
        "global_writes":gw,"object_writes":ow,"effect_score":score
    }

def graph(md,d,ib,secs,sx,roots,max_depth=6,max_nodes=5000):
    q=deque((name,va,0,[f"{name}:0x{va:08X}"]) for name,va in roots.items())
    seen=set();nodes=[];edges=[]
    while q and len(seen)<max_nodes:
        name,va,depth,path=q.popleft()
        key=(name,va)
        if key in seen or depth>max_depth or not is_exec(va,ib,secs):continue
        seen.add(key)
        meta=classify_func(md,d,va,ib,secs,sx)
        if not meta:continue
        meta["root"]=name;meta["depth"]=depth;meta["path"]=path
        nodes.append(meta)
        for c in meta["calls"]:
            dst=int(c["to"],16)
            edges.append({"root":name,"src":meta["va"],**c})
            if depth<max_depth and is_exec(dst,ib,secs):
                q.append((name,dst,depth+1,path+[c["to"]]))
    return nodes,edges

def caller_xrefs(md,d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);sva=ib+s["va"]
        for x in md.disasm(d[a:b],sva):
            if x.mnemonic!="call" or len(x.operands)!=1 or x.operands[0].type!=X86_OP_IMM:continue
            if (x.operands[0].imm&0xffffffff)==target:
                out.append({"callsite":f"0x{x.address:08X}","target":f"0x{target:08X}"})
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
    out=src/"reverse"/"r9";asm=out/"asm";asm.mkdir(parents=True,exist_ok=True)

    print("[R9 1/9] Classificando SafeProfileRunning 0x00C1E2E0...",flush=True)
    safe=classify_func(md,d,SAFE_PROFILE,ib,secs,sx)
    safe["call_xrefs"]=caller_xrefs(md,d,SAFE_PROFILE,ib,secs)
    if safe["size"]<=0x20 and not safe["calls"] and not safe["global_writes"] and not safe["object_writes"]:
        safe["semantic_class"]="PROFILE_STATE_GETTER_OR_FLAG"
    else:
        safe["semantic_class"]="UNRESOLVED"
    print("          size=",safe["size"],"class=",safe["semantic_class"],flush=True)

    print("[R9 2/9] Classificando success roots...",flush=True)
    root_meta={}
    for name,va in ROOTS.items():
        m=classify_func(md,d,va,ib,secs,sx)
        root_meta[name]=m
        print(f"          {name} 0x{va:08X}: size={m['size']} calls={len(m['calls'])} objWrites={len(m['object_writes'])} globalWrites={len(m['global_writes'])}",flush=True)

    print("[R9 3/9] Construindo effect graph...",flush=True)
    nodes,edges=graph(md,d,ib,secs,sx,ROOTS,7,6500)
    print("          nodes=",len(nodes),"edges=",len(edges),flush=True)

    print("[R9 4/9] Separando funcoes com WRITE real...",flush=True)
    write_nodes=[]
    for n in nodes:
        if n["global_writes"] or n["object_writes"]:
            mut=len(n["classification"]["mutation"])
            ui=len(n["classification"]["ui"])
            # Add path-depth pressure: near success roots is better.
            score=n["effect_score"]+mut*6-ui*2-n["depth"]
            write_nodes.append({**n,"rank_score":score})
    write_nodes.sort(key=lambda x:(-x["rank_score"],x["depth"],x["va"]))
    for n in write_nodes[:25]:
        print(f"          {n['va']} depth={n['depth']} score={n['rank_score']} writes={len(n['global_writes'])+len(n['object_writes'])} mutationStrings={len(n['classification']['mutation'])}",flush=True)

    print("[R9 5/9] Isolando candidatos ownership/profile/save...",flush=True)
    decisive=[]
    for n in write_nodes:
        ss=" ".join(n["classification"]["mutation"]).lower()
        why=[]
        if "own_car" in ss or "owned" in ss or "ownership" in ss or "unlock" in ss:why.append("ownership")
        if "profile" in ss or "save" in ss or "serialize" in ss:why.append("profile/persistence")
        if "blueprint" in ss or "bp_" in ss:why.append("blueprint")
        if "inventory" in ss or "sync" in ss or "server_items" in ss:why.append("sync")
        if why:
            decisive.append({**n,"why_effect":why})
    decisive.sort(key=lambda x:(x["depth"],-x["rank_score"],x["va"]))
    for n in decisive[:20]:
        print("          ",n["va"],"depth",n["depth"],"score",n["rank_score"],n["why_effect"],flush=True)

    print("[R9 6/9] Verificando se own_car e UI-only...",flush=True)
    own=[n for n in nodes if n["va"]=="0x00AC9D60"]
    own=own[0] if own else None
    own_class="NOT_IN_SUCCESS_ROOT_GRAPH"
    if own:
        ui=len(own["classification"]["ui"]);mut=len(own["classification"]["mutation"])
        writes=len(own["global_writes"])+len(own["object_writes"])
        own_class="UI_REFRESH_WITH_SIDE_EFFECTS" if writes and mut else ("UI_REFRESH" if ui else "UNRESOLVED")
    print("          own_car:",own_class,flush=True)

    print("[R9 7/9] Gravando ASM dos candidatos...",flush=True)
    dump=[SAFE_PROFILE,*ROOTS.values(),CALLBACK]
    dump += [int(n["va"],16) for n in decisive[:30]]
    dump += [int(n["va"],16) for n in write_nodes[:20]]
    for va in list(dict.fromkeys(dump))[:100]:
        txt=asm_dump(md,d,va,ib,secs)
        if txt:(asm/f"fn_{va:08X}.asm.txt").write_text(txt,encoding="utf-8")

    print("[R9 8/9] Decidindo patch strategy...",flush=True)
    top=decisive[0] if decisive else None
    # We only allow direct mutation patch preparation if a shallow (<4) writer exists.
    # Otherwise prefer callback injection into already verified success-only branch.
    direct_ready=bool(top and top["depth"]<=3 and top["rank_score"]>=12)
    injection_ready=True  # R8 already proved success-only callsites in callback.
    strategy="PATCH_EXISTING_MUTATION" if direct_ready else "INJECT_AT_VERIFIED_SUCCESS_BRANCH"

    model={
      "phase":"R9",
      "safe_profile":safe,
      "success_roots":root_meta,
      "effect_graph":{"node_count":len(nodes),"edge_count":len(edges)},
      "write_candidates":write_nodes[:300],
      "decisive_candidates":decisive[:200],
      "own_car_classification":own_class,
      "decision":{
        "direct_mutation_patch_ready":direct_ready,
        "success_branch_injection_ready":injection_ready,
        "recommended_strategy":strategy,
        "top_decisive_candidate":top,
        "note":"R9 changes no gameplay bytes."
      }
    }
    (out/"SUCCESS_EFFECT_WRITES.json").write_text(json.dumps(model,indent=2),encoding="utf-8")

    doc=src/"docs"/"R9-SUCCESS-EFFECT-WRITES.md"
    lines=[
      "# R9 Success-path effect writers","",
      "## SafeProfileRunning","",
      f"- 0x00C1E2E0 size: {safe['size']} bytes.",
      f"- classification: {safe['semantic_class']}.",
      f"- calls: {len(safe['calls'])}; object writes: {len(safe['object_writes'])}; global writes: {len(safe['global_writes'])}.",
      "",
      "## Verified success roots",""
    ]
    for name,m in root_meta.items():
        lines.append(f"- {name} {m['va']} size={m['size']} calls={len(m['calls'])} objectWrites={len(m['object_writes'])} globalWrites={len(m['global_writes'])}")
    lines+=["","## Top decisive write candidates",""]
    for n in decisive[:20]:
        lines.append("- "+n["va"]+" depth="+str(n["depth"])+" score="+str(n["rank_score"])+" why="+",".join(n["why_effect"]))
    lines+=["","## Decision","",f"- recommended_strategy = {strategy}",
            f"- direct_mutation_patch_ready = {direct_ready}",
            f"- success_branch_injection_ready = {injection_ready}"]
    doc.write_text("\n".join(lines)+"\n",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R9"
    manifest["r9_success_effect_writes"]="reverse/r9/SUCCESS_EFFECT_WRITES.json"
    manifest["r9_safe_profile_classification"]=safe["semantic_class"]
    manifest["r9_own_car_classification"]=own_class
    manifest["r9_direct_mutation_patch_ready"]=direct_ready
    manifest["r9_success_branch_injection_ready"]=injection_ready
    manifest["r9_recommended_strategy"]=strategy
    manifest["r9_top_decisive_candidates"]=decisive[:20]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R9 9/9] SOURCE RECONSTRUCTION R9 OK",flush=True)
    print("SafeProfile:",safe["semantic_class"],flush=True)
    print("own_car:",own_class,flush=True)
    print("Direct mutation patch ready:",direct_ready,flush=True)
    print("Success branch injection ready:",injection_ready,flush=True)
    print("Recommended strategy:",strategy,flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
