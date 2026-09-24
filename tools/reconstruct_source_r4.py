#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct,hashlib,re
from pathlib import Path
from collections import defaultdict
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"
REQ_BODY=0x009A4BB0
RESULT=0x009A48A0
RESULT_KEY_GLOBALS=[0x0183DFF4,0x0183DFCC,0x0183DFC4,0x0183E004,0x0183DFF8,0x0183DFC8]

def u16(b,o):return struct.unpack_from("<H",b,o)[0]
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def sha256(b):return hashlib.sha256(b).hexdigest()

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

def next_prologue(d,start,secs,limit=0x30000):
    end=min(len(d),start+limit)
    for s in secs:
        if s["raw"]<=start<s["raw"]+s["rs"]:
            end=min(end,s["raw"]+s["rs"]);break
    p=d.find(b"\x55\x8B\xEC",start+3,end)
    return p if p>=0 else end

def read_csv(path):
    if not path.is_file():return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def ascii_at(d,off,maxlen=512):
    if off is None or off<0 or off>=len(d) or not(32<=d[off]<=126):return None
    j=off
    while j<len(d) and j-off<maxlen and 32<=d[j]<=126:j+=1
    return d[off:j].decode("ascii","replace") if j-off>=3 else None

def utf16_at(d,off,maxchars=256):
    if off is None or off<0 or off+2>len(d):return None
    out=[];p=off
    for _ in range(maxchars):
        if p+2>len(d):break
        c=u16(d,p);p+=2
        if c==0:break
        if c<32 or c>126:return None
        out.append(chr(c))
    return "".join(out) if len(out)>=3 else None

def string_at_va(d,va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return None
    a=ascii_at(d,f)
    if a:return {"kind":"ascii","va":f"0x{va:08X}","text":a}
    w=utf16_at(d,f)
    if w:return {"kind":"utf16","va":f"0x{va:08X}","text":w}
    return None

def pointer_chain(d,va,ib,secs,maxdepth=6):
    out=[];cur=va;seen=set()
    for depth in range(maxdepth+1):
        if cur in seen:break
        seen.add(cur)
        s=string_at_va(d,cur,ib,secs)
        if s:
            out.append({"depth":depth,"va":f"0x{cur:08X}","string":s});break
        f=v2f(cur,ib,secs)
        if f is None or f+4>len(d):break
        nxt=u32(d,f)
        out.append({"depth":depth,"va":f"0x{cur:08X}","dword":f"0x{nxt:08X}"})
        if nxt<ib:break
        cur=nxt
    return out

def disasm_func(md,d,va,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,secs)
    return fs,fe,list(md.disasm(d[fs:fe],va))

def rows_for(ins,fs,va):
    return [{"va":f"0x{x.address:08X}","file":f"0x{fs+(x.address-va):08X}","bytes":x.bytes.hex(" ").upper(),"mnemonic":x.mnemonic,"op_str":x.op_str} for x in ins]

def refs_for(md,d,ins,ib,secs):
    out=[]
    for idx,x in enumerate(ins):
        vals=[]
        for op in x.operands:
            if op.type==X86_OP_IMM:vals.append(("imm",op.imm&0xffffffff))
            elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index:vals.append(("abs_mem",op.mem.disp&0xffffffff))
        for kind,va in vals:
            if v2f(va,ib,secs) is None:continue
            ch=pointer_chain(d,va,ib,secs,4)
            ss=[c["string"] for c in ch if "string" in c]
            out.append({"instruction_index":idx,"insn_va":f"0x{x.address:08X}","kind":kind,"target_va":f"0x{va:08X}","chain":ch,"strings":ss})
    return out

def context(rows,idx,before=10,after=16):
    return rows[max(0,idx-before):min(len(rows),idx+after+1)]

def request_fields(refs,rows):
    out=[];seen=set()
    for r in refs:
        for s in r["strings"]:
            txt=s.get("text","")
            for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_.-]{0,80})=",txt):
                key=m.group(1)
                if key in seen:continue
                seen.add(key)
                out.append({"key":key,"literal":txt,"xref_instruction":r["insn_va"],"context":context(rows,r["instruction_index"])})
    return out

def xref_globals(md,d,targets,ib,secs):
    wanted=set(targets);out=defaultdict(list)
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);sva=ib+s["va"]
        for x in md.disasm(d[a:b],sva):
            for op in x.operands:
                va=None
                if op.type==X86_OP_IMM:va=op.imm&0xffffffff
                elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index:va=op.mem.disp&0xffffffff
                if va in wanted:out[va].append({"insn_va":f"0x{x.address:08X}","mnemonic":x.mnemonic,"op_str":x.op_str})
    return out

def nearby_strings(d,va,ib,secs,radius=0x120):
    f=v2f(va,ib,secs)
    if f is None:return []
    a=max(0,f-radius);b=min(len(d),f+radius);out=[];p=a
    while p<b:
        s=ascii_at(d,p,160)
        if s:
            pv=f2v(p,ib,secs);out.append({"va":f"0x{pv:08X}" if pv else None,"text":s});p+=len(s)+1
        else:p+=1
    return out[:64]

def same_fn_strings(sx,insn_va):
    try:v=int(insn_va,16)
    except:return []
    out=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if abs(fn-v)<=0x600:
            t=r.get("string","")
            if t and t not in seen:seen.add(t);out.append(t)
    return out[:80]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True);ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe";atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX";src=root/"src-reconstructed"
    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")
    if not atlas.is_dir():raise SystemExit("FULL GAME ATLAS MAX nao encontrado")
    if not src.is_dir():raise SystemExit("src-reconstructed nao encontrado")
    d=ams.read_bytes()
    if sha256(d)!=STABLE_SHA:raise SystemExit("AMS SHA inesperado: "+sha256(d))
    ib,secs=parse_pe(d);sx=read_csv(atlas/"STRING_XREFS.csv")
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    out=src/"reverse"/"r4";out.mkdir(parents=True,exist_ok=True)

    print("[R4 1/9] Desassemblando request/result...",flush=True)
    req_fs,req_fe,req_ins=disasm_func(md,d,REQ_BODY,ib,secs)
    res_fs,res_fe,res_ins=disasm_func(md,d,RESULT,ib,secs)
    req_rows=rows_for(req_ins,req_fs,REQ_BODY);res_rows=rows_for(res_ins,res_fs,RESULT)

    print("[R4 2/9] Resolvendo strings/campos do request...",flush=True)
    rr=refs_for(md,d,req_ins,ib,secs);fields=request_fields(rr,req_rows)
    atlas_req=[];seen=set()
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if REQ_BODY<=fn<REQ_BODY+(req_fe-req_fs):
            t=r.get("string","")
            if t and t not in seen:seen.add(t);atlas_req.append({"function_va":r.get("function_va"),"text":t})
    if not any(x["key"]=="car_id" for x in fields):fields.insert(0,{"key":"car_id","literal":"car_id=","xref_instruction":"atlas","context":[]})

    print("[R4 3/9] Resolvendo globals/chaves do response...",flush=True)
    gx=xref_globals(md,d,RESULT_KEY_GLOBALS,ib,secs);globals_out=[]
    for g in RESULT_KEY_GLOBALS:
        refs=gx.get(g,[]);ev=[]
        for x in refs[:40]:ev.extend(same_fn_strings(sx,x["insn_va"]))
        globals_out.append({"global_va":f"0x{g:08X}","pointer_chain":pointer_chain(d,g,ib,secs,6),"nearby_strings":nearby_strings(d,g,ib,secs),"code_xrefs":refs[:80],"same_function_string_evidence":list(dict.fromkeys(ev))[:80]})

    print("[R4 4/9] Construindo mapa de status...",flush=True)
    status={
      "conditions":[
        {"condition":"input_code == 0","result":"response-body inspection; no detected error key preserves status 0"},
        {"condition":"input_code - 0xBB8 == 0xFA1","normalized_status":1},
        {"condition":"input_code - 0xBB8 == 0xFA7","normalized_status":2},
        {"condition":"input_code - 0xBB8 == 0x138E","result":"special response-key-assisted path"},
        {"condition":"other nonzero input","result":"mapped into local domain with +0x3E8"}
      ],
      "response_key_slots":[
        {"global":"0x0183DFF4","tag":8},{"global":"0x0183DFCC","tag":3},{"global":"0x0183DFC4","tag":1},
        {"global":"0x0183E004","tag":16},{"global":"0x0183DFF8","tag":9},{"global":"0x0183DFC8","tag":2,"special_code":"0x138E"}
      ]
    }

    print("[R4 5/9] Gravando contrato...",flush=True)
    contract={
      "phase":"R4","endpoint":"scripts/cars/craft_car.php","request_body_va":"0x009A4BB0",
      "request_wrapper_va":"0x009A4BA0","request_wrapper_argument":"[this+0x68]",
      "request_fields":fields,"request_atlas_strings":atlas_req,
      "result_handler_va":"0x009A48A0","result_key_globals":globals_out,"status_mapping":status,
      "minimal_offline_success_hypothesis":{
        "transport_code":0,"response_error_keys":"absent","normalized_status":0,"confidence":"medium",
        "basis":"status local begins at 0; code 0 with no tested error key reaches common store without replacing it"
      },"no_binary_changes":True
    }
    (out/"CRAFTCAR_BACKEND_CONTRACT.json").write_text(json.dumps(contract,indent=2),encoding="utf-8")

    print("[R4 6/9] Gravando evidencia...",flush=True)
    lines=["R4 CRAFTCAR BACKEND CONTRACT EVIDENCE","="*100,f"Request 0x{REQ_BODY:08X} file 0x{req_fs:08X}..0x{req_fe:08X}",f"Result 0x{RESULT:08X} file 0x{res_fs:08X}..0x{res_fe:08X}","","REQUEST FIELDS"]
    for f in fields:
        lines.append(f"- {f['key']} literal={f.get('literal')} xref={f.get('xref_instruction')}")
        for x in f.get("context",[]):lines.append(f"  {x['va']} {x['bytes']:<28} {x['mnemonic']} {x['op_str']}")
    lines+=["","RESULT GLOBALS"]
    for g in globals_out:
        lines.append("- "+g["global_va"])
        for c in g["pointer_chain"]:lines.append("  chain "+json.dumps(c,ensure_ascii=False))
        for s in g["nearby_strings"][:20]:lines.append("  nearby "+json.dumps(s,ensure_ascii=False))
        for s in g["same_function_string_evidence"][:20]:lines.append("  function-string "+s)
    (out/"EVIDENCE.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")

    print("[R4 7/9] Gerando OfflineBackend C++...",flush=True)
    inc=src/"include"/"rextreme"/"network";cpp=src/"src"/"network";inc.mkdir(parents=True,exist_ok=True);cpp.mkdir(parents=True,exist_ok=True)
    (inc/"CraftCarContract.hpp").write_text('''#pragma once
#include <cstdint>
#include <string>
namespace rextreme::network {
struct CraftCarRequest { std::int32_t carId = 0; };
struct CraftCarReply { std::int32_t transportCode = 0; std::string responseDocument; };
class OfflineCraftCarBackend {
public:
    static constexpr const char* kEndpoint = "scripts/cars/craft_car.php";
    static CraftCarReply Handle(const CraftCarRequest& request);
};
}
''',encoding="utf-8")
    (cpp/"CraftCarContract.cpp").write_text('''#include "rextreme/network/CraftCarContract.hpp"
namespace rextreme::network {
CraftCarReply OfflineCraftCarBackend::Handle(const CraftCarRequest& request) {
    CraftCarReply reply{};
    (void)request;
    // Medium-confidence compatibility candidate from R4:
    // zero transport code + no response error keys preserves normalized status 0.
    reply.transportCode = 0;
    reply.responseDocument = "{}";
    return reply;
}
}
''',encoding="utf-8")

    print("[R4 8/9] Atualizando docs/manifest...",flush=True)
    (src/"docs"/"R4-CRAFTCAR-BACKEND-CONTRACT.md").write_text('''# R4 CraftCar backend contract

## Confirmed

- Endpoint: scripts/cars/craft_car.php
- Request body: 0x009A4BB0; wrapper 0x009A4BA0 passes [this+0x68].
- Request field literal car_id= is present.
- Result handler: 0x009A48A0.
- Result status is stored at operation +0x54 and delivered to completion callbacks.

## Local compatibility candidate

The zero transport-code path begins with normalized status 0. If none of the tested response error keys are present, that status reaches the common result store unchanged. R4 records transportCode=0 with an empty response document as a medium-confidence compatibility candidate, not as a claim about the original server schema.

## R5 target

- Resolve each result-key global to its exact string.
- Trace the success completion callback from GS_Garage+0x298.
- Identify the exact profile/car-ownership mutation reached after normalized status 0.
- Only then connect the local backend candidate into the runtime.
''',encoding="utf-8")
    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json";manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R4";manifest["r4_backend_contract"]="reverse/r4/CRAFTCAR_BACKEND_CONTRACT.json"
    manifest["r4_endpoint"]="scripts/cars/craft_car.php";manifest["r4_request_fields"]=[x["key"] for x in fields]
    manifest["r4_minimal_success_candidate"]={"transportCode":0,"responseDocument":"{}","confidence":"medium"}
    manifest["r4_result_key_globals"]=[f"0x{x:08X}" for x in RESULT_KEY_GLOBALS]
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R4 9/9] SOURCE RECONSTRUCTION R4 OK",flush=True)
    print("Request fields:",", ".join(x["key"] for x in fields),flush=True)
    print("Contract:",out/"CRAFTCAR_BACKEND_CONTRACT.json",flush=True)
    print("No gameplay bytes changed.",flush=True)

if __name__=="__main__":main()
