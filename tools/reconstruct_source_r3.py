#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, struct, hashlib, re
from pathlib import Path
from collections import defaultdict

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

VA_BUILD=0x00A87960
VA_CALLER=0x0099FF50
VA_REQ_WRAPPER=0x009A4BA0
VA_REQ_BODY=0x009A4BB0
VA_RESULT=0x009A48A0

PHASE54_FILE=0x0059F3F2
PHASE54_CURRENT=bytes.fromhex("B8 02 00 00 00 90")
PHASE54_ORIGINAL=bytes.fromhex("8B 86 F8 00 00 00")

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

def next_prologue(d,start,secs,limit=0x30000):
    end=min(len(d),start+limit)
    for s in secs:
        if s["raw"]<=start<s["raw"]+s["rs"]:
            end=min(end,s["raw"]+s["rs"])
            break
    p=d.find(b"\x55\x8B\xEC",start+3,end)
    return p if p>=0 else end

def read_csv(path):
    if not path.is_file(): return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def disasm_range(md,d,va,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None: return None
    fe=next_prologue(d,fs,secs)
    ins=list(md.disasm(d[fs:fe],va))
    return fs,fe,ins

def fmt_ins(ins,fs,va):
    rows=[]
    for x in ins:
        rows.append({
            "va":f"0x{x.address:08X}",
            "file":f"0x{fs+(x.address-va):08X}",
            "bytes":x.bytes.hex(" ").upper(),
            "mnemonic":x.mnemonic,
            "op_str":x.op_str
        })
    return rows

def direct_calls(ins):
    out=[]
    for x in ins:
        if x.mnemonic!="call": continue
        try:
            if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                out.append((x.address,x.operands[0].imm & 0xffffffff))
        except: pass
    return out

def field_accesses(md,ins,this_reg_name):
    out=[]
    for x in ins:
        for idx,op in enumerate(x.operands):
            if op.type!=X86_OP_MEM: continue
            base=md.reg_name(op.mem.base) if op.mem.base else ""
            if base!=this_reg_name: continue
            disp=op.mem.disp
            if disp<0 or disp>0x800: continue
            kind="READ"
            if x.mnemonic.startswith("mov") and idx==0:
                kind="WRITE"
            elif x.mnemonic in ("inc","dec","add","sub","and","or","xor") and idx==0:
                kind="READ_WRITE"
            out.append({
                "va":f"0x{x.address:08X}",
                "field":f"0x{disp:X}",
                "kind":kind,
                "insn":x.mnemonic+" "+x.op_str
            })
    return out

def string_evidence(atlas,target_start,target_end):
    sx=read_csv(atlas/"STRING_XREFS.csv")
    out=[]
    for r in sx:
        try:fn=int(r.get("function_va",""),16)
        except:continue
        if target_start<=fn<target_end:
            txt=r.get("string","")
            if txt and txt not in [x["text"] for x in out]:
                out.append({"function_va":r.get("function_va"),"text":txt})
    return out

def write_asm(path,name,va,fs,fe,rows):
    lines=[
        "; R3 "+name,
        f"; VA 0x{va:08X}",
        f"; FILE 0x{fs:08X}..0x{fe:08X}",
        f"; SIZE {fe-fs}",
        ""
    ]
    for x in rows:
        lines.append(f'{x["va"]}  {x["bytes"]:<30}  {x["mnemonic"]} {x["op_str"]}'.rstrip())
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX"
    src=root/"src-reconstructed"
    if not ams.is_file(): raise SystemExit("AMS.exe nao encontrado")
    if not atlas.is_dir(): raise SystemExit("FULL GAME ATLAS MAX nao encontrado")
    if not src.is_dir(): raise SystemExit("src-reconstructed nao encontrado")

    d=ams.read_bytes()
    if sha(d)!=STABLE_SHA: raise SystemExit("AMS SHA inesperado: "+sha(d))
    ib,secs=parse_pe(d)

    md=Cs(CS_ARCH_X86,CS_MODE_32)
    md.detail=True

    out=src/"reverse"/"r3"
    asm_dir=out/"asm"
    asm_dir.mkdir(parents=True,exist_ok=True)

    print("[R3 1/8] Desassemblando corpos logicos...",flush=True)
    specs={
        "GS_Garage_BuildCar":(VA_BUILD,"ebx"),
        "CraftCar_Caller":(VA_CALLER,"esi"),
        "CraftCar_RequestWrapper":(VA_REQ_WRAPPER,"ecx"),
        "CraftCar_RequestBody":(VA_REQ_BODY,""),
        "CraftCar_Result":(VA_RESULT,"edi"),
    }
    metas={}
    for name,(va,thisreg) in specs.items():
        x=disasm_range(md,d,va,ib,secs)
        if x is None: continue
        fs,fe,ins=x
        rows=fmt_ins(ins,fs,va)
        write_asm(asm_dir/(name+".asm.txt"),name,va,fs,fe,rows)
        metas[name]={
            "va":f"0x{va:08X}",
            "file_start":f"0x{fs:08X}",
            "file_end":f"0x{fe:08X}",
            "size":fe-fs,
            "calls":[{"from":f"0x{a:08X}","to":f"0x{b:08X}"} for a,b in direct_calls(ins)],
            "fields":field_accesses(md,ins,thisreg) if thisreg else [],
            "strings":string_evidence(atlas,va,fe-fs+va),
        }
        print(f"          {name}: {fe-fs} bytes calls={len(metas[name]['calls'])} fields={len(metas[name]['fields'])}",flush=True)

    print("[R3 2/8] Validando override Campaign Edition...",flush=True)
    phase54_current=d[PHASE54_FILE:PHASE54_FILE+6]
    phase54_state="CURRENT_FORCE_STATE_2" if phase54_current==PHASE54_CURRENT else "UNEXPECTED"
    overrides={
        "CraftCarCaller_state_guard":{
            "file":"0x0059F3F2",
            "current_bytes":phase54_current.hex(" ").upper(),
            "current_semantics":"EAX = 2",
            "original_bytes":PHASE54_ORIGINAL.hex(" ").upper(),
            "original_semantics":"EAX = *(this + 0xF8)",
            "status":phase54_state
        }
    }

    print("[R3 3/8] Construindo modelo semantico...",flush=True)
    semantic={
        "GS_Garage":{
            "this_register":"EBX",
            "fields":{
                "0x298":"address registered into active build operation callback/listener list",
                "0x2D4":"object dereferenced before helper 0xD805F0",
                "0x35C":"GarageBottomBarWidget pointer",
                "0x3AC":"active build operation object",
                "0x3B0":"active build operation control/refcount"
            },
            "flow":[
                "checks GlobalIsOnline through 0x00FAD9D0",
                "prepares build inputs and selected vehicle data",
                "calls CraftCar_Caller 0x0099FF50",
                "moves returned shared operation into +0x3AC/+0x3B0",
                "registers &this+0x298 with operation when absent",
                "gets build button from bottomBar +0x35C and calls virtual +0x7C(false)",
                "calls GS_Garage virtual +0x54 near completion"
            ]
        },
        "CraftCar_Caller":{
            "this_register":"ESI",
            "guards":[
                "this+0x70 == 0","this+0x80 == 0","this+0x90 == 0",
                "this+0xA0 == 0","this+0xB0 == 0","this+0xC0 == 0",
                "helper 0x0099E0A0 returns false",
                "state must equal 2"
            ],
            "original_state_field":"0xF8",
            "campaign_override":"Phase54 forces state=2 before comparisons",
            "request_source":"shared object at this+0x90; request context uses object+0x40",
            "calls_wrapper":"0x009A4BA0"
        },
        "CraftCar_Request":{
            "wrapper":"0x009A4BA0 pushes [ecx+0x68] then calls 0x009A4BB0",
            "body":"0x009A4BB0",
            "endpoint":"scripts/cars/craft_car.php"
        },
        "CraftCar_Result":{
            "this_register":"EDI",
            "fields":{
                "0x24/0x28":"shared context copied into callback dispatch",
                "0x44/0x48":"vector begin/end of completion callback pointers",
                "0x50":"deferred compaction flag",
                "0x51":"currently notifying callbacks flag",
                "0x54":"normalized result/status code",
                "0x60":"object passed to helper 0x009A4440"
            },
            "flow":[
                "normalizes transport/backend result into local status",
                "stores normalized status at this+0x54",
                "calls helper 0x009A4440 with status",
                "sets this+0x51 while notifying callbacks",
                "iterates pointers in [this+0x44, this+0x48)",
                "invokes callback virtual +0x04 with shared context and status",
                "clears notification flag and compacts null callback entries when this+0x50 is set",
                "publishes/forwards a derived result through helpers 0x00CE5B30 and 0x00CB8770"
            ]
        }
    }

    print("[R3 4/8] Gerando headers C++...",flush=True)
    inc=src/"include"/"rextreme"/"game"/"garage"
    inc.mkdir(parents=True,exist_ok=True)

    coordinator_hpp='''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

template <class T>
struct SharedPtr32R3 {
    T* object;
    void* control;
};

struct CraftRequestContext;
struct CraftOperation;

class CraftCarCoordinator {
public:
    // Original main caller: 0x0099FF50
    SharedPtr32R3<CraftOperation> BeginCraft(void* arg0, void* arg1, void* arg2, void* arg3);

private:
    std::uint8_t unknown_00_6F[0x70];
    void* busy70;
    std::uint8_t unknown_74_7F[0x0C];
    void* busy80;
    std::uint8_t unknown_84_8F[0x0C];
    SharedPtr32R3<CraftRequestContext> slot90;
    std::uint8_t unknown_98_9F[0x08];
    void* busyA0;
    std::uint8_t unknown_A4_AF[0x0C];
    void* busyB0;
    std::uint8_t unknown_B4_BF[0x0C];
    void* busyC0;
    std::uint8_t unknown_C4_F7[0x34];
    std::int32_t stateF8; // original state guard; Campaign Edition Phase54 forces value 2
};

} // namespace rextreme::game::garage
'''
    (inc/"CraftCarCoordinator.hpp").write_text(coordinator_hpp,encoding="utf-8")

    operation_hpp='''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

struct CompletionCallback;

class CraftCarOperation {
public:
    // Original result handler: 0x009A48A0
    void HandleResult(std::int32_t transportCode, void* response);

private:
    std::uint8_t unknown_00_23[0x24];
    void* callbackContextObject;
    void* callbackContextControl;
    std::uint8_t unknown_2C_43[0x18];
    CompletionCallback** callbacksBegin; // +0x44
    CompletionCallback** callbacksEnd;   // +0x48
    std::uint8_t unknown_4C_4F[4];
    bool compactCallbacksPending;        // +0x50
    bool notifyingCallbacks;             // +0x51
    std::uint8_t unknown_52_53[2];
    std::int32_t resultStatus;            // +0x54
    std::uint8_t unknown_58_5F[8];
    void* resultContext;                  // +0x60
};

} // namespace rextreme::game::garage
'''
    (inc/"CraftCarOperation.hpp").write_text(operation_hpp,encoding="utf-8")

    print("[R3 5/8] Gerando C++ semantico...",flush=True)
    gdir=src/"src"/"game"/"garage"
    gdir.mkdir(parents=True,exist_ok=True)

    coordinator_cpp='''#include "rextreme/game/garage/CraftCarCoordinator.hpp"

namespace rextreme::game::garage {

// Original VA: 0x0099FF50.
// This is semantic pseudocode backed by the R3 instruction map.
SharedPtr32R3<CraftOperation> CraftCarCoordinator::BeginCraft(
    void* arg0, void* arg1, void* arg2, void* arg3) {

    if (busy70 || busy80 || slot90.object || busyA0 || busyB0 || busyC0) {
        return {};
    }

    // helper 0x0099E0A0 must also report false.
    // Original client then required stateF8 == 2.
    // Campaign Edition Phase54 replaces the load from +0xF8 with constant 2.

    // Request construction and exact argument typing remain to be completed in R4.
    return {};
}

} // namespace rextreme::game::garage
'''
    (gdir/"CraftCarCoordinator.cpp").write_text(coordinator_cpp,encoding="utf-8")

    operation_cpp='''#include "rextreme/game/garage/CraftCarOperation.hpp"

namespace rextreme::game::garage {

// Original VA: 0x009A48A0.
// Pseudocode intentionally preserves unknown helpers instead of inventing server semantics.
void CraftCarOperation::HandleResult(std::int32_t transportCode, void* response) {
    std::int32_t normalizedStatus = transportCode;

    // Original code inspects response keys and transport ranges here.
    // Several backend/transport codes are translated to small local status values,
    // then shifted into the local status domain.

    resultStatus = normalizedStatus;

    // helper 0x009A4440(resultContext, &resultStatus)
    notifyingCallbacks = true;

    for (CompletionCallback** it = callbacksBegin; it != callbacksEnd; ++it) {
        if (*it == nullptr) continue;
        // Original virtual +0x04 receives callbackContext shared state and resultStatus.
    }

    notifyingCallbacks = false;

    if (compactCallbacksPending) {
        // Original implementation removes null callback entries in place.
        compactCallbacksPending = false;
    }

    // Original tail forwards a derived result through 0x00CE5B30 -> 0x00CB8770.
}

} // namespace rextreme::game::garage
'''
    (gdir/"CraftCarOperation.cpp").write_text(operation_cpp,encoding="utf-8")

    craft_cpp='''#include "rextreme/game/garage/CraftCar.hpp"

namespace rextreme::game::garage {

// Wrapper VA 0x009A4BA0:
//   push [ecx+0x68]
//   call 0x009A4BB0
//   ret
void CraftCarService::RequestCraft() {
    // The real request body is 0x009A4BB0.
    // Recovered endpoint: scripts/cars/craft_car.php
}

void CraftCarService::HandleResult() {
    // Behavioral implementation is represented by CraftCarOperation::HandleResult.
}

} // namespace rextreme::game::garage
'''
    (gdir/"CraftCar.cpp").write_text(craft_cpp,encoding="utf-8")

    print("[R3 6/8] Atualizando GS_Garage layout...",flush=True)
    gs_hpp='''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

class GarageBottomBarWidget;

struct SharedOpaque32 {
    void* object;
    void* control;
};

class GS_Garage {
public:
    // vtable 0x0186A9CC; ctor 0x00E00B20; build slot +0x110 = 0x00A87960
    void BuildCar();

private:
    std::uint8_t unknown_000_297[0x298];
    std::uint8_t buildListenerNode[0x3C]; // starts at +0x298; exact type pending
    void* selectionOrGarageObject;        // +0x2D4
    std::uint8_t unknown_2D8_353[0x7C];
    void* ownerObject;                    // +0x354
    void* ownerControl;                   // +0x358
    GarageBottomBarWidget* bottomBar;     // +0x35C
    void* bottomBarControl;               // +0x360
    std::uint8_t unknown_364_3AB[0x48];
    SharedOpaque32 activeBuildOperation;  // +0x3AC/+0x3B0
};

} // namespace rextreme::game::garage
'''
    (inc/"GS_Garage.hpp").write_text(gs_hpp,encoding="utf-8")

    gs_cpp='''#include "rextreme/game/garage/GS_Garage.hpp"

namespace rextreme::game::garage {

// Original VA: 0x00A87960.
// Semantic skeleton reconstructed from 1120 bytes of x86.
void GS_Garage::BuildCar() {
    // 1. Query GlobalIsOnline (0x00FAD9D0). Campaign Edition forces false globally.
    // 2. Prepare selected-car/build arguments.
    // 3. Call CraftCar coordinator 0x0099FF50.
    // 4. Move returned shared operation into +0x3AC/+0x3B0.
    // 5. Register &this+0x298 in the operation callback/listener list if absent.
    // 6. Fetch build button from bottomBar (+0x35C) and invoke virtual +0x7C(false).
    // 7. Invoke GS_Garage virtual +0x54.
}

} // namespace rextreme::game::garage
'''
    (gdir/"GS_Garage.cpp").write_text(gs_cpp,encoding="utf-8")

    print("[R3 7/8] Gravando semantic maps...",flush=True)
    (out/"SEMANTICS.json").write_text(json.dumps({
        "phase":"R3",
        "functions":metas,
        "campaign_overrides":overrides,
        "semantic_model":semantic
    },indent=2),encoding="utf-8")

    doc=src/"docs"/"R3-GARAGE-CRAFT-SEMANTICS.md"
    doc.write_text("""# R3 Garage/CraftCar semantics

## Confirmed

- CraftCar request wrapper 0x009A4BA0 only pushes [this+0x68] and calls 0x009A4BB0.
- 0x009A4BB0 is treated as the real request body.
- CraftCar caller 0x0099FF50 blocks when operation slots +0x70/+0x80/+0x90/+0xA0/+0xB0/+0xC0 are occupied.
- The original caller consumed state at +0xF8 and required value 2.
- Campaign Edition Phase54 forces that consumed state to 2.
- GS_Garage stores the returned build operation at +0x3AC/+0x3B0.
- GS_Garage registers a listener/address rooted at +0x298 into the operation.
- GS_Garage reaches the bottom bar through +0x35C and disables the build button through virtual +0x7C(false).
- CraftCar result stores normalized status at +0x54 and notifies callback pointers in [ +0x44, +0x48 ).

## Still unresolved

- Concrete type names for the coordinator and operation classes.
- Exact payload field names in 0x009A4BB0.
- Exact response-key names associated with global string objects used by 0x009A48A0.
- Which callback/listener ultimately mutates owned-car/profile data after a successful craft.
""",encoding="utf-8")

    mp=src/"reverse"/"RECONSTRUCTION_MANIFEST.json"
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    manifest["source_reconstruction_phase"]="R3"
    manifest["r3_request_body"]="0x009A4BB0"
    manifest["r3_campaign_overrides"]=overrides
    manifest["r3_confirmed_fields"]={
        "GS_Garage":["0x298","0x2D4","0x35C","0x3AC","0x3B0"],
        "CraftCar_Caller":["0x70","0x80","0x90","0xA0","0xB0","0xC0","0xF8"],
        "CraftCar_Result":["0x24","0x28","0x44","0x48","0x50","0x51","0x54","0x60"]
    }
    mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    print("[R3 8/8] SOURCE RECONSTRUCTION R3 OK",flush=True)
    print("Request body:",hex(VA_REQ_BODY),flush=True)
    print("Semantic output:",out/"SEMANTICS.json",flush=True)

if __name__=="__main__":
    main()
