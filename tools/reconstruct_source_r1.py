#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, re, shutil
from pathlib import Path
from collections import defaultdict, deque

KNOWN = {
    "GarageBottomBarWidget_vtable": "0x01831854",
    "GarageBottomBarWidget_ctor": "0x0096EB10",
    "GarageBottomBarWidget_register_buttons": "0x00972B90",
    "GarageBottomBarWidget_build_callback": "0x00973C90",
    "GarageBottomBarWidget_dtor": "0x0096EDF0",
    "GS_Garage_vtable": "0x0186A9CC",
    "GS_Garage_ctor": "0x00E00B20",
    "GS_Garage_build_handler": "0x00A87960",
    "CraftCar_caller": "0x0099FF50",
    "CraftCar": "0x009A4BA0",
    "CraftCar_result": "0x009A48A0",
    "RegisterHelper": "0x0096E4B0",
    "SignalInvokeHelper": "0x00936BE0",
}

SUBSYSTEM_ROOTS = {
    "garage": [
        "0x0096EB10","0x00972B90","0x00973C90","0x00A87960",
        "0x0099FF50","0x009A4BA0","0x009A48A0"
    ],
    "ui": ["0x00972B90","0x0096E4B0","0x00936BE0"],
    "network": ["0x009A4BA0","0x009A48A0"],
    "profile": [],
}

KEYWORDS = {
    "garage": ("garage","build_button","ready_to_build","craft","blueprint","upgrade"),
    "network": ("http://","https://",".php","scripts/","request","response","server","online","network"),
    "profile": ("profile","save","inventory","currency","token","coin","reward","career"),
    "ui": ("widget","button","template","bottom_bar","screen","dialog"),
}

def normva(x):
    if not x:return None
    x=x.strip()
    if not x:return None
    try:return f"0x{int(x,16):08X}"
    except:return x.upper()

def read_csv(path):
    if not path.is_file():
        return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames)
        w.writeheader()
        for r in rows:w.writerow({k:r.get(k,"") for k in fieldnames})

def safe_ident(s):
    s=re.sub(r"[^A-Za-z0-9_]+","_",s)
    if not s or s[0].isdigit():s="_"+s
    return s.strip("_") or "Unknown"

def ensure(p):
    p.mkdir(parents=True,exist_ok=True)
    return p

def transitive(root_vas,callees,max_nodes=50000):
    q=deque((r,0) for r in root_vas if r)
    seen={}
    while q and len(seen)<max_nodes:
        va,d=q.popleft()
        if va in seen:continue
        seen[va]=d
        for dst in callees.get(va,()):
            if dst not in seen:q.append((dst,d+1))
    return seen

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX"
    if not atlas.is_dir():
        raise SystemExit(f"Atlas nao encontrado: {atlas}")

    required=["SUMMARY.json","FUNCTIONS.csv","CALL_GRAPH.csv","RTTI.csv","VTABLES.csv","STRINGS.csv","STRING_XREFS.csv"]
    missing=[x for x in required if not (atlas/x).is_file()]
    if missing:
        raise SystemExit("Atlas incompleto. Faltando: "+", ".join(missing))

    print("[R1 1/8] Lendo atlas...",flush=True)
    summary=json.loads((atlas/"SUMMARY.json").read_text(encoding="utf-8"))
    funcs=read_csv(atlas/"FUNCTIONS.csv")
    calls=read_csv(atlas/"CALL_GRAPH.csv")
    rtti=read_csv(atlas/"RTTI.csv")
    vtables=read_csv(atlas/"VTABLES.csv")
    strings=read_csv(atlas/"STRINGS.csv")
    sx=read_csv(atlas/"STRING_XREFS.csv")

    f_by_va={}
    for r in funcs:
        va=normva(r.get("va"))
        if va:f_by_va[va]=r

    callees=defaultdict(set);callers=defaultdict(set)
    for r in calls:
        s=normva(r.get("src_function_va"));d=normva(r.get("dst_va"))
        if s and d:
            callees[s].add(d);callers[d].add(s)

    print(f"          functions={len(f_by_va)} calls={len(calls)} RTTI={len(rtti)} vtableRows={len(vtables)}",flush=True)

    out=root/"src-reconstructed"
    if out.exists():
        backup=root/"src-reconstructed.previous"
        if backup.exists():shutil.rmtree(backup)
        shutil.move(str(out),str(backup))
    ensure(out)

    print("[R1 2/8] Criando estrutura...",flush=True)
    for rel in [
        "include/rextreme/reverse","include/rextreme/game/garage","include/rextreme/network",
        "include/rextreme/profile","include/rextreme/ui",
        "src/game/garage","src/network","src/profile","src/ui",
        "reverse","docs","generated"
    ]:ensure(out/rel)

    print("[R1 3/8] Classificando strings/xrefs...",flush=True)
    tags=defaultdict(set)
    evidence=defaultdict(list)
    for r in sx:
        fn=normva(r.get("function_va"))
        text=(r.get("string") or "")
        lo=text.lower()
        if not fn:continue
        for sub,words in KEYWORDS.items():
            if any(w in lo for w in words):
                tags[fn].add(sub)
                if len(evidence[fn])<20:evidence[fn].append(text[:500])

    print("[R1 4/8] Construindo subgrafos prioritarios...",flush=True)
    reach={}
    for sub,roots in SUBSYSTEM_ROOTS.items():
        roots2=[normva(x) for x in roots]
        reach[sub]=transitive(roots2,callees,50000)
        print(f"          {sub}: {len(reach[sub])} funcoes alcancaveis",flush=True)

    for sub,rs in reach.items():
        for va in rs:tags[va].add(sub)

    print("[R1 5/8] Gerando mapa integral das funcoes...",flush=True)
    index_rows=[]
    unresolved=[]
    reverse_known={normva(v):k for k,v in KNOWN.items()}
    for va,r in sorted(f_by_va.items()):
        known_name=reverse_known.get(va,"")
        stags=sorted(tags.get(va,set()))
        row={
            "va":va,
            "file_start":r.get("file_start",""),
            "file_end":r.get("file_end",""),
            "size":r.get("size",""),
            "section":r.get("section",""),
            "caller_count":r.get("caller_count",""),
            "callee_count":r.get("callee_count",""),
            "known_name":known_name,
            "subsystems":";".join(stags),
            "evidence":" | ".join(evidence.get(va,[])[:8]),
        }
        index_rows.append(row)
        if not known_name:unresolved.append(row)

    fields=["va","file_start","file_end","size","section","caller_count","callee_count","known_name","subsystems","evidence"]
    write_csv(out/"reverse"/"FUNCTION_INDEX.csv",index_rows,fields)
    write_csv(out/"reverse"/"UNRESOLVED_FUNCTIONS.csv",unresolved,fields)
    (out/"reverse"/"KNOWN_ANCHORS.json").write_text(json.dumps(KNOWN,indent=2),encoding="utf-8")
    (out/"reverse"/"ATLAS_SOURCE_SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("[R1 6/8] Gerando headers/source conhecidos...",flush=True)
    address_hpp="#pragma once\n#include <cstdint>\n\nnamespace rextreme::reverse {\nstruct Address final {\n"
    for name,va in KNOWN.items():
        address_hpp+=f"    static constexpr std::uintptr_t {safe_ident(name)} = {va};\n"
    address_hpp+="};\n} // namespace rextreme::reverse\n"
    (out/"include/rextreme/reverse/AddressMap.hpp").write_text(address_hpp,encoding="utf-8")

    gbbw_hpp=r'''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

template <class T>
struct SharedPtr32 {
    T* object;
    void* control;
};

struct SignalOpaque;

class GarageBottomBarWidget {
public:
    // Original vtable: 0x01831854
    // Constructor:     0x0096EB10
    // Destructor:      0x0096EDF0
    // Register UI:     0x00972B90
    // Build callback:  0x00973C90

    void RegisterButtons();
    void OnBuildPressed();

private:
    std::uint8_t unknown_00_33[0x34];

    SharedPtr32<SignalOpaque> signal_34;
    SharedPtr32<SignalOpaque> signal_3C;
    SharedPtr32<SignalOpaque> buildSignal; // +0x44/+0x48 CONFIRMED
    SharedPtr32<SignalOpaque> signal_4C;
    SharedPtr32<SignalOpaque> signal_54;
    SharedPtr32<SignalOpaque> signal_5C;
    SharedPtr32<SignalOpaque> signal_64;
};

} // namespace rextreme::game::garage
'''
    (out/"include/rextreme/game/garage/GarageBottomBarWidget.hpp").write_text(gbbw_hpp,encoding="utf-8")

    gbbw_cpp=r'''#include "rextreme/game/garage/GarageBottomBarWidget.hpp"

namespace rextreme::game::garage {

// Original VA: 0x00972B90.
// Binds UI delegates. Exact code will be reconstructed in R2.
void GarageBottomBarWidget::RegisterButtons() {
}

// Original callback VA: 0x00973C90.
// Verified: read buildSignal.object at +0x44; if null, return;
// otherwise invoke signal infrastructure using the signal object's +0x08 member.
void GarageBottomBarWidget::OnBuildPressed() {
    if (!buildSignal.object) {
        return;
    }

    // R2: type SignalOpaque and reconstruct 0x00936BE0 exactly.
}

} // namespace rextreme::game::garage
'''
    (out/"src/game/garage/GarageBottomBarWidget.cpp").write_text(gbbw_cpp,encoding="utf-8")

    gs_hpp=r'''#pragma once
#include <cstdint>

namespace rextreme::game::garage {

class GarageBottomBarWidget;

class GS_Garage {
public:
    // Original vtable:      0x0186A9CC
    // Original ctor:        0x00E00B20
    // Build handler +0x110: 0x00A87960
    void BuildCar();

private:
    std::uint8_t unknown_000_353[0x354];
    void* ownerObject;
    void* ownerControl;
    GarageBottomBarWidget* bottomBar; // +0x35C
    void* bottomBarControl;
};

} // namespace rextreme::game::garage
'''
    (out/"include/rextreme/game/garage/GS_Garage.hpp").write_text(gs_hpp,encoding="utf-8")

    gs_cpp=r'''#include "rextreme/game/garage/GS_Garage.hpp"

namespace rextreme::game::garage {

// Original VA: 0x00A87960
// Known downstream chain:
//   GS_Garage::BuildCar -> 0x0099FF50 -> CraftCar 0x009A4BA0
void GS_Garage::BuildCar() {
    // R2: reconstruct validation/state guards and exact CraftCar request setup.
}

} // namespace rextreme::game::garage
'''
    (out/"src/game/garage/GS_Garage.cpp").write_text(gs_cpp,encoding="utf-8")

    craft_hpp=r'''#pragma once

namespace rextreme::game::garage {

struct CraftCarService {
    // Caller: 0x0099FF50
    // Request: 0x009A4BA0
    // Result: 0x009A48A0
    static void RequestCraft();
    static void HandleResult();
};

} // namespace rextreme::game::garage
'''
    (out/"include/rextreme/game/garage/CraftCar.hpp").write_text(craft_hpp,encoding="utf-8")

    craft_cpp=r'''#include "rextreme/game/garage/CraftCar.hpp"

namespace rextreme::game::garage {

void CraftCarService::RequestCraft() {
    // Recovered endpoint: scripts/cars/craft_car.php
    // R2: reconstruct payload and offline-compatible request contract.
}

void CraftCarService::HandleResult() {
    // R2: reconstruct profile/progression mutations from 0x009A48A0.
}

} // namespace rextreme::game::garage
'''
    (out/"src/game/garage/CraftCar.cpp").write_text(craft_cpp,encoding="utf-8")

    net_hpp=r'''#pragma once
#include <string_view>

namespace rextreme::network {

class OfflineBackend {
public:
    static bool HandleEndpoint(std::string_view endpoint);
};

} // namespace rextreme::network
'''
    (out/"include/rextreme/network/OfflineBackend.hpp").write_text(net_hpp,encoding="utf-8")

    net_cpp=r'''#include "rextreme/network/OfflineBackend.hpp"

namespace rextreme::network {

bool OfflineBackend::HandleEndpoint(std::string_view endpoint) {
    // R2+ will add endpoint handlers reconstructed from the original client contracts.
    return false;
}

} // namespace rextreme::network
'''
    (out/"src/network/OfflineBackend.cpp").write_text(net_cpp,encoding="utf-8")

    print("[R1 7/8] Gerando manifest e README...",flush=True)
    manifests={}
    for sub,rs in reach.items():
        rows=[]
        for va,depth in sorted(rs.items(),key=lambda x:(x[1],x[0])):
            fr=f_by_va.get(va,{})
            rows.append({
                "va":va,
                "depth":depth,
                "file_start":fr.get("file_start",""),
                "size":fr.get("size",""),
                "known_name":reverse_known.get(va,""),
                "strings":evidence.get(va,[])[:10],
            })
        (out/"reverse"/f"{sub.upper()}_SUBGRAPH.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        manifests[sub]=len(rows)

    manifest={
        "source_reconstruction_phase":"R1",
        "atlas_function_count":len(f_by_va),
        "indexed_call_count":len(calls),
        "rtti_count":len(rtti),
        "vtable_row_count":len(vtables),
        "known_anchor_count":len(KNOWN),
        "unresolved_function_count":len(unresolved),
        "subgraphs":manifests,
        "priorities":[
            "GarageBottomBarWidget buildSignal connection",
            "GS_Garage BuildCar exact semantics",
            "CraftCar request/result contracts",
            "Profile/save mutations",
            "Offline endpoint compatibility"
        ]
    }
    (out/"reverse"/"RECONSTRUCTION_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    readme=f"""# Asphalt ReXtreme - Reconstructed Source

This tree is a clean-room functional reconstruction from the shipped x86 client and FULL GAME ATLAS.

R1 status:
- Atlas functions indexed: {len(f_by_va)}
- Call graph rows consumed: {len(calls)}
- RTTI rows consumed: {len(rtti)}
- Vtable rows consumed: {len(vtables)}
- Unresolved functions tracked: {len(unresolved)}

This is not the original Gameloft source. Every reconstructed symbol keeps explicit VA/file provenance.

Immediate targets:
1. GarageBottomBarWidget build signal +0x44/+0x48
2. GS_Garage::BuildCar at 0x00A87960
3. CraftCar request 0x009A4BA0
4. CraftCar result handler 0x009A48A0
5. Local backend contracts and profile persistence
"""
    (out/"README.md").write_text(readme,encoding="utf-8")

    print("[R1 8/8] RECONSTRUCTION R1 OK",flush=True)
    print("Output:",out,flush=True)
    print("Functions indexed:",len(f_by_va),flush=True)
    print("Unresolved:",len(unresolved),flush=True)
    print("Garage subgraph:",manifests.get("garage",0),flush=True)
    print("Network subgraph:",manifests.get("network",0),flush=True)

if __name__=="__main__":
    main()
