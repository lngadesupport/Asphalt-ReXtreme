#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, re
from pathlib import Path

VTABLES = {
    "variant_A": 0x01831854,  # table containing 009747F0
    "variant_B": 0x01837A5C,  # table containing 0098DE50
}
METHODS = {
    "A_slot0":0x009752F0,
    "A_slot2":0x0096F380,
    "A_slot4":0x009747F0,
    "A_slot5":0x009740D0,
    "B_slot0":0x0098E080,
    "B_slot2":0x0098DB20,
    "B_slot4":0x0098DE50,
    "B_slot5":0x0098DB50,
    "shared_slot1":0x00972B90,
    "shared_slot3":0x00974480,
    "shared_slot6":0x00975040,
    "shared_slot7":0x009743C0,
    "shared_slot8":0x00974A40,
    "shared_slot9":0x00974ED0,
}
GLOBAL_ISONLINE=0x00FAD9D0

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i32(b,o): return struct.unpack_from("<i",b,o)[0]

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
        span=max(s["vs"],s["rs"])
        if s["va"]<=rva<s["va"]+span:
            return s["raw"]+(rva-s["va"])
    return None

def sec_for_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]: return s
    return None

def is_exec_file(off,secs):
    s=sec_for_file(off,secs)
    return bool(s and s["ch"]&0x20000000)

def find_all(d,pat):
    out=[]; p=0
    while True:
        p=d.find(pat,p)
        if p<0: break
        out.append(p); p+=1
    return out

def dump(d,a,z):
    out=[]
    a=max(0,a); z=min(len(d),z)
    for p in range(a,z,16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def prologue(d,near,back=0x1800):
    lo=max(0,near-back)
    for p in range(near,lo-1,-1):
        if d[p:p+3]==b"\x55\x8B\xEC": return p
    return None

def next_prologue(d,start,limit=0x1000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def scan_flow(d,start,end,ib,secs):
    out=[]; p=start
    while p<end-6:
        va=f2v(p,ib,secs)
        if va is None: p+=1; continue
        op=d[p]
        if op in (0xE8,0xE9):
            dst=(va+5+i32(d,p+1))&0xffffffff
            out.append((p,"CALL" if op==0xE8 else "JMP",dst,v2f(dst,ib,secs)))
            p+=5; continue
        if op==0x0F and 0x80<=d[p+1]<=0x8F:
            dst=(va+6+i32(d,p+2))&0xffffffff
            out.append((p,f"JCC 0F{d[p+1]:02X}",dst,v2f(dst,ib,secs)))
            p+=6; continue
        if 0x70<=op<=0x7F:
            rel=d[p+1]-256 if d[p+1]>=128 else d[p+1]
            dst=(va+2+rel)&0xffffffff
            out.append((p,f"JCC {op:02X}",dst,v2f(dst,ib,secs)))
            p+=2; continue
        if op==0xFF and p+1<end and ((d[p+1]>>3)&7)==2:
            out.append((p,"CALL [indirect]",None,None))
        p+=1
    return out

def ascii_z(d,off,limit=240):
    if off is None or off<0 or off>=len(d): return ""
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0: z=min(len(d),off+limit)
    raw=d[off:z]
    try:
        s=raw.decode("ascii","replace")
    except:
        return ""
    return s if all((ord(c)>=0x20 or c in "\t\r\n") for c in s) else ""

def rtti_name_for_vtable(d,vtable_va,ib,secs):
    vf=v2f(vtable_va,ib,secs)
    if vf is None or vf<4: return None,{}
    col_va=u32(d,vf-4)
    col_f=v2f(col_va,ib,secs)
    info={"vtable_file":vf,"col_va":col_va,"col_file":col_f}
    if col_f is None or col_f+20>len(d): return None,info
    # x86 MSVC CompleteObjectLocator: sig, offset, cdOffset, pTypeDescriptor, pClassHierarchy
    sig,off,cd,td_va,chd_va=struct.unpack_from("<IIIII",d,col_f)
    info.update(sig=sig,offset=off,cdOffset=cd,type_desc_va=td_va,class_hierarchy_va=chd_va)
    td_f=v2f(td_va,ib,secs)
    info["type_desc_file"]=td_f
    name=None
    if td_f is not None and td_f+8<len(d):
        name=ascii_z(d,td_f+8,300)
    return name,info

def direct_callers(d,target_va,ib,secs):
    res=[]
    for s in secs:
        if not(s["ch"]&0x20000000): continue
        p=s["raw"]; end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                src=f2v(p,ib,secs)
                if src is not None and ((src+5+i32(d,p+1))&0xffffffff)==target_va:
                    res.append(p); p+=5; continue
            p+=1
    return res

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    guards=[
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]
    for name,off,exp in guards:
        cur=d[off:off+len(exp)]
        if cur!=exp: raise SystemExit(f"{name} guard failed at 0x{off:08X}: {cur.hex(' ')} expected {exp.hex(' ')}")

    ib,secs=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE57_VTABLE_HANDLER_MAP"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"LATEST-PHASE57-VTABLE-HANDLER-MAP.txt"
    lines=[]; w=lines.append

    w("="*82)
    w(" ReXtreme Phase 57 - build screen vtable / handler map")
    w("="*82)
    w("AMS_SHA256="+hashlib.sha256(d).hexdigest())
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("")

    w("===== RTTI / VTABLE IDENTITY =====")
    for name,vva in VTABLES.items():
        rtti,info=rtti_name_for_vtable(d,vva,ib,secs)
        w(f"[{name}] vtableVA=0x{vva:08X} vtableFile={('0x%08X'%info.get('vtable_file')) if info.get('vtable_file') is not None else 'N/A'}")
        w(f" RTTI={rtti!r}")
        for k in ("col_va","col_file","sig","offset","cdOffset","type_desc_va","type_desc_file","class_hierarchy_va"):
            if k in info:
                v=info[k]
                if isinstance(v,int): w(f" {k}=0x{v:08X}")
                else: w(f" {k}={v}")
        vf=info.get("vtable_file")
        if vf is not None:
            for i in range(10):
                va=u32(d,vf+4*i)
                fo=v2f(va,ib,secs)
                w(f" slot+0x{4*i:02X}: VA=0x{va:08X} file={('0x%08X'%fo) if fo is not None else 'N/A'}")
        w("")

    w("===== EXECUTABLE REFERENCES TO VTABLE POINTERS =====")
    for name,vva in VTABLES.items():
        refs=[x for x in find_all(d,struct.pack("<I",vva)) if is_exec_file(x,secs)]
        w(f"[{name}] refs={len(refs)}")
        for r in refs[:100]:
            rv=f2v(r,ib,secs); pr=prologue(d,r)
            w(f" refFile=0x{r:08X} refVA=0x{rv:08X} prologue={('0x%08X'%pr) if pr is not None else 'N/A'}")
            lines.extend(dump(d,r-64,r+112))
        w("")

    w("===== VARIANT-SPECIFIC METHOD BODIES =====")
    for name,va in METHODS.items():
        if not (name.startswith("A_") or name.startswith("B_")): continue
        fo=v2f(va,ib,secs)
        if fo is None: continue
        end=next_prologue(d,fo,0x1200)
        w(f"[{name}] VA=0x{va:08X} file=0x{fo:08X} end=0x{end:08X} len=0x{end-fo:X}")
        lines.extend(dump(d,fo,end))
        w("--- FLOW ---")
        iso=[]
        for p,k,dst,dfo in scan_flow(d,fo,end,ib,secs):
            if dst is None:
                w(f"{k} file=0x{p:08X}")
            else:
                w(f"{k} file=0x{p:08X} -> VA=0x{dst:08X} file={('0x%08X'%dfo) if dfo is not None else 'N/A'}")
                if k=="CALL" and dst==GLOBAL_ISONLINE: iso.append(p)
        w(f"GlobalIsOnlineCalls={len(iso)} "+(",".join(f"0x{x:08X}" for x in iso) if iso else ""))
        callers=direct_callers(d,va,ib,secs)
        w(f"DirectRelativeCallers={len(callers)}")
        for c in callers[:40]:
            w(f" callerFile=0x{c:08X} callerVA=0x{f2v(c,ib,secs):08X} prologue={('0x%08X'%prologue(d,c)) if prologue(d,c) is not None else 'N/A'}")
            lines.extend(dump(d,c-48,c+96))
        w("")

    # Focused comparison for corresponding slots.
    w("===== SLOT PAIR SUMMARY =====")
    pairs=[("slot0",METHODS["A_slot0"],METHODS["B_slot0"]),
           ("slot2",METHODS["A_slot2"],METHODS["B_slot2"]),
           ("slot4",METHODS["A_slot4"],METHODS["B_slot4"]),
           ("slot5",METHODS["A_slot5"],METHODS["B_slot5"])]
    for label,a,b in pairs:
        af=v2f(a,ib,secs); bf=v2f(b,ib,secs)
        w(f"{label}: A=0x{a:08X}/file={('0x%08X'%af) if af is not None else 'N/A'} B=0x{b:08X}/file={('0x%08X'%bf) if bf is not None else 'N/A'}")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*82)
    print(" PHASE 57 VTABLE / HANDLER MAP READY")
    print("="*82)
    print("No binary bytes were changed.")
    print("Report:",out)

if __name__=="__main__":
    main()
