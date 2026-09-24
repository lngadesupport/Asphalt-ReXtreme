#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import defaultdict

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

# Stable guards.
P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

REGISTER_HELPER=0x0096E4B0
INVOKE_HELPER=0x00936BE0
BUILD_CALLBACK=0x00973C90
SIBLINGS={
    "sibling_34":0x00973D20,
    "sibling_3C":0x00973E40,
    "sibling_4C":0x0097B7E0,
    "sibling_54_64":0x00973ED0,
}
BUTTON_REGISTRY=0x00972B90
BUILD_HANDLER=0x00A87960
CRAFTCALLER=0x0099FF50
CRAFTCAR=0x009A4BA0
GS_GARAGE_VTABLE=0x0186A9CC

FIELD_OFFSETS=[0x34,0x3C,0x44,0x4C,0x54,0x5C,0x64]
KNOWN={
    "register_helper":REGISTER_HELPER,
    "invoke_helper":INVOKE_HELPER,
    "build_callback":BUILD_CALLBACK,
    "button_registry":BUTTON_REGISTRY,
    "build_handler":BUILD_HANDLER,
    "craftcaller":CRAFTCALLER,
    "craftcar":CRAFTCAR,
}
KNOWN.update(SIBLINGS)

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
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b: raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28); so=opt+osz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append(dict(
            name=d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            vs=u32(d,o+8), va=u32(d,o+12), rs=u32(d,o+16), raw=u32(d,o+20), ch=u32(d,o+36)
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
    f=v2f(va,ib,secs)
    return f is not None and is_exec_file(f,secs)

def find_all(d,pat):
    out=[];p=0
    while True:
        p=d.find(pat,p)
        if p<0:return out
        out.append(p);p+=1

def prologue(d,near,back=0x6000):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC":return p
    return None

def next_prologue(d,start,limit=0x4000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def direct_calls(d,fs,fe,ib,secs):
    out=[];p=fs
    while p+5<=fe:
        if d[p] in (0xE8,0xE9):
            sva=f2v(p,ib,secs)
            if sva is not None:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                out.append((p,"CALL" if d[p]==0xE8 else "JMP",dst,v2f(dst,ib,secs)))
            p+=5;continue
        p+=1
    return out

def indirect_calls(d,fs,fe):
    out=[];p=fs
    while p+2<=fe:
        if d[p]==0xFF:
            mr=d[p+1]; reg=(mr>>3)&7; mod=(mr>>6)&3; rm=mr&7
            if reg==2:
                if mod==0:
                    out.append((p,0,2,mr))
                    p+=2;continue
                if mod==1 and p+3<=fe:
                    out.append((p,i8(d,p+2),3,mr))
                    p+=3;continue
                if mod==2 and p+6<=fe and rm!=4:
                    out.append((p,u32(d,p+2),6,mr))
                    p+=6;continue
        p+=1
    return out

def direct_callers(d,target,ib,secs):
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-5,s["raw"]+s["rs"]-5)
        cur=None
        while p<=end:
            if d[p:p+3]==b"\x55\x8B\xEC":cur=f2v(p,ib,secs)
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    out.append((p,cur))
                    p+=5;continue
            p+=1
    return out

def ascii_z(d,off,limit=300):
    if off is None or not(0<=off<len(d)):return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    raw=d[off:z]
    try:s=raw.decode("ascii","replace")
    except:return ""
    return s if s and sum(0x20<=ord(c)<0x7f for c in s)>=max(1,int(len(s)*.9)) else ""

def rtti_for_vtable_file(d,vf,ib,secs):
    if vf<4:return None
    col=v2f(u32(d,vf-4),ib,secs)
    if col is None or col+20>len(d):return None
    td=v2f(u32(d,col+12),ib,secs)
    return ascii_z(d,td+8,300) if td is not None else None

def method_vtable_owners(d,method_va,ib,secs):
    out=[]
    for hit in find_all(d,struct.pack("<I",method_va)):
        if is_exec_file(hit,secs):continue
        for vf in range(hit,max(4,hit-0x600)-1,-4):
            name=rtti_for_vtable_file(d,vf,ib,secs)
            if not(name and name.startswith(".?A")):continue
            idx=(hit-vf)//4
            good=True
            for p in range(vf,hit+4,4):
                if not is_exec_va(u32(d,p),ib,secs):
                    good=False;break
            if good:
                out.append((vf,f2v(vf,ib,secs),idx,idx*4,name,hit))
                break
    uniq=[];seen=set()
    for x in out:
        k=(x[0],x[2])
        if k not in seen:
            seen.add(k);uniq.append(x)
    return uniq

def disp32_field_uses(d,disp,ib,secs,lo_va=0x00900000,hi_va=0x00A00000):
    pat=struct.pack("<I",disp)
    rows=[]
    for p in find_all(d,pat):
        if not is_exec_file(p,secs) or p<2:continue
        va=f2v(p,ib,secs)
        if va is None or not(lo_va<=va<=hi_va):continue
        mr=d[p-1];mod=(mr>>6)&3;rm=mr&7
        if mod!=2 or rm==4:continue
        op=d[p-2]
        if op not in (0x8B,0x89,0x8D,0x83,0x81,0x80,0xC6,0xC7,0x39,0x3B,0xFF,0xF6,0xF7):continue
        fs=prologue(d,p);fva=f2v(fs,ib,secs) if fs is not None else None
        rows.append((p,va,fs,fva,op,mr))
    return rows

def immediate_exec_refs(d,va,secs):
    return [p for p in find_all(d,struct.pack("<I",va)) if is_exec_file(p,secs)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
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
        if cur!=exp:raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256: {cursha}, expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE68_BUILD_ACTION_OBJECT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE68-BUILD-ACTION-OBJECT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*100)
    w(" ReXtreme Phase 68 - build_button action object / signal bridge")
    w("="*100)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")

    w("===== BUILD CALLBACK ROOT =====")
    w(f"build_callback=0x{BUILD_CALLBACK:08X}")
    w("callback_shape=[this+0x44] -> [+0x08] -> invoke_helper")
    w(f"register_helper=0x{REGISTER_HELPER:08X}")
    w(f"invoke_helper=0x{INVOKE_HELPER:08X}")
    w("")

    for label,va in [("register_helper",REGISTER_HELPER),("invoke_helper",INVOKE_HELPER)]:
        fs=v2f(va,ib,secs);fe=next_prologue(d,fs,0x2800)
        w(f"===== {label.upper()} =====")
        w(f"VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X} len=0x{fe-fs:X}")
        lines.extend(dump(d,fs,fe))
        w("-- direct edges --")
        for p,k,dst,dfo in direct_calls(d,fs,fe,ib,secs):
            tag=next((n for n,v in KNOWN.items() if v==dst),"")
            w(f" {k} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'} {tag}")
        w("-- indirect calls --")
        for p,slot,n,mr in indirect_calls(d,fs,fe):
            w(f" ICALL file=0x{p:08X} disp={('0x%X'%slot) if slot>=0 else str(slot)} modrm=0x{mr:02X}")
        w("-- direct callers --")
        cs=direct_callers(d,va,ib,secs)
        w(f" count={len(cs)}")
        for cp,cfn in cs[:160]:
            w(f" callerFile=0x{cp:08X} callerFn={('0x%08X'%cfn) if cfn else 'N/A'}")
            lines.extend(dump(d,cp-96,cp+160))
        owners=method_vtable_owners(d,va,ib,secs)
        w(f"-- RTTI-backed vtable owners={len(owners)} --")
        for vf,vva,idx,slot,rtti,hit in owners:
            w(f" RTTI={rtti!r} vtableVA=0x{vva:08X} index={idx} slot=0x{slot:X} hitFile=0x{hit:08X}")
        w("")

    w("===== CALLBACK THUNKS / FIELD MAP =====")
    for name,va in [("build_44",BUILD_CALLBACK)]+list(SIBLINGS.items()):
        fs=v2f(va,ib,secs);fe=next_prologue(d,fs,0x400)
        w(f"[{name}] VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X}")
        lines.extend(dump(d,fs,fe))
    w("")

    w("===== WRITES/USES OF CALLBACK TARGET FIELDS IN GARAGE/UI CODE =====")
    field_rows={}
    for off in FIELD_OFFSETS:
        rows=disp32_field_uses(d,off,ib,secs)
        field_rows[off]=rows
        w(f"[field+0x{off:X}] uses={len(rows)}")
        seenfn=set()
        for p,pva,fs,fva,op,mr in rows[:300]:
            w(f" useFile=0x{p:08X} useVA=0x{pva:08X} fn={('0x%08X'%fva) if fva else 'N/A'} opcode=0x{op:02X} modrm=0x{mr:02X}")
            if fs is not None and fva not in seenfn:
                seenfn.add(fva)
                lines.extend(dump(d,max(fs,p-80),min(next_prologue(d,fs,0x1800),p+144)))
        w("")

    w("===== IMMEDIATE REFS TO BUILD CALLBACK / REGISTER HELPER =====")
    for label,va in [("build_callback",BUILD_CALLBACK),("register_helper",REGISTER_HELPER),("invoke_helper",INVOKE_HELPER)]:
        refs=immediate_exec_refs(d,va,secs)
        w(f"[{label}] refs={len(refs)}")
        for p in refs[:100]:
            fs=prologue(d,p);fva=f2v(fs,ib,secs) if fs is not None else None
            w(f" refFile=0x{p:08X} refVA=0x{f2v(p,ib,secs):08X} fn={('0x%08X'%fva) if fva else 'N/A'}")
            lines.extend(dump(d,p-96,p+176))
        w("")

    w("===== BUILD REGISTRATION CALLSITE FOCUS =====")
    # Known build_button registration call to REGISTER_HELPER around file 0x00572299.
    p0=0x00572260;p1=0x005722C0
    lines.extend(dump(d,p0,p1))
    w("Expected build registration structure:")
    w(" callback thunk 0x00973C90")
    w(" event source/object +0x1DC")
    w(" helper 0x0096E4B0")
    w("")

    w("===== GS_GARAGE BUILD SLOT CONTEXT =====")
    bf=v2f(BUILD_HANDLER,ib,secs);be=next_prologue(d,bf,0x1400)
    w(f"BuildHandler VA=0x{BUILD_HANDLER:08X} file=0x{bf:08X} end=0x{be:08X}")
    lines.extend(dump(d,bf,min(be,bf+0x900)))
    w("")

    # Detect functions that touch multiple callback-target offsets.
    fn_fields=defaultdict(set)
    for off,rows in field_rows.items():
        for _,_,_,fva,_,_ in rows:
            if fva is not None:fn_fields[fva].add(off)
    multi=sorted(((fva,offs) for fva,offs in fn_fields.items() if len(offs)>=3),key=lambda x:(-len(x[1]),x[0]))
    w("===== FUNCTIONS TOUCHING >=3 CALLBACK-TARGET FIELDS =====")
    w(f"count={len(multi)}")
    for fva,offs in multi[:120]:
        w(f"fn=0x{fva:08X} fields="+",".join(f"0x{x:X}" for x in sorted(offs)))
        fs=v2f(fva,ib,secs)
        if fs is not None:lines.extend(dump(d,fs,min(next_prologue(d,fs,0x1800),fs+0x700)))
    w("")

    obj={
        "phase":"68-build-action-object",
        "ams_sha256":cursha,
        "build_callback":"0x00973C90",
        "register_helper":"0x0096E4B0",
        "invoke_helper":"0x00936BE0",
        "field_offsets":[f"0x{x:X}" for x in FIELD_OFFSETS],
        "multi_field_functions":[f"0x{x:08X}" for x,_ in multi[:100]],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*100)
    print(" PHASE 68 BUILD ACTION OBJECT MAP READY")
    print("="*100)
    print("Register helper: 0x0096E4B0")
    print("Invoke helper:   0x00936BE0")
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
