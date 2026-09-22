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

GBBW_VTABLE=0x01831854
CTOR=0x0096EB10
DTOR=0x0096EDF0
BUILD_CALLBACK=0x00973C90
INVOKE_HELPER=0x00936BE0
BUILD_HANDLER=0x00A87960
FIELDS=[0x34,0x3C,0x44,0x4C,0x54,0x5C,0x64]
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]
def sha(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c); n=u16(d,pe+6); osz=u16(d,pe+20); opt=pe+24
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8),va=u32(d,o+12),rs=u32(d,o+16),raw=u32(d,o+20),ch=u32(d,o+36)))
    return ib,secs

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]: return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"]<=rva<s["va"]+max(s["vs"],s["rs"]): return s["raw"]+(rva-s["va"])
    return None

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:return bool(s["ch"]&0x20000000)
    return False

def prologue(d,near,back=0x5000):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return near

def next_prologue(d,start,limit=0x5000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def method_table(d,vva,ib,secs,count=128):
    vf=v2f(vva,ib,secs); out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        if not is_exec_va(va,ib,secs):break
        out.append((i,i*4,va))
    return out

def detect_this_reg(d,fs,fe):
    # Common x86 member-function prologues: mov esi,ecx / mov edi,ecx / mov ebx,ecx.
    lim=min(fe,fs+0x60)
    pats={b"\x8B\xF1":"esi",b"\x8B\xF9":"edi",b"\x8B\xD9":"ebx",b"\x8B\xC1":"eax"}
    best=None
    for pat,r in pats.items():
        p=d.find(pat,fs,lim)
        if p>=0 and (best is None or p<best[0]):best=(p,r)
    return best[1] if best else "ecx"

def classify(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    return "MEM"

def scan_member_access(d,fs,fe,this_reg):
    rid=REGS.index(this_reg)
    out=[];p=fs
    while p+3<=fe:
        op=d[p]
        if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
            p+=1;continue
        mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
        if rm!=rid or rm==4:
            p+=1;continue
        disp=None;ln=0
        if mod==1:
            disp=d[p+2];ln=3
        elif mod==2 and p+6<=fe:
            disp=u32(d,p+2);ln=6
        if disp in FIELDS:
            out.append((p,disp,classify(op,mr),op,mr))
        p+=ln if ln else 1
    return out

def direct_target_after(d,p,search=0x30,ib=None,secs=None):
    z=min(len(d)-5,p+search)
    q=p+3
    while q<=z:
        if d[q]==0xE8:
            sva=f2v(q,ib,secs)
            if sva is not None:
                return q,(sva+5+i32(d,q+1))&0xffffffff
        q+=1
    return None

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
                    out.append((p,f2v(fs,ib,secs)))
                    p+=5;continue
            p+=1
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    d=ams.read_bytes()
    for n,o,e in [("P53",P53_OFF,P53),("P54",P54_OFF,P54),("P55",P55_OFF,P55),
                  ("P63rev",P63_OFF,PRE63),("P65rev",P65_OFF,PRE65),
                  ("GlobalFalse",GLOBAL_OFF,GLOBAL_FALSE),("Popup",POPUP_OFF,POPUP)]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA {cursha}")

    ib,secs=parse_pe(d)
    methods=method_table(d,GBBW_VTABLE,ib,secs,96)
    # Include ctor/dtor even if not in first method run.
    targets=[]
    seen=set()
    for idx,slot,va in methods:
        if va not in seen: targets.append((f"vslot_0x{slot:X}",slot,va));seen.add(va)
    for name,va in [("ctor",CTOR),("dtor",DTOR),("build_callback",BUILD_CALLBACK),("invoke_helper",INVOKE_HELPER)]:
        if va not in seen:targets.append((name,None,va));seen.add(va)

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE71_GBBW_SIGNAL_LIFECYCLE"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE71-GBBW-SIGNAL-LIFECYCLE.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*108)
    w(" ReXtreme Phase 71 - GarageBottomBarWidget signal/member lifecycle")
    w("="*108)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w(f"GBBW_vtable=0x{GBBW_VTABLE:08X}")
    w(f"methods={len(methods)}")
    w("target fields="+",".join(f"+0x{x:X}" for x in FIELDS))
    w("")

    all_hits=[]
    helper_targets=defaultdict(list)
    for label,slot,va in targets:
        fs=v2f(va,ib,secs)
        if fs is None:continue
        # honor exact target address as start if prologue at/near it; otherwise nearest previous.
        realfs=prologue(d,fs,0x80)
        if realfs>fs or fs-realfs>0x80: realfs=fs
        fe=next_prologue(d,realfs,0x4000)
        thisreg=detect_this_reg(d,realfs,fe)
        hits=scan_member_access(d,realfs,fe,thisreg)
        if not hits:continue
        w(f"===== {label} VA=0x{va:08X} file=0x{realfs:08X} end=0x{fe:08X} this={thisreg} =====")
        for p,disp,kind,op,mr in hits:
            w(f"member +0x{disp:X} {kind} file=0x{p:08X} VA=0x{f2v(p,ib,secs):08X} op=0x{op:02X} modrm=0x{mr:02X}")
            all_hits.append((label,slot,va,p,disp,kind,thisreg))
            if kind=="ADDRESS":
                nxt=direct_target_after(d,p,0x50,ib,secs)
                if nxt:
                    cp,dst=nxt
                    helper_targets[dst].append((label,slot,va,p,disp,cp))
                    w(f"  ADDRESS_NEXT_CALL file=0x{cp:08X} -> VA=0x{dst:08X}")
            lines.extend(dump(d,p-48,p+96))
        w("")

    w("===== +0x44 ONLY =====")
    h44=[x for x in all_hits if x[4]==0x44]
    w(f"Count={len(h44)}")
    for label,slot,va,p,disp,kind,tr in h44:
        w(f"{label} methodVA=0x{va:08X} slot={('0x%X'%slot) if slot is not None else 'N/A'} kind={kind} file=0x{p:08X} this={tr}")
    w("")

    w("===== HELPERS RECEIVING ADDRESSES OF SIGNAL FIELDS =====")
    for dst,rows in sorted(helper_targets.items(), key=lambda kv:(-len(kv[1]),kv[0])):
        w(f"helperVA=0x{dst:08X} refs={len(rows)}")
        for label,slot,va,p,disp,cp in rows:
            w(f" from={label} method=0x{va:08X} field=+0x{disp:X} leaFile=0x{p:08X} callFile=0x{cp:08X}")
        callers=direct_callers(d,dst,ib,secs)
        w(f" directCallersTotal={len(callers)}")
        hf=v2f(dst,ib,secs)
        if hf is not None:
            he=next_prologue(d,hf,0x1800)
            lines.extend(dump(d,hf,min(he,hf+0x700)))
        w("")

    w("===== BUILD CALLBACK / INVOKE HELPER =====")
    for va,name in [(BUILD_CALLBACK,"build_callback"),(INVOKE_HELPER,"invoke_helper")]:
        fs=v2f(va,ib,secs);fe=next_prologue(d,fs,0x1800)
        w(f"[{name}] VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X}")
        lines.extend(dump(d,fs,fe))
        w(f" directCallers={len(direct_callers(d,va,ib,secs))}")
    w("")

    # Rank functions that actually mutate/address +0x44.
    mut=[]
    for x in h44:
        kind=x[5]
        score={"WRITE":100,"READ_WRITE":90,"ADDRESS":80,"READ":20,"CALL_MEM":10,"MEM":5}.get(kind,0)
        mut.append((score,x))
    mut.sort(key=lambda t:(-t[0],t[1][3]))
    w("===== RANKED +0x44 CLASS-MEMBER CANDIDATES =====")
    for score,x in mut:
        label,slot,va,p,disp,kind,tr=x
        w(f"score={score} {kind} label={label} methodVA=0x{va:08X} slot={('0x%X'%slot) if slot is not None else 'N/A'} file=0x{p:08X}")
    w("")

    obj={
      "phase":"71-gbbw-signal-lifecycle",
      "ams_sha256":cursha,
      "gbbw_method_count":len(methods),
      "field44_hits":[
        {"label":x[0],"slot":f"0x{x[1]:X}" if x[1] is not None else None,
         "method_va":f"0x{x[2]:08X}","file":f"0x{x[3]:08X}","kind":x[5]}
        for x in h44
      ],
      "address_helpers":[
        {"helper_va":f"0x{dst:08X}","refs":len(rows)}
        for dst,rows in sorted(helper_targets.items(),key=lambda kv:(-len(kv[1]),kv[0]))
      ],
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")
    print("="*108)
    print(" PHASE 71 GBBW SIGNAL LIFECYCLE READY")
    print("="*108)
    print("GBBW methods:",len(methods))
    print("+0x44 class-member hits:",len(h44))
    if mut:
        top=mut[0][1]
        print("Top +0x44:",top[5],top[0],hex(top[2]),hex(top[3]))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
