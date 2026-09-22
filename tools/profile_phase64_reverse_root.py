#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict, deque

# Known stable chain / targets.
P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; P63=bytes.fromhex("90 90"); PRE63=bytes.fromhex("74 0B")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

CRAFTCAR_START=0x009A4BA0
CRAFTCAR_CALLER=0x0099FF50
BUILD_HANDLER=0x00A87960
GS_GARAGE_VTABLE=0x0186A9CC
GBBW_VTABLE=0x01831854

UI_SEEDS = {
    "template_build_button_builder":0x0096F3B0,
    "build_button_getter":0x00973510,
    "preclick_secondary_updater":0x00975A50,
    "garage_click_router":0x009747F0,
    "garage_click_slot14":0x009740D0,
    "garage_click_slot18":0x00975040,
    "garage_slot1C":0x009743C0,
    "garage_slot20":0x00974A40,
    "garage_slot24":0x00974ED0,
}
KNOWN = dict(UI_SEEDS)
KNOWN.update({
    "craftcar_start":CRAFTCAR_START,
    "craftcar_unique_caller":CRAFTCAR_CALLER,
    "build_handler":BUILD_HANDLER,
})

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8(b,o):
    x=b[o]; return x-256 if x>=128 else x
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

def sha_bytes(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:
        raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16),
            raw=u32(d,o+20), ch=u32(d,o+36)
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

def sec_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]: return s
    return None

def is_exec_file(off,secs):
    s=sec_for_file(off,secs)
    return bool(s and (s["ch"]&0x20000000))

def is_exec_va(va,ib,secs):
    fo=v2f(va,ib,secs)
    return fo is not None and is_exec_file(fo,secs)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p); p+=1

def guess_prologue(d,near,back=0x5000):
    lo=max(0,near-back)
    # Primary MSVC frame prologue.
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC":
            return p
    return None

def next_prologue(d,start,limit=0x5000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def function_va_for_file(d,off,ib,secs):
    p=guess_prologue(d,off)
    return f2v(p,ib,secs) if p is not None else None

def scan_direct_call_index(d,ib,secs):
    callers=defaultdict(list)  # targetVA -> [(callFile, callerFnVA)]
    outgoing=defaultdict(list) # callerFnVA -> [(callFile,targetVA)]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        cur_fn=None
        while p<=end:
            if d[p:p+3]==b"\x55\x8B\xEC":
                cur_fn=f2v(p,ib,secs)
            if d[p]==0xE8:
                src=f2v(p,ib,secs)
                if src is not None:
                    dst=(src+5+i32(d,p+1))&0xffffffff
                    if is_exec_va(dst,ib,secs):
                        fn=cur_fn or function_va_for_file(d,p,ib,secs)
                        callers[dst].append((p,fn))
                        if fn is not None:
                            outgoing[fn].append((p,dst))
                p+=5; continue
            p+=1
    return callers,outgoing

def scan_slot_calls(d,ib,secs,slot):
    # Common x86 form FF 90 xx xx xx xx (call [eax+disp32]), any rm except SIB.
    hits=[]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d),s["raw"]+s["rs"])
        while p+6<=end:
            if d[p]==0xFF:
                modrm=d[p+1]
                reg=(modrm>>3)&7; mod=(modrm>>6)&3; rm=modrm&7
                if reg==2 and mod==2 and rm!=4 and u32(d,p+2)==slot:
                    fn=function_va_for_file(d,p,ib,secs)
                    hits.append((p,f2v(p,ib,secs),fn,modrm))
                    p+=6; continue
            p+=1
    return hits

def closure_forward(seeds,outgoing,max_depth=6):
    q=deque((va,0,[va]) for va in seeds)
    best={}
    paths={}
    while q:
        va,dep,path=q.popleft()
        if va in best and best[va]<=dep: continue
        best[va]=dep; paths[va]=path
        if dep>=max_depth: continue
        for _,dst in outgoing.get(va,[]):
            q.append((dst,dep+1,path+[dst]))
    return best,paths

def closure_reverse(seeds,callers,max_depth=7):
    q=deque((va,0,[va]) for va in seeds)
    best={}
    paths={}
    while q:
        va,dep,path=q.popleft()
        if va in best and best[va]<=dep: continue
        best[va]=dep; paths[va]=path
        if dep>=max_depth: continue
        for _,parent in callers.get(va,[]):
            if parent is not None:
                q.append((parent,dep+1,[parent]+path))
    return best,paths

def ascii_z(d,off,limit=256):
    if off is None or off<0 or off>=len(d): return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("ascii","replace")
    except:return ""
    if not s:return ""
    printable=sum(0x20<=ord(c)<0x7f for c in s)
    return s if printable>=max(1,int(len(s)*0.9)) else ""

def rtti_name_for_vtable_file(d,vf,ib,secs):
    if vf<4:return None
    col_va=u32(d,vf-4)
    col_f=v2f(col_va,ib,secs)
    if col_f is None or col_f+20>len(d):return None
    td_va=u32(d,col_f+12)
    td_f=v2f(td_va,ib,secs)
    if td_f is None:return None
    return ascii_z(d,td_f+8,300)

def vtable_occurrences_of_method(d,method_va,ib,secs):
    out=[]
    for hit in find_all(d,struct.pack("<I",method_va)):
        if is_exec_file(hit,secs): continue
        # walk backward looking for RTTI-backed vtable start
        for vf in range(hit,max(4,hit-0x800)-1,-4):
            name=rtti_name_for_vtable_file(d,vf,ib,secs)
            if not(name and name.startswith(".?A")): continue
            idx=(hit-vf)//4
            good=True
            for p in range(vf,hit+4,4):
                if not is_exec_va(u32(d,p),ib,secs):
                    good=False; break
            if good:
                out.append((vf,f2v(vf,ib,secs),idx,idx*4,name,hit))
                break
    uniq=[]; seen=set()
    for x in out:
        key=(x[0],x[2])
        if key not in seen:
            seen.add(key); uniq.append(x)
    return uniq

def abs_data_refs_to_va(d,va,secs):
    return [p for p in find_all(d,struct.pack("<I",va)) if not is_exec_file(p,secs)]

def exec_refs_to_va(d,va,ib,secs):
    return [p for p in find_all(d,struct.pack("<I",va)) if is_exec_file(p,secs)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")

    d=bytearray(ams.read_bytes())

    # Stable guards first.
    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        cur=bytes(d[off:off+len(exp)])
        if cur!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    before_sha=sha_bytes(bytes(d))
    p63_state=bytes(d[P63_OFF:P63_OFF+2])
    reverted=False
    if p63_state==P63:
        d[P63_OFF:P63_OFF+2]=PRE63
        tmp=ams.with_suffix(".phase64.tmp")
        tmp.write_bytes(d)
        tmp.replace(ams)
        reverted=True
    elif p63_state!=PRE63:
        raise SystemExit(f"Phase63 site unexpected at 0x{P63_OFF:08X}: {p63_state.hex(' ')}")
    after_sha=sha_bytes(ams.read_bytes())
    d=ams.read_bytes()

    ib,secs=parse_pe(d)
    callers,outgoing=scan_direct_call_index(d,ib,secs)

    # Canonical CraftCar chain.
    craft_callers=callers.get(CRAFTCAR_START,[])
    unique_callers=callers.get(CRAFTCAR_CALLER,[])

    # Build handler vtable owners and slot-0x110 dispatchers.
    owners=vtable_occurrences_of_method(d,BUILD_HANDLER,ib,secs)
    slot110=scan_slot_calls(d,ib,secs,0x110)
    slot110_fns=sorted({fn for _,_,fn,_ in slot110 if fn is not None})

    # Reverse from all slot+0x110 dispatchers.
    rev_depth,rev_paths=closure_reverse(slot110_fns,callers,7)

    # Forward from UI/build-button side.
    ui_depth,ui_paths=closure_forward(list(UI_SEEDS.values()),outgoing,7)

    # Direct meet points.
    meets=sorted(set(rev_depth)&set(ui_depth),
                 key=lambda va:(rev_depth[va]+ui_depth[va],ui_depth[va],rev_depth[va],va))

    # Data/delegate bridge: functions referenced as pointers in non-exec data,
    # then code references to those data cells.
    delegate_rows=[]
    candidate_vas=set(slot110_fns)|set(rev_depth)
    for va in sorted(candidate_vas):
        datarefs=abs_data_refs_to_va(d,va,secs)
        for dr in datarefs[:60]:
            dva=f2v(dr,ib,secs)
            if dva is None: continue
            xrefs=exec_refs_to_va(d,dva,ib,secs)
            for xr in xrefs[:60]:
                fn=function_va_for_file(d,xr,ib,secs)
                delegate_rows.append((va,dr,dva,xr,fn))
                if fn is not None and fn not in rev_depth:
                    rev_depth[fn]=8
                    rev_paths[fn]=[fn,va]

    # Recompute extended meets after delegate bridge.
    meets2=sorted(set(rev_depth)&set(ui_depth),
                  key=lambda va:(rev_depth[va]+ui_depth[va],ui_depth[va],rev_depth[va],va))

    # UI function-pointer immediates pointing into reverse-side candidates.
    ui_pointer_hits=[]
    rev_candidates=set(rev_depth)|set(slot110_fns)|{BUILD_HANDLER}
    for uname,uva in UI_SEEDS.items():
        uf=v2f(uva,ib,secs)
        if uf is None: continue
        ue=next_prologue(d,uf,0x5000)
        body=d[uf:ue]
        for rv in sorted(rev_candidates):
            pat=struct.pack("<I",rv)
            pos=0
            while True:
                j=body.find(pat,pos)
                if j<0: break
                ui_pointer_hits.append((uname,uva,uf+j,rv))
                pos=j+1

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE64_REVERSE_ROOT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE64-REVERSE-ROOT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[]; w=lines.append
    w("="*96)
    w(" ReXtreme Phase 64 - reverse-root / meet-in-the-middle build-button analysis")
    w("="*96)
    w(f"AMS_SHA256_BEFORE={before_sha}")
    w(f"Phase63Reverted={reverted}")
    w(f"AMS_SHA256={after_sha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    w("===== CANONICAL BACKEND CHAIN =====")
    w(f"CraftCarStart=0x{CRAFTCAR_START:08X}")
    w(f"CraftCarStartDirectCallers={len(craft_callers)}")
    for cf,fn in craft_callers:
        w(f" callerCallFile=0x{cf:08X} callerFn={('0x%08X'%fn) if fn else 'N/A'}")
    w(f"CraftCarUniqueCaller=0x{CRAFTCAR_CALLER:08X}")
    w(f"UniqueCallerDirectCallers={len(unique_callers)}")
    for cf,fn in unique_callers:
        w(f" callerCallFile=0x{cf:08X} callerFn={('0x%08X'%fn) if fn else 'N/A'}")
    w(f"BuildHandler=0x{BUILD_HANDLER:08X}")
    w("")

    w("===== BUILD HANDLER VTABLE OWNERS =====")
    for vf,vva,idx,slot,rtti,hit in owners:
        mark=" [GS_GARAGE]" if vva==GS_GARAGE_VTABLE else ""
        w(f"RTTI={rtti!r} vtableVA=0x{vva:08X} slot=0x{slot:X} index={idx} hitFile=0x{hit:08X}{mark}")
    w("")

    w("===== ALL CALL [VTABLE+0x110] DISPATCHERS =====")
    w(f"CallSites={len(slot110)} UniqueContainingFunctions={len(slot110_fns)}")
    for p,pva,fn,modrm in slot110:
        w(f"callFile=0x{p:08X} callVA=0x{pva:08X} containingFn={('0x%08X'%fn) if fn else 'N/A'} modrm=0x{modrm:02X}")
    w("")

    w("===== REVERSE ROOTS FROM SLOT+0x110 =====")
    roots=sorted(rev_depth,key=lambda va:(rev_depth[va],va))
    for va in roots[:1200]:
        w(f"depth={rev_depth[va]} fn=0x{va:08X} path="+" -> ".join(f"0x{x:08X}" for x in rev_paths.get(va,[va])))
    w("")

    w("===== UI FORWARD GRAPH =====")
    for va in sorted(ui_depth,key=lambda x:(ui_depth[x],x))[:1200]:
        names=[n for n,v in UI_SEEDS.items() if v==va]
        w(f"depth={ui_depth[va]} fn=0x{va:08X} seed={','.join(names)} path="+" -> ".join(f"0x{x:08X}" for x in ui_paths.get(va,[va])))
    w("")

    w("===== DIRECT MEET POINTS =====")
    w(f"Count={len(meets)}")
    for va in meets[:200]:
        w(f"MEET fn=0x{va:08X} score={rev_depth[va]+ui_depth[va]} uiDepth={ui_depth[va]} reverseDepth={rev_depth[va]}")
        w(" UI_PATH="+" -> ".join(f"0x{x:08X}" for x in ui_paths[va]))
        w(" BACKEND_PATH="+" -> ".join(f"0x{x:08X}" for x in rev_paths[va]))
        fo=v2f(va,ib,secs)
        if fo is not None: lines.extend(dump(d,fo,min(len(d),fo+0x180)))
    w("")

    w("===== DELEGATE / DATA FUNCTION-POINTER BRIDGES =====")
    w(f"Count={len(delegate_rows)}")
    for va,dr,dva,xr,fn in delegate_rows[:1000]:
        w(f"targetFn=0x{va:08X} dataFile=0x{dr:08X} dataVA=0x{dva:08X} codeRefFile=0x{xr:08X} codeFn={('0x%08X'%fn) if fn else 'N/A'}")
        lines.extend(dump(d,xr-48,xr+96))
    w("")

    w("===== EXTENDED MEET POINTS (INCLUDING DELEGATE BRIDGES) =====")
    w(f"Count={len(meets2)}")
    for va in meets2[:250]:
        w(f"MEET2 fn=0x{va:08X} score={rev_depth[va]+ui_depth[va]} uiDepth={ui_depth[va]} reverseDepth={rev_depth[va]}")
        w(" UI_PATH="+" -> ".join(f"0x{x:08X}" for x in ui_paths[va]))
        w(" BACKEND_PATH="+" -> ".join(f"0x{x:08X}" for x in rev_paths[va]))
    w("")

    w("===== UI BODY FUNCTION-POINTER HITS INTO BACKEND REVERSE SET =====")
    w(f"Count={len(ui_pointer_hits)}")
    for uname,uva,p,rv in ui_pointer_hits:
        w(f"ui={uname} uiVA=0x{uva:08X} ptrFile=0x{p:08X} -> backendCandidate=0x{rv:08X}")
        lines.extend(dump(d,p-32,p+48))
    w("")

    # Focus known vtables and registration-like calls around template builder.
    w("===== TEMPLATE BUILDER BODY / CALLS =====")
    tf=v2f(UI_SEEDS["template_build_button_builder"],ib,secs)
    if tf is not None:
        te=next_prologue(d,tf,0x5000)
        lines.extend(dump(d,tf,te))
        for p,dst in outgoing.get(UI_SEEDS["template_build_button_builder"],[]):
            name=next((k for k,v in KNOWN.items() if v==dst),"")
            w(f"CALL file=0x{p:08X} -> 0x{dst:08X} {name}")
    w("")

    summary_obj={
        "phase":"64-reverse-root",
        "phase63_reverted":reverted,
        "ams_sha256_before":before_sha,
        "ams_sha256":after_sha,
        "backend":{
            "craftcar_start":f"0x{CRAFTCAR_START:08X}",
            "craftcar_unique_caller":f"0x{CRAFTCAR_CALLER:08X}",
            "build_handler":f"0x{BUILD_HANDLER:08X}",
            "slot110_dispatchers":[f"0x{x:08X}" for x in slot110_fns],
        },
        "direct_meets":[
            {
                "va":f"0x{x:08X}",
                "ui_depth":ui_depth[x],
                "reverse_depth":rev_depth[x],
                "ui_path":[f"0x{v:08X}" for v in ui_paths[x]],
                "backend_path":[f"0x{v:08X}" for v in rev_paths[x]],
            } for x in meets[:100]
        ],
        "extended_meets":[
            {
                "va":f"0x{x:08X}",
                "ui_depth":ui_depth[x],
                "reverse_depth":rev_depth[x],
            } for x in meets2[:100]
        ],
        "delegate_bridge_count":len(delegate_rows),
        "ui_pointer_hit_count":len(ui_pointer_hits),
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(summary_obj,indent=2),encoding="utf-8")

    print("="*96)
    print(" PHASE 64 REVERSE ROOT READY")
    print("="*96)
    print("Phase63 reverted:", reverted)
    print("Global IsOnline remains FALSE.")
    print("Direct meet points:", len(meets))
    print("Extended meet points:", len(meets2))
    print("Delegate bridges:", len(delegate_rows))
    print("UI pointer hits:", len(ui_pointer_hits))
    print("Report:", report)
    print("Summary:", summary)

if __name__=="__main__":
    main()
