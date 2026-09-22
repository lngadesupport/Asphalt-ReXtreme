#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

GS_VTABLE=0x0186A9CC
GS_CTORS=[0x00E00B20,0x00E0E8D0]
GS_SLOT_DC=0x00ABE7E0
GBBW_FACTORY=0x00A6C7F0
GBBW_CTOR=0x0096EB10
GBBW_BASE_CTOR=0x00964830
BUILD_HANDLER=0x00A87960
BUILD_CALLBACK=0x00973C90

GS_FIELDS=[0x354,0x358,0x35C,0x360]
GBBW_OWNER_FIELDS=[0x04,0x08]
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8v(x): return x-256 if x>=128 else x
def i32(b,o): return struct.unpack_from("<i",b,o)[0]
def sha(b): return hashlib.sha256(b).hexdigest()

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
            vs=u32(d,o+8),va=u32(d,o+12),rs=u32(d,o+16),
            raw=u32(d,o+20),ch=u32(d,o+36)
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

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:
            return bool(s["ch"]&0x20000000)
    return False

def next_prologue(d,start,limit=0x10000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def prev_prologue(d,near,limit=0x8000):
    lo=max(0,near-limit)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC":return p
    return None

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def method_table(d,vva,ib,secs,count=128):
    vf=v2f(vva,ib,secs);out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        if not is_exec_va(va,ib,secs):break
        out.append((i,i*4,va))
    return out

def detect_this_reg(d,fs,fe):
    lim=min(fe,fs+0x90)
    pats=[(b"\x8B\xF1","esi"),(b"\x8B\xF9","edi"),(b"\x8B\xD9","ebx"),(b"\x8B\xC1","eax")]
    best=None
    for pat,r in pats:
        p=d.find(pat,fs,lim)
        if p>=0 and (best is None or p<best[0]):best=(p,r)
    return best[1] if best else "ecx"

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8v(d[p+2]),3
    if mod==2 and p+6<=fe:return rm,i32(d,p+2),6
    return None

def classify(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    if op==0xFF and ext==6:return "READ"
    return "MEM"

def scan_fields(d,fs,fe,thisreg,fields):
    rid=REGS.index(thisreg)
    rows=[];p=fs
    while p+3<=fe:
        op=d[p]
        if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
            p+=1;continue
        dec=decode_mem(d,p,fe)
        if not dec:
            p+=1;continue
        rm,disp,ln=dec
        if rm==rid and disp in fields:
            rows.append((p,disp,classify(op,d[p+1]),op,d[p+1]))
        p+=ln
    return rows

def direct_calls(d,fs,fe,ib,secs):
    out=[];p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,ib,secs):out.append((p,dst))
            p+=5;continue
        p+=1
    return out

def direct_callers(d,target,ib,secs):
    rows=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    pf=prev_prologue(d,p)
                    rows.append((p,f2v(pf,ib,secs) if pf is not None else None))
                    p+=5;continue
            p+=1
    return rows

def global_disp_refs(d,disp,secs):
    # Conservative scan for common x86 memory operands with mod=2 disp32 equal to target.
    rows=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-6,s["raw"]+s["rs"]-6)
        while p<=end:
            op=d[p]
            if op in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
                mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
                if mod==2 and rm!=4 and i32(d,p+2)==disp:
                    rows.append((p,REGS[rm],classify(op,mr),op,mr))
                    p+=6;continue
            p+=1
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for n,o,e in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    methods=method_table(d,GS_VTABLE,ib,secs,128)

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE80_OWNER_PAIR_TYPE"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE80-OWNER-PAIR-TYPE.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*118)
    w(" ReXtreme Phase 80 - GS_Garage+0x354/+0x358 owner pair -> GBBW+0x04/+0x08")
    w("="*118)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")

    # GS +0xDC exact path.
    sf=v2f(GS_SLOT_DC,ib,secs);se=next_prologue(d,sf,0x2000)
    w("===== GS_GARAGE SLOT +0xDC -> FACTORY =====")
    w(f"VA=0x{GS_SLOT_DC:08X} file=0x{sf:08X} end=0x{se:08X}")
    lines.extend(dump(d,sf,se))
    w("Expected key sequence: lea <reg>,[this+0x354] then pass to 0x00A6C7F0.")
    w("")

    # Factory exact body.
    ff=v2f(GBBW_FACTORY,ib,secs);fe=next_prologue(d,ff,0x3000)
    w("===== GBBW FACTORY =====")
    w(f"VA=0x{GBBW_FACTORY:08X} file=0x{ff:08X} end=0x{fe:08X}")
    lines.extend(dump(d,ff,fe))
    for p,dst in direct_calls(d,ff,fe,ib,secs):
        tag=" GBBW_CTOR" if dst==GBBW_CTOR else ""
        w(f"CALL file=0x{p:08X} -> VA=0x{dst:08X}{tag}")
    w("")

    # Base ctor proof of +4/+8.
    bf=v2f(GBBW_BASE_CTOR,ib,secs);be=next_prologue(d,bf,0x1000)
    w("===== GBBW BASE CTOR OWNER STORAGE =====")
    w(f"VA=0x{GBBW_BASE_CTOR:08X} file=0x{bf:08X} end=0x{be:08X}")
    lines.extend(dump(d,bf,be))
    btr=detect_this_reg(d,bf,be)
    for row in scan_fields(d,bf,be,btr,set(GBBW_OWNER_FIELDS)):
        p,disp,kind,op,mr=row
        w(f"{kind} GBBW+0x{disp:X} file=0x{p:08X} op=0x{op:02X} modrm=0x{mr:02X}")
    w("")

    # All GS vtable method accesses to owner pair.
    byfield=defaultdict(list)
    w("===== GS_GARAGE VTABLE METHOD ACCESSES TO +0x354/+0x358/+0x35C/+0x360 =====")
    for idx,slot,va in methods:
        mf=v2f(va,ib,secs)
        if mf is None:continue
        me=next_prologue(d,mf,0x7000)
        tr=detect_this_reg(d,mf,me)
        for row in scan_fields(d,mf,me,tr,set(GS_FIELDS)):
            p,disp,kind,op,mr=row
            byfield[disp].append((idx,slot,va,p,kind,tr,op,mr))
    for field in GS_FIELDS:
        rows=byfield[field]
        w(f"[GS+0x{field:X}] uses={len(rows)}")
        for idx,slot,va,p,kind,tr,op,mr in rows:
            tags=[]
            if va==GS_SLOT_DC:tags.append("SLOT_DC")
            if va==BUILD_HANDLER:tags.append("BUILD_HANDLER")
            w(f" slot=0x{slot:X} method=0x{va:08X} kind={kind} file=0x{p:08X} this={tr} tags={','.join(tags) if tags else '-'}")
            if kind in ("WRITE","ADDRESS","READ_WRITE") or field in (0x354,0x358):
                lines.extend(dump(d,p-64,p+128))
        w("")

    # GS constructors - dump/accesses independently (not necessarily vtable method entries).
    ctor_rows=[]
    w("===== GS_GARAGE CONSTRUCTORS OWNER-PAIR ACCESSES =====")
    for cva in GS_CTORS:
        cf=v2f(cva,ib,secs)
        if cf is None:
            w(f"ctor 0x{cva:08X}: not mapped")
            continue
        ce=next_prologue(d,cf,0x12000)
        tr=detect_this_reg(d,cf,ce)
        w(f"[ctor 0x{cva:08X}] file=0x{cf:08X} end=0x{ce:08X} this={tr}")
        acc=scan_fields(d,cf,ce,tr,set(GS_FIELDS))
        for p,disp,kind,op,mr in acc:
            ctor_rows.append((cva,p,disp,kind,tr))
            w(f" {kind} GS+0x{disp:X} file=0x{p:08X}")
            lines.extend(dump(d,p-80,p+144))
        w("")

    # Broader global displacement references to +354/+358, then score those in GS methods/ctors.
    global_rows={}
    w("===== GLOBAL DISP32 REFERENCES TO 0x354 / 0x358 =====")
    gs_method_vas={va for _,_,va in methods}
    for field in (0x354,0x358):
        rows=global_disp_refs(d,field,secs)
        global_rows[field]=rows
        w(f"[disp 0x{field:X}] refs={len(rows)}")
        for p,base,kind,op,mr in rows[:800]:
            pf=prev_prologue(d,p)
            pva=f2v(pf,ib,secs) if pf is not None else None
            tag=[]
            if pva in gs_method_vas:tag.append("GS_VMETHOD")
            if pva in GS_CTORS:tag.append("GS_CTOR")
            w(f" file=0x{p:08X} VA=0x{f2v(p,ib,secs):08X} fn={('0x%08X'%pva) if pva else 'N/A'} base={base} kind={kind} tags={','.join(tag) if tag else '-'}")
        w("")

    # GBBW methods accessing +4/+8: tells us whether owner pair is consumed anywhere.
    # Vtable known first entries from prior map; scan conservative first 24 slots.
    gf=v2f(0x01831854,ib,secs)
    gmethods=[]
    if gf is not None:
        for i in range(24):
            va=u32(d,gf+i*4)
            if not is_exec_va(va,ib,secs):break
            gmethods.append((i,i*4,va))
    owner_reads=[]
    w("===== GBBW METHODS USING OWNER PAIR +0x04/+0x08 =====")
    for idx,slot,va in gmethods:
        mf=v2f(va,ib,secs);me=next_prologue(d,mf,0x5000)
        tr=detect_this_reg(d,mf,me)
        acc=scan_fields(d,mf,me,tr,set(GBBW_OWNER_FIELDS))
        for p,disp,kind,op,mr in acc:
            owner_reads.append((slot,va,p,disp,kind,tr))
            w(f"gbSlot=0x{slot:X} method=0x{va:08X} {kind} +0x{disp:X} file=0x{p:08X} this={tr}")
            lines.extend(dump(d,p-48,p+112))
    if not owner_reads:w("none")
    w("")

    # Callers of build handler, for controlled bypass feasibility.
    bh_callers=direct_callers(d,BUILD_HANDLER,ib,secs)
    w("===== BUILD HANDLER DIRECT CALLERS =====")
    w(f"Count={len(bh_callers)}")
    for p,pva in bh_callers:
        w(f"callFile=0x{p:08X} parentFn={('0x%08X'%pva) if pva else 'N/A'}")
    w("")

    owner_write_count=sum(1 for rows in byfield.values() for r in rows if r[4] in ("WRITE","READ_WRITE"))
    pair_write_count=sum(1 for field in (0x354,0x358) for r in byfield[field] if r[4] in ("WRITE","READ_WRITE"))
    ctor_pair_writes=[r for r in ctor_rows if r[2] in (0x354,0x358) and r[3] in ("WRITE","READ_WRITE")]

    obj={
        "phase":"80-owner-pair-type",
        "ams_sha256":cursha,
        "gs_owner_pair":["0x354","0x358"],
        "gbbw_owner_pair":["0x04","0x08"],
        "gs_owner_pair_vmethod_writes":pair_write_count,
        "gs_owner_pair_ctor_writes":[
            {"ctor":f"0x{x[0]:08X}","file":f"0x{x[1]:08X}","field":f"0x{x[2]:X}","kind":x[3]}
            for x in ctor_pair_writes
        ],
        "gbbw_owner_pair_method_uses":[
            {"slot":f"0x{x[0]:X}","method_va":f"0x{x[1]:08X}","file":f"0x{x[2]:08X}","field":f"0x{x[3]:X}","kind":x[4]}
            for x in owner_reads
        ],
        "build_handler_direct_callers":len(bh_callers),
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*118)
    print(" PHASE 80 OWNER PAIR TYPE MAP READY")
    print("="*118)
    print("GS owner-pair vmethod writes:",pair_write_count)
    print("GS owner-pair ctor writes:",len(ctor_pair_writes))
    print("GBBW owner-pair method uses:",len(owner_reads))
    print("Build-handler direct callers:",len(bh_callers))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
