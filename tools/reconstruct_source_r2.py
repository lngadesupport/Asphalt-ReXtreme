#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, struct, hashlib
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

TARGETS={
    "GarageBottomBarWidget_RegisterButtons":0x00972B90,
    "GarageBottomBarWidget_OnBuildPressed":0x00973C90,
    "GS_Garage_BuildCar":0x00A87960,
    "CraftCar_Caller":0x0099FF50,
    "CraftCar_Request":0x009A4BA0,
    "CraftCar_Result":0x009A48A0,
    "SignalInvokeHelper":0x00936BE0,
    "RegisterHelper":0x0096E4B0,
}

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def sha(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); optsz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+optsz
    secs=[]
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
            return s["raw"]+(rva-s["va"])
    return None

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def next_prologue(d,start,secs,limit=0x20000):
    end=min(len(d),start+limit)
    for s in secs:
        if s["raw"]<=start<s["raw"]+s["rs"]:
            end=min(end,s["raw"]+s["rs"])
            break
    p=d.find(b"\x55\x8B\xEC",start+3,end)
    return p if p>=0 else end

def read_csv(path):
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def shards_in(rows,a,b):
    out=[]
    for r in rows:
        try:fs=int(r.get("file_start",""),16)
        except:continue
        if a<=fs<b:
            out.append({
                "va":r.get("va"),"file_start":r.get("file_start"),
                "file_end":r.get("file_end"),"size":r.get("size"),
                "known_name":r.get("known_name","")
            })
    out.sort(key=lambda x:int(x["file_start"],16))
    return out

def disasm(md,d,a,b,va):
    ins=[];calls=[];jmps=[];pair=[]
    for x in md.disasm(d[a:b],va):
        file_off=a+(x.address-va)
        row={
            "address":f"0x{x.address:08X}",
            "file":f"0x{file_off:08X}",
            "bytes":x.bytes.hex(" ").upper(),
            "mnemonic":x.mnemonic,
            "op_str":x.op_str
        }
        ins.append(row)
        if x.mnemonic=="call":
            try:
                if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                    calls.append({"from":row["address"],"file":row["file"],"to":f"0x{x.operands[0].imm & 0xffffffff:08X}"})
            except:pass
        if x.mnemonic.startswith("j"):
            try:
                if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                    jmps.append({"from":row["address"],"to":f"0x{x.operands[0].imm & 0xffffffff:08X}","kind":x.mnemonic})
            except:pass
        lo=x.op_str.lower()
        if "0x44" in lo or "0x48" in lo:
            pair.append(row)
    return ins,calls,jmps,pair

def render_asm(name,m):
    out=[
        "; "+name,
        "; VA "+m["va"],
        "; FILE "+m["file_start"]+".."+m["file_end"],
        "; SIZE "+str(m["size"]),
        "; ATLAS SHARDS "+str(len(m["atlas_shards"])),
        ""
    ]
    for x in m["instructions"]:
        out.append(f'{x["address"]}  {x["bytes"]:<30}  {x["mnemonic"]} {x["op_str"]}'.rstrip())
    return "\n".join(out)+"\n"

def cpp_calls(m):
    if not m["calls"]:return "    // no direct calls decoded\n"
    return "".join(f'    // {x["from"]} -> {x["to"]}\n' for x in m["calls"])

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
    if not src.is_dir():raise SystemExit("src-reconstructed nao encontrado; execute R1 primeiro")

    d=ams.read_bytes()
    if sha(d)!=STABLE_SHA:raise SystemExit("AMS SHA inesperado: "+sha(d))
    ib,secs=parse_pe(d)
    rows=read_csv(atlas/"FUNCTIONS.csv")

    md=Cs(CS_ARCH_X86,CS_MODE_32)
    md.detail=True

    out=src/"reverse"/"r2"
    asm_dir=out/"asm"
    asm_dir.mkdir(parents=True,exist_ok=True)

    print("[R2 1/7] Reagrupando shards...",flush=True)
    logical={}
    for name,va in TARGETS.items():
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,secs)
        ins,calls,jmps,pair=disasm(md,d,fs,fe,va)
        logical[name]={
            "name":name,"va":f"0x{va:08X}",
            "file_start":f"0x{fs:08X}","file_end":f"0x{fe:08X}",
            "size":fe-fs,"atlas_shards":shards_in(rows,fs,fe),
            "calls":calls,"jumps":jmps,"build_pair_refs":pair,
            "instructions":ins
        }
        (asm_dir/(name+".asm.txt")).write_text(render_asm(name,logical[name]),encoding="utf-8")
        print(f"          {name}: {fe-fs} bytes, shards={len(logical[name]['atlas_shards'])}, calls={len(calls)}",flush=True)

    print("[R2 2/7] Reconstruindo cadeia conhecida...",flush=True)
    known={f"0x{x:08X}" for x in TARGETS.values()}
    chain=[]
    for name,m in logical.items():
        for c in m["calls"]:
            if c["to"] in known:
                chain.append({"source":name,**c})

    print("[R2 3/7] Gerando C++ de garagem...",flush=True)
    garage=src/"src"/"game"/"garage"
    garage.mkdir(parents=True,exist_ok=True)

    reg=logical["GarageBottomBarWidget_RegisterButtons"]
    cb=logical["GarageBottomBarWidget_OnBuildPressed"]
    gs=logical["GS_Garage_BuildCar"]
    req=logical["CraftCar_Request"]
    res=logical["CraftCar_Result"]

    gbbw_cpp=(
        '#include "rextreme/game/garage/GarageBottomBarWidget.hpp"\n\n'
        'namespace rextreme::game::garage {\n\n'
        '// Original logical VA 0x00972B90.\n'
        '// UI registration includes build_button and routes delegates through RegisterHelper 0x0096E4B0.\n'
        'void GarageBottomBarWidget::RegisterButtons() {\n'
        + cpp_calls(reg) +
        '}\n\n'
        '// Original VA 0x00973C90.\n'
        '// Verified: read buildSignal.object at +0x44; null returns; otherwise dispatch via 0x00936BE0.\n'
        'void GarageBottomBarWidget::OnBuildPressed() {\n'
        '    if (buildSignal.object == nullptr) return;\n'
        '    // Signal internals remain opaque in R2.\n'
        '}\n\n'
        '} // namespace rextreme::game::garage\n'
    )
    (garage/"GarageBottomBarWidget.cpp").write_text(gbbw_cpp,encoding="utf-8")

    gs_cpp=(
        '#include "rextreme/game/garage/GS_Garage.hpp"\n\n'
        'namespace rextreme::game::garage {\n\n'
        '// Original logical VA 0x00A87960.\n'
        '// Atlas shards are merged before this reconstruction.\n'
        'void GS_Garage::BuildCar() {\n'
        + cpp_calls(gs) +
        '    // R3 will type the state guards and translate branch semantics.\n'
        '}\n\n'
        '} // namespace rextreme::game::garage\n'
    )
    (garage/"GS_Garage.cpp").write_text(gs_cpp,encoding="utf-8")

    craft_cpp=(
        '#include "rextreme/game/garage/CraftCar.hpp"\n\n'
        'namespace rextreme::game::garage {\n\n'
        '// Original logical VA 0x009A4BA0.\n'
        '// Recovered endpoint: scripts/cars/craft_car.php\n'
        'void CraftCarService::RequestCraft() {\n'
        + cpp_calls(req) +
        '    // R3 will type request payload and completion callback.\n'
        '}\n\n'
        '// Original logical VA 0x009A48A0.\n'
        'void CraftCarService::HandleResult() {\n'
        + cpp_calls(res) +
        '    // R3 will reconstruct exact profile/inventory mutations.\n'
        '}\n\n'
        '} // namespace rextreme::game::garage\n'
    )
    (garage/"CraftCar.cpp").write_text(craft_cpp,encoding="utf-8")

    print("[R2 4/7] Gerando manifests...",flush=True)
    compact={}
    for name,m in logical.items():
        compact[name]={k:v for k,v in m.items() if k!="instructions"}
    (out/"LOGICAL_FUNCTIONS.json").write_text(json.dumps(compact,indent=2),encoding="utf-8")
    (out/"GARAGE_CHAIN.json").write_text(json.dumps(chain,indent=2),encoding="utf-8")

    print("[R2 5/7] Gerando relatorio...",flush=True)
    lines=["# R2 Garage/CraftCar reconstruction","", "## Logical functions"]
    for name,m in logical.items():
        lines.append("- "+name+" "+m["va"]+" file "+m["file_start"]+".."+m["file_end"]+
                     " size "+str(m["size"])+" bytes; shards merged "+str(len(m["atlas_shards"]))+
                     "; decoded calls "+str(len(m["calls"])))
    lines+=["","## Known direct chain edges"]
    for x in chain:
        lines.append("- "+x["source"]+" "+x["from"]+" -> "+x["to"])
    lines+=["","## Confirmed endpoint","- CraftCar_Request: scripts/cars/craft_car.php",
            "","## R3 targets",
            "- Type GS_Garage::BuildCar fields and branches.",
            "- Type CraftCar request payload and callback.",
            "- Reconstruct CraftCar result mutations.",
            "- Connect buildSignal to local BuildCar path."]
    (src/"docs"/"R2-GARAGE-CRAFT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    print("[R2 6/7] Atualizando manifest R1 -> R2...",flush=True)
    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R2"
    manifest["r2_logical_functions"]={
        k:{
            "va":v["va"],"file_start":v["file_start"],"file_end":v["file_end"],
            "size":v["size"],"atlas_shards_merged":len(v["atlas_shards"]),
            "decoded_calls":len(v["calls"])
        } for k,v in logical.items()
    }
    manifest["r2_known_chain_edges"]=len(chain)
    manifest["r2_confirmed_endpoint"]="scripts/cars/craft_car.php"
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R2 7/7] SOURCE RECONSTRUCTION R2 OK",flush=True)
    print("Logical functions:",len(logical),flush=True)
    print("Known chain edges:",len(chain),flush=True)
    print("Output:",out,flush=True)

if __name__=="__main__":
    main()
