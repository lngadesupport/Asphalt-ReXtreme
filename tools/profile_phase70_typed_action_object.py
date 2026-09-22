#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict, deque

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

TARGET_VTABLE=0x01832394
TARGET_CTOR=0x00976B60
TARGET_PARENT=0x00A6CA80
RESOLVER=0x00902140
GBBW_VTABLE=0x01831854
GS_GARAGE_VTABLE=0x0186A9CC
BUILD_HANDLER=0x00A87960
BUILD_CALLBACK=0x00973C90

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]
def sha(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4] != b"PE\0\0": raise RuntimeError("invalid PE")
    n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
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

def is_exec_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return bool(s["ch"]&0x20000000)
    return False

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    return f is not None and is_exec_file(f,secs)

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
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
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def ascii_z(d,off,limit=300):
    if off is None or not(0<=off<len(d)): return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("utf-8","replace")
    except:return ""
    if not s:return ""
    printable=sum((32<=ord(c)<127) or c in "\t\r\n" for c in s)
    return s if printable>=max(1,int(len(s)*.85)) else ""

def rtti_name(d,vva,ib,secs):
    vf=v2f(vva,ib,secs)
    if vf is None or vf<4:return None
    col=v2f(u32(d,vf-4),ib,secs)
    if col is None or col+20>len(d):return None
    td=v2f(u32(d,col+12),ib,secs)
    if td is None:return None
    return ascii_z(d,td+8)

def direct_calls(d,fn_va,ib,secs,limit=0x5000):
    fs=v2f(fn_va,ib,secs)
    if fs is None:return []
    fe=next_prologue(d,fs,limit)
    out=[];p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,dst))
            p+=5;continue
        p+=1
    return out

def direct_callers(d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    fs=prologue(d,p)
                    out.append((p,f2v(fs,ib,secs) if fs is not None else None))
                    p+=5;continue
            p+=1
    return out

def exec_refs_to_imm(d,va,secs):
    pat=struct.pack("<I",va)
    return [p for p in find_all(d,pat) if is_exec_file(p,secs)]

def scan_push_strings_before(d,call_file,ib,secs,back=0x100):
    rows=[]
    lo=max(0,call_file-back)
    p=lo
    while p<call_file-4:
        if d[p]==0x68:
            va=u32(d,p+1)
            fo=v2f(va,ib,secs)
            if fo is not None:
                s=ascii_z(d,fo)
                if s:
                    rows.append((p,va,s))
            p+=5
        else:
            p+=1
    return rows

def infer_pair_store_after(d,call_file,max_ahead=0x80):
    z=min(len(d),call_file+5+max_ahead)
    # look for paired stores [reg+off], [reg+off+4]
    hits=[]
    p=call_file+5
    while p+3<z:
        # mov [r32+disp8], reg32 = 89 /r
        if d[p]==0x89:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; src=(mr>>3)&7
            if mod==1 and rm!=4:
                disp=d[p+2]
                hits.append((p,rm,src,disp))
                p+=3; continue
        p+=1
    # return the first adjacent-ish pair with offsets 4 apart
    for a in hits:
        for b in hits:
            if b[0]>a[0] and b[0]-a[0] <= 0x20 and b[1]==a[1] and b[3]==a[3]+4:
                return a,b
    return None

def method_table(d,vva,ib,secs,count=128):
    vf=v2f(vva,ib,secs)
    out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        if not is_exec_va(va,ib,secs):break
        out.append((i,i*4,va))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        cur=d[off:off+len(exp)]
        if cur!=exp: raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE70_TYPED_ACTION_OBJECT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE70-TYPED-ACTION-OBJECT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    cls=rtti_name(d,TARGET_VTABLE,ib,secs)

    w("="*104)
    w(" ReXtreme Phase 70 - typed action object / field +0x44 source map")
    w("="*104)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w(f"TargetCtor=0x{TARGET_CTOR:08X}")
    w(f"TargetVtable=0x{TARGET_VTABLE:08X}")
    w(f"TargetRTTI={cls!r}")
    w(f"TargetParent=0x{TARGET_PARENT:08X}")
    w("")

    w("===== TARGET VTABLE =====")
    for idx,slot,va in method_table(d,TARGET_VTABLE,ib,secs,48):
        w(f"index={idx:02d} slot=0x{slot:02X} VA=0x{va:08X}")
    w("")

    w("===== EXECUTABLE VTABLE INSTALL/REF SITES =====")
    refs=exec_refs_to_imm(d,TARGET_VTABLE,secs)
    w(f"Count={len(refs)}")
    for p in refs:
        fs=prologue(d,p)
        fva=f2v(fs,ib,secs) if fs is not None else None
        w(f"refFile=0x{p:08X} refVA=0x{f2v(p,ib,secs):08X} fn={('0x%08X'%fva) if fva else 'N/A'}")
        lines.extend(dump(d,p-80,p+160))
    w("")

    w("===== TARGET CONSTRUCTOR BODY =====")
    cf=v2f(TARGET_CTOR,ib,secs); ce=next_prologue(d,cf,0x3000)
    w(f"file=0x{cf:08X} end=0x{ce:08X}")
    lines.extend(dump(d,cf,ce))
    w("")

    w("===== RESOLVER CALLS INSIDE TARGET CONSTRUCTOR =====")
    resolver_rows=[]
    for p,dst in direct_calls(d,TARGET_CTOR,ib,secs,0x3000):
        if dst!=RESOLVER:continue
        sva=f2v(p,ib,secs)
        strings=scan_push_strings_before(d,p,ib,secs,0xB0)
        pair=infer_pair_store_after(d,p,0x90)
        w(f"callFile=0x{p:08X} callVA=0x{sva:08X} -> resolver 0x{RESOLVER:08X}")
        if strings:
            for sp,sva2,s in strings[-5:]:
                w(f"  priorPush file=0x{sp:08X} VA=0x{sva2:08X} string={s!r}")
        else:
            w("  priorPushString=none")
        pair_obj=None
        if pair:
            a,b=pair
            pair_obj={"first":a[3],"second":b[3]}
            w(f"  inferredPairStore=+0x{a[3]:X}/+0x{b[3]:X} firstFile=0x{a[0]:08X} secondFile=0x{b[0]:08X}")
            lines.extend(dump(d,p-64,b[0]+80))
        resolver_rows.append({
            "call_file":f"0x{p:08X}",
            "strings":[s for _,_,s in strings[-5:]],
            "pair":pair_obj
        })
    w("")

    w("===== FOCUS: PAIR +0x40/+0x44 =====")
    # Known exact sequence from Phase69, but validate on current bytes.
    focus=0x00576580
    lines.extend(dump(d,focus,0x00576630))
    # decode pushed absolute string at 0x0057658C-ish by scanning this region
    for p in range(focus,0x005765C8):
        if d[p]==0x68 and p+5<=len(d):
            va=u32(d,p+1);fo=v2f(va,ib,secs)
            s=ascii_z(d,fo) if fo is not None else ""
            if s:
                w(f"focusPush file=0x{p:08X} -> VA=0x{va:08X} string={s!r}")
    w("")

    w("===== TARGET CONSTRUCTOR DIRECT CALLERS =====")
    callers=direct_callers(d,TARGET_CTOR,ib,secs)
    w(f"Count={len(callers)}")
    for p,parent in callers:
        w(f"callFile=0x{p:08X} parentFn={('0x%08X'%parent) if parent else 'N/A'}")
        lines.extend(dump(d,p-96,p+160))
    w("")

    w("===== TARGET PARENT BODY =====")
    pf=v2f(TARGET_PARENT,ib,secs); pe=next_prologue(d,pf,0x5000)
    w(f"VA=0x{TARGET_PARENT:08X} file=0x{pf:08X} end=0x{pe:08X}")
    lines.extend(dump(d,pf,pe))
    w("")

    w("===== TARGET PARENT DIRECT CALLERS =====")
    pc=direct_callers(d,TARGET_PARENT,ib,secs)
    w(f"Count={len(pc)}")
    for p,parent in pc:
        w(f"callFile=0x{p:08X} parentFn={('0x%08X'%parent) if parent else 'N/A'}")
        lines.extend(dump(d,p-96,p+160))
    w("")

    w("===== GS_GARAGE VTABLE METHODS CALLING TARGET PARENT =====")
    gsm=method_table(d,GS_GARAGE_VTABLE,ib,secs,128)
    hits=[]
    for idx,slot,mva in gsm:
        for p,dst in direct_calls(d,mva,ib,secs,0x5000):
            if dst==TARGET_PARENT:
                hits.append((idx,slot,mva,p))
                w(f"gsSlot=0x{slot:X} methodVA=0x{mva:08X} callFile=0x{p:08X} -> 0x{TARGET_PARENT:08X}")
    if not hits:w("none")
    w("")

    w("===== GBBW/GS_GARAGE RELATION CHECK =====")
    w(f"GarageBottomBarWidgetRTTI={rtti_name(d,GBBW_VTABLE,ib,secs)!r}")
    w(f"GS_GarageRTTI={rtti_name(d,GS_GARAGE_VTABLE,ib,secs)!r}")
    w(f"BuildHandler=0x{BUILD_HANDLER:08X}")
    w(f"BuildCallback=0x{BUILD_CALLBACK:08X}")
    w("")

    obj={
        "phase":"70-typed-action-object",
        "ams_sha256":cursha,
        "target_vtable":f"0x{TARGET_VTABLE:08X}",
        "target_rtti":cls,
        "target_ctor":f"0x{TARGET_CTOR:08X}",
        "target_parent":f"0x{TARGET_PARENT:08X}",
        "resolver_calls":resolver_rows,
        "gs_garage_methods_calling_parent":[
            {"slot":f"0x{slot:X}","method_va":f"0x{mva:08X}","call_file":f"0x{p:08X}"}
            for idx,slot,mva,p in hits
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")

    print("="*104)
    print(" PHASE 70 TYPED ACTION OBJECT MAP READY")
    print("="*104)
    print("RTTI:",cls)
    print("Resolver calls:",len(resolver_rows))
    print("GS_Garage methods calling parent:",len(hits))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
