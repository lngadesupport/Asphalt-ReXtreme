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

GS_GARAGE_VTABLE=0x0186A9CC
GS_GARAGE_BOTTOMBAR_FACTORY_METHOD=0x00ABE7E0
GBBW_FACTORY=0x00A6C7F0
GBBW_CTOR=0x0096EB10
GBBW_VTABLE=0x01831854
BUILD_HANDLER=0x00A87960
BUILD_CALLBACK=0x00973C90

REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8(b,o):
    x=b[o]; return x-256 if x>=128 else x
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
            vs=u32(d,o+8),va=u32(d,o+12),rs=u32(d,o+16),raw=u32(d,o+20),ch=u32(d,o+36)
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

def next_prologue(d,start,limit=0x7000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def method_table(d,vva,ib,secs,count=128):
    vf=v2f(vva,ib,secs)
    out=[]
    if vf is None:return out
    for i in range(count):
        va=u32(d,vf+i*4)
        if not is_exec_va(va,ib,secs): break
        out.append((i,i*4,va))
    return out

def detect_this_reg(d,fs,fe):
    lim=min(fe,fs+0x80)
    pats=[
        (b"\x8B\xF1","esi"),
        (b"\x8B\xF9","edi"),
        (b"\x8B\xD9","ebx"),
        (b"\x8B\xC1","eax"),
    ]
    best=None
    for pat,r in pats:
        p=d.find(pat,fs,lim)
        if p>=0 and (best is None or p<best[0]): best=(p,r)
    return best[1] if best else "ecx"

def direct_calls(d,fs,fe,ib,secs):
    out=[]; p=fs
    while p+5<=fe:
        if d[p]==0xE8:
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,ib,secs): out.append((p,dst))
            p+=5; continue
        p+=1
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
                    fs=p
                    lo=max(s["raw"],p-0x6000)
                    while fs>lo and d[fs:fs+3]!=b"\x55\x8B\xEC": fs-=1
                    out.append((p,f2v(fs,ib,secs) if d[fs:fs+3]==b"\x55\x8B\xEC" else None))
                    p+=5; continue
            p+=1
    return out

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8(d,p+2),3
    if mod==2 and p+6<=fe:return rm,i32(d,p+2),6
    return None

def classify_mem(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    return "MEM"

def member_accesses(d,fs,fe,thisreg):
    rid=REGS.index(thisreg)
    out=[];p=fs
    while p+3<=fe:
        op=d[p]
        if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
            p+=1;continue
        dec=decode_mem(d,p,fe)
        if not dec:
            p+=1;continue
        rm,disp,ln=dec
        if rm==rid:
            out.append((p,disp,classify_mem(op,d[p+1]),op,d[p+1]))
        p+=ln
    return out

def scan_stack_setup_before(d,callp,fs,ib,secs,back=0xC0):
    lo=max(fs,callp-back)
    rows=[]
    p=lo
    while p<callp:
        b=d[p]
        if 0x50<=b<=0x57:
            rows.append((p,"PUSH_REG",REGS[b-0x50]))
            p+=1; continue
        if b==0x68 and p+5<=callp:
            imm=u32(d,p+1)
            rows.append((p,"PUSH_IMM",f"0x{imm:08X}"))
            p+=5; continue
        if b==0x6A and p+2<=callp:
            rows.append((p,"PUSH_IMM8",str(i8(d,p+1))))
            p+=2; continue
        if b==0xFF and p+3<=callp:
            mr=d[p+1]; ext=(mr>>3)&7
            dec=decode_mem(d,p,callp)
            if ext==6 and dec:
                rm,disp,ln=dec
                rows.append((p,"PUSH_MEM",f"[{REGS[rm]}{disp:+#x}]"))
                p+=ln; continue
        if b==0x8D and p+3<=callp:
            mr=d[p+1]; dst=(mr>>3)&7
            dec=decode_mem(d,p,callp)
            if dec:
                rm,disp,ln=dec
                rows.append((p,"LEA",f"{REGS[dst]}=[{REGS[rm]}{disp:+#x}]"))
                p+=ln;continue
        p+=1
    return rows

def search_candidate_field_usage(d,methods,candidate_offsets,ib,secs):
    rows=[]
    for idx,slot,va in methods:
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x5000)
        tr=detect_this_reg(d,fs,fe)
        for p,disp,kind,op,mr in member_accesses(d,fs,fe,tr):
            if disp in candidate_offsets:
                rows.append((idx,slot,va,p,disp,kind,tr))
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    for name,off,exp in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[off:off+len(exp)]!=exp:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:
        raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE74_GS_GARAGE_GBBW_STORAGE"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE74-GS-GARAGE-GBBW-STORAGE.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*112)
    w(" ReXtreme Phase 74 - GS_Garage -> GarageBottomBarWidget storage/owner map")
    w("="*112)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")

    # Analyze GS_Garage +0xDC method.
    fs=v2f(GS_GARAGE_BOTTOMBAR_FACTORY_METHOD,ib,secs)
    fe=next_prologue(d,fs,0x5000)
    tr=detect_this_reg(d,fs,fe)
    w("===== GS_GARAGE +0xDC METHOD =====")
    w(f"VA=0x{GS_GARAGE_BOTTOMBAR_FACTORY_METHOD:08X} file=0x{fs:08X} end=0x{fe:08X} this={tr}")
    lines.extend(dump(d,fs,fe))
    w("-- direct calls --")
    call_to_factory=None
    for p,dst in direct_calls(d,fs,fe,ib,secs):
        tag=""
        if dst==GBBW_FACTORY: tag="GBBW_FACTORY"
        elif dst==GBBW_CTOR: tag="GBBW_CTOR"
        w(f"CALL file=0x{p:08X} -> VA=0x{dst:08X} {tag}")
        if dst==GBBW_FACTORY: call_to_factory=p
    w("-- this-member accesses --")
    member_rows=member_accesses(d,fs,fe,tr)
    candidate_offsets=set()
    for p,disp,kind,op,mr in member_rows:
        w(f"{kind} this{disp:+#x} file=0x{p:08X} VA=0x{f2v(p,ib,secs):08X} op=0x{op:02X} modrm=0x{mr:02X}")
        if -0x1000 < disp < 0x2000 and disp not in (0,):
            candidate_offsets.add(disp)
    w("")

    if call_to_factory is not None:
        w("===== STACK/ARG SETUP BEFORE 0x00A6C7F0 =====")
        for p,k,v in scan_stack_setup_before(d,call_to_factory,fs,ib,secs,0x120):
            w(f"file=0x{p:08X} {k} {v}")
        lines.extend(dump(d,max(fs,call_to_factory-0x140),min(fe,call_to_factory+0x120)))
        w("")

    w("===== GBBW FACTORY BODY =====")
    ff=v2f(GBBW_FACTORY,ib,secs); ffe=next_prologue(d,ff,0x5000)
    w(f"VA=0x{GBBW_FACTORY:08X} file=0x{ff:08X} end=0x{ffe:08X}")
    lines.extend(dump(d,ff,ffe))
    w("-- calls --")
    for p,dst in direct_calls(d,ff,ffe,ib,secs):
        tag=" GBBW_CTOR" if dst==GBBW_CTOR else ""
        w(f"CALL file=0x{p:08X} -> VA=0x{dst:08X}{tag}")
    w("")

    # Candidate fields: keep plausible positive GS_Garage offsets from +0xDC method.
    candidate_offsets={x for x in candidate_offsets if 0x20<=x<=0x1000}
    w("===== CANDIDATE GS_GARAGE FIELDS FROM +0xDC =====")
    w("Offsets="+(",".join(f"0x{x:X}" for x in sorted(candidate_offsets)) if candidate_offsets else "none"))
    w("")

    methods=method_table(d,GS_GARAGE_VTABLE,ib,secs,128)
    reuse=search_candidate_field_usage(d,methods,candidate_offsets,ib,secs) if candidate_offsets else []

    w("===== SAME FIELDS REUSED BY OTHER GS_GARAGE METHODS =====")
    w(f"Count={len(reuse)}")
    byoff=defaultdict(list)
    for row in reuse: byoff[row[4]].append(row)
    for off in sorted(byoff):
        rows=byoff[off]
        w(f"[field +0x{off:X}] uses={len(rows)}")
        for idx,slot,va,p,disp,kind,tr2 in rows[:120]:
            marker=""
            if va==BUILD_HANDLER: marker=" BUILD_HANDLER"
            w(f" slot=0x{slot:X} method=0x{va:08X}{marker} kind={kind} file=0x{p:08X} this={tr2}")
            lines.extend(dump(d,p-48,p+96))
        w("")

    # Look for methods that reference the GBBW vtable immediate or factory directly.
    w("===== GS_GARAGE METHODS REFERENCING GBBW FACTORY/VTABLE =====")
    refs=[]
    for idx,slot,va in methods:
        mf=v2f(va,ib,secs)
        if mf is None:continue
        me=next_prologue(d,mf,0x5000)
        body=d[mf:me]
        for label,val in [("GBBW_VTABLE",GBBW_VTABLE),("GBBW_FACTORY",GBBW_FACTORY),("GBBW_CTOR",GBBW_CTOR),("BUILD_CALLBACK",BUILD_CALLBACK)]:
            pat=struct.pack("<I",val)
            pos=0
            while True:
                j=body.find(pat,pos)
                if j<0: break
                refs.append((idx,slot,va,mf+j,label,val))
                pos=j+1
        for cp,dst in direct_calls(d,mf,me,ib,secs):
            if dst in (GBBW_FACTORY,GBBW_CTOR):
                refs.append((idx,slot,va,cp,"DIRECT_CALL",dst))
    for idx,slot,va,p,label,val in refs:
        w(f"slot=0x{slot:X} method=0x{va:08X} file=0x{p:08X} {label}=0x{val:08X}")
        lines.extend(dump(d,p-64,p+112))
    if not refs:w("none")
    w("")

    # Build handler accesses to candidate fields.
    bf=v2f(BUILD_HANDLER,ib,secs); be=next_prologue(d,bf,0x4000)
    btr=detect_this_reg(d,bf,be)
    w("===== BUILD HANDLER FIELD CROSSCHECK =====")
    w(f"BuildHandler=0x{BUILD_HANDLER:08X} file=0x{bf:08X} this={btr}")
    bhits=[]
    for p,disp,kind,op,mr in member_accesses(d,bf,be,btr):
        if disp in candidate_offsets:
            bhits.append((p,disp,kind))
            w(f"{kind} this+0x{disp:X} file=0x{p:08X}")
    if not bhits:w("none")
    w("")

    obj={
        "phase":"74-gs-garage-gbbw-storage",
        "ams_sha256":cursha,
        "gs_garage_slot_dc":"0x00ABE7E0",
        "gbbw_factory":"0x00A6C7F0",
        "gbbw_ctor":"0x0096EB10",
        "candidate_gs_garage_fields":[f"0x{x:X}" for x in sorted(candidate_offsets)],
        "reuse_count":len(reuse),
        "gbbw_refs_in_gs_methods":[
            {"slot":f"0x{slot:X}","method_va":f"0x{va:08X}","file":f"0x{p:08X}","kind":label,"target":f"0x{val:08X}"}
            for idx,slot,va,p,label,val in refs
        ],
        "build_handler_candidate_field_hits":[
            {"file":f"0x{p:08X}","field":f"0x{disp:X}","kind":kind}
            for p,disp,kind in bhits
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*112)
    print(" PHASE 74 GS_GARAGE -> GBBW STORAGE MAP READY")
    print("="*112)
    print("Candidate GS_Garage fields:",",".join(f"0x{x:X}" for x in sorted(candidate_offsets)) if candidate_offsets else "none")
    print("Reuse hits:",len(reuse))
    print("GBBW refs in GS_Garage methods:",len(refs))
    print("Build-handler candidate-field hits:",len(bhits))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
