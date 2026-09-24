#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict

# Stable chain.
P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

# Failed Phase65 site. Phase66 restores it before mapping.
P65_OFF=0x0056E9CE
P65=bytes.fromhex("C6 45 E3 01")
PRE65=bytes.fromhex("0F 94 45 E3")
STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

# GarageBottomBarWidget / Garage known addresses.
VTABLE_A=0x01831854
VTABLE_B=0x01837A5C
GS_GARAGE_VTABLE=0x0186A9CC
BUILD_HANDLER=0x00A87960
CRAFTCAR_CALLER=0x0099FF50
CRAFTCAR=0x009A4BA0

BUILD_BUTTON_VA=0x0153F0DC
TEMPLATE_BUILD_BUTTON_VA=0x0153F1A0
READY_TO_BUILD_VA=0x0153F12C
HINT_TO_BUILD_VA=0x0153F144

TARGETS={
    "gbbw_base_ctor":0x00964830,
    "owner_pair_helper_A":0x00964C40,
    "owner_pair_helper_B":0x00964D90,
    "weak_resolve_00902060":0x00902060,
    "weak_resolve_00902140":0x00902140,
    "weak_resolve_00902220":0x00902220,
    "ui_lookup_00934890":0x00934890,
    "template_build_button":0x0096F3B0,
    "build_button_getter":0x00973510,
    "ready_to_build_ui":0x00974480,
    "garage_slot10":0x009747F0,
    "garage_slot14":0x009740D0,
    "garage_slot18":0x00975040,
    "garage_slot1C":0x009743C0,
    "garage_slot20":0x00974A40,
    "garage_slot24":0x00974ED0,
    "secondary_updater":0x00975A50,
    "build_handler":BUILD_HANDLER,
    "craftcar_unique_caller":CRAFTCAR_CALLER,
    "craftcar":CRAFTCAR,
}

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

def sha(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4] != b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
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
        if s["raw"] <= off < s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"] <= rva < s["va"]+max(s["vs"],s["rs"]):
            return s["raw"]+(rva-s["va"])
    return None

def sec_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]: return s
    return None

def is_exec_file(off,secs):
    s=sec_for_file(off,secs)
    return bool(s and (s["ch"] & 0x20000000))

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    return f is not None and is_exec_file(f,secs)

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: return out
        out.append(p); p+=1

def prologue(d,near,back=0x6000):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def next_prologue(d,start,limit=0x6000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def direct_callers(d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    out.append((p,prologue(d,p)))
                    p+=5; continue
            p+=1
    return out

def scan_direct_calls_in_fn(d,fs,fe,ib,secs):
    out=[]; p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,dst,v2f(dst,ib,secs)))
            p+=5; continue
        p+=1
    return out

def virtual_calls_in_fn(d,fs,fe):
    out=[]; p=fs
    while p+2<=fe:
        if d[p]==0xFF:
            mr=d[p+1]; reg=(mr>>3)&7; mod=(mr>>6)&3; rm=mr&7
            if reg==2 and rm!=4:
                if mod==1 and p+3<=fe:
                    disp=d[p+2]
                    if disp>=128: disp-=256
                    out.append((p,disp,3))
                    p+=3; continue
                if mod==2 and p+6<=fe:
                    disp=u32(d,p+2)
                    out.append((p,disp,6))
                    p+=6; continue
        p+=1
    return out

def ascii_z(d,off,limit=300):
    if off is None or not(0<=off<len(d)): return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0: z=min(len(d),off+limit)
    raw=d[off:z]
    try: s=raw.decode("ascii","replace")
    except: return ""
    return s if s and sum(0x20<=ord(c)<0x7f for c in s)>=max(1,int(len(s)*.9)) else ""

def rtti_name(d,vtable_va,ib,secs):
    vf=v2f(vtable_va,ib,secs)
    if vf is None or vf<4:return None
    col=v2f(u32(d,vf-4),ib,secs)
    if col is None or col+20>len(d):return None
    td=v2f(u32(d,col+12),ib,secs)
    return ascii_z(d,td+8,300) if td is not None else None

def method_table(d,vva,ib,secs,count=20):
    vf=v2f(vva,ib,secs)
    out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        out.append((i,i*4,va,v2f(va,ib,secs)))
    return out

def looks_like_disp32_use(d,pos):
    # pos points to 4-byte displacement. Require a ModRM byte just before it with mod=10b.
    if pos<2:return False
    mr=d[pos-1]
    mod=(mr>>6)&3; rm=mr&7
    if mod!=2 or rm==4:return False
    op=d[pos-2]
    return op in {0x8B,0x89,0x8D,0x83,0x81,0x80,0xC6,0xC7,0x39,0x3B,0xFF,0xF6,0xF7}

def member_hits(d,disp,ib,secs):
    pat=struct.pack("<I",disp)
    rows=[]
    for p in find_all(d,pat):
        if not is_exec_file(p,secs): continue
        if not looks_like_disp32_use(d,p): continue
        fs=prologue(d,p)
        rows.append((p,f2v(p,ib,secs),fs,f2v(fs,ib,secs) if fs is not None else None))
    return rows

def function_bounds_for_va(d,va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return None,None
    # Known VA is expected to be function start. Still cap at next prologue.
    return f,next_prologue(d,f,0x7000)

def write_function_section(lines,d,name,va,ib,secs,body_cap=0x900):
    w=lines.append
    fs,fe=function_bounds_for_va(d,va,ib,secs)
    if fs is None:
        w(f"[{name}] VA=0x{va:08X} file=N/A"); return
    fe=min(fe,fs+body_cap)
    w(f"[{name}] VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X}")
    lines.extend(dump(d,fs,fe))
    w("-- direct calls --")
    for p,dst,dstf in scan_direct_calls_in_fn(d,fs,fe,ib,secs):
        tag=next((k for k,v in TARGETS.items() if v==dst),"")
        w(f" CALL file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dstf) if dstf is not None else 'N/A'} {tag}")
    w("-- virtual calls --")
    for p,slot,n in virtual_calls_in_fn(d,fs,fe):
        w(f" VCALL file=0x{p:08X} slot={slot if slot<0 else '0x%X'%slot}")
    w("")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")

    d=bytearray(ams.read_bytes())
    before=sha(bytes(d))

    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),
        ("Phase36Popup",POPUP_OFF,POPUP),
    ]:
        cur=bytes(d[off:off+len(exp)])
        if cur!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    p65=bytes(d[P65_OFF:P65_OFF+4])
    reverted=False
    if p65==P65:
        backup=root/"_PACKAGE_PHASE5"/"AMS.PHASE65-FAILED-BEFORE-PHASE66.exe"
        if not backup.exists(): backup.write_bytes(d)
        d[P65_OFF:P65_OFF+4]=PRE65
        tmp=ams.with_suffix(".phase66.tmp")
        tmp.write_bytes(d); tmp.replace(ams)
        reverted=True
    elif p65!=PRE65:
        raise SystemExit(f"Phase65 site unexpected at 0x{P65_OFF:08X}: {p65.hex(' ')}")

    d=ams.read_bytes()
    after=sha(d)
    if after!=STABLE_SHA:
        raise SystemExit(f"After Phase65 rollback SHA is {after}, expected stable {STABLE_SHA}. Nothing else was changed.")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE66_BUILD_BUTTON_CALLBACK_BINDING"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE66-BUILD-BUTTON-CALLBACK-BINDING.txt"
    summary=outdir/"SUMMARY.json"

    lines=[]; w=lines.append
    w("="*100)
    w(" ReXtreme Phase 66 - build_button callback / owner binding mapper")
    w("="*100)
    w(f"AMS_SHA256_BEFORE={before}")
    w(f"Phase65Reverted={reverted}")
    w(f"AMS_SHA256={after}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO NEW GAMEPLAY PATCH APPLIED")
    w("")

    w("===== CANONICAL GARAGE BACKEND =====")
    w(f"GS_Garage_vtable=0x{GS_GARAGE_VTABLE:08X}")
    w(f"slot+0x110=0x{BUILD_HANDLER:08X}")
    w(f"CraftCarCaller=0x{CRAFTCAR_CALLER:08X}")
    w(f"CraftCar=0x{CRAFTCAR:08X}")
    w("")

    w("===== GARAGE BOTTOM BAR RTTI / VTABLES =====")
    for label,vva in [("A",VTABLE_A),("B",VTABLE_B)]:
        w(f"[Variant {label}] vtableVA=0x{vva:08X} RTTI={rtti_name(d,vva,ib,secs)!r}")
        for i,slot,va,fo in method_table(d,vva,ib,secs,24):
            tag=next((k for k,v in TARGETS.items() if v==va),"")
            w(f" slot=0x{slot:02X} index={i:02d} VA=0x{va:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'} {tag}")
        w("")

    w("===== BUILD_BUTTON / READY STRING XREFS =====")
    for label,va in [
        ("build_button",BUILD_BUTTON_VA),
        ("template_build_button",TEMPLATE_BUILD_BUTTON_VA),
        ("STR_BP_READY_TO_BUILD",READY_TO_BUILD_VA),
        ("STR_BP_HINT_TO_BUILD",HINT_TO_BUILD_VA),
    ]:
        refs=[p for p in find_all(d,struct.pack("<I",va)) if is_exec_file(p,secs)]
        w(f"[{label}] VA=0x{va:08X} executableRefs={len(refs)}")
        for p in refs:
            fs=prologue(d,p); fva=f2v(fs,ib,secs) if fs is not None else None
            w(f" refFile=0x{p:08X} refVA=0x{f2v(p,ib,secs):08X} containingFn={('0x%08X'%fva) if fva else 'N/A'}")
            lines.extend(dump(d,p-64,p+128))
        w("")

    w("===== MEMBER +0x90 / +0x94 USERS =====")
    h90=member_hits(d,0x90,ib,secs); h94=member_hits(d,0x94,ib,secs)
    byfn=defaultdict(lambda:{"90":[],"94":[]})
    for p,pva,fs,fva in h90:
        if fva is not None: byfn[fva]["90"].append(p)
    for p,pva,fs,fva in h94:
        if fva is not None: byfn[fva]["94"].append(p)
    both=[(fva,v) for fva,v in byfn.items() if v["90"] and v["94"]]
    # Prioritize the GarageBottomBarWidget code region, but keep all exact pair users.
    both.sort(key=lambda x:(0 if 0x00960000<=x[0]<=0x00980000 else 1,x[0]))
    w(f"FunctionsWithBoth={len(both)}")
    for fva,v in both[:160]:
        fs=v2f(fva,ib,secs); fe=next_prologue(d,fs,0x4000) if fs is not None else None
        if fs is None: continue
        vcs=virtual_calls_in_fn(d,fs,min(fe,fs+0x800))
        interesting=[(p,slot) for p,slot,_ in vcs if slot not in (4,8)]
        w(f"fn=0x{fva:08X} file=0x{fs:08X} refs90={','.join('0x%08X'%x for x in v['90'])} refs94={','.join('0x%08X'%x for x in v['94'])} virtualNonRef={','.join('0x%X@0x%08X'%(slot,p) for p,slot in interesting[:24])}")
        lines.extend(dump(d,fs,min(fe,fs+0x500)))
    w("")

    w("===== FOCUSED FUNCTION BODIES =====")
    for name,va in TARGETS.items():
        write_function_section(lines,d,name,va,ib,secs)
    w("")

    w("===== DIRECT CALLERS OF OWNER/LOOKUP HELPERS =====")
    for name in ["gbbw_base_ctor","weak_resolve_00902060","weak_resolve_00902140","weak_resolve_00902220","ui_lookup_00934890"]:
        va=TARGETS[name]
        callers=direct_callers(d,va,ib,secs)
        w(f"[{name}] VA=0x{va:08X} callers={len(callers)}")
        for p,fs in callers[:120]:
            fva=f2v(fs,ib,secs) if fs is not None else None
            w(f" callFile=0x{p:08X} callVA=0x{f2v(p,ib,secs):08X} callerFn={('0x%08X'%fva) if fva else 'N/A'}")
            lines.extend(dump(d,p-56,p+112))
        w("")

    w("===== FUNCTION POINTER / DATA REFS TO GBBW VIRTUAL METHODS =====")
    methods={}
    for label,vva in [("A",VTABLE_A),("B",VTABLE_B)]:
        for i,slot,va,fo in method_table(d,vva,ib,secs,16):
            methods[(label,slot)]=va
    for (label,slot),va in methods.items():
        refs=find_all(d,struct.pack("<I",va))
        data=[p for p in refs if not is_exec_file(p,secs)]
        execs=[p for p in refs if is_exec_file(p,secs)]
        w(f"{label} slot=0x{slot:02X} method=0x{va:08X} dataRefs={len(data)} execImmediateRefs={len(execs)}")
        for p in data[:40]:
            w(f" dataFile=0x{p:08X} dataVA={('0x%08X'%f2v(p,ib,secs)) if f2v(p,ib,secs) else 'N/A'}")
        for p in execs[:40]:
            fs=prologue(d,p); fva=f2v(fs,ib,secs) if fs is not None else None
            w(f" execRefFile=0x{p:08X} callerFn={('0x%08X'%fva) if fva else 'N/A'}")
            lines.extend(dump(d,p-48,p+80))
    w("")

    obj={
        "phase":"66-build-button-callback-binding",
        "phase65_reverted":reverted,
        "ams_sha256_before":before,
        "ams_sha256":after,
        "stable_sha_expected":STABLE_SHA,
        "functions_with_both_90_94":len(both),
        "global_isonline":"FALSE",
        "new_gameplay_patch":False,
        "report":str(report),
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*100)
    print(" PHASE 66 BUILD_BUTTON CALLBACK BINDING MAP READY")
    print("="*100)
    print("Phase65 reverted:",reverted)
    print("AMS SHA256:",after)
    print("Global IsOnline remains FALSE.")
    print("No new gameplay patch was applied.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
