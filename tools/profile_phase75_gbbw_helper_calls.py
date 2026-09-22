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
GBBW_FIELD=0x35C
GBBW_CTRL_FIELD=0x360
GBBW_VTABLE=0x01831854
BUILD_HANDLER=0x00A87960
BUILD_BUTTON_GETTER=0x00973510
BUILD_CALLBACK=0x00973C90
TARGET_FIELD=0x44
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

def next_prologue(d,start,limit=0x6000):
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
    lim=min(fe,fs+0x80)
    pats=[(b"\x8B\xF1","esi"),(b"\x8B\xF9","edi"),(b"\x8B\xD9","ebx"),(b"\x8B\xC1","eax")]
    best=None
    for pat,r in pats:
        p=d.find(pat,fs,lim)
        if p>=0 and (best is None or p<best[0]):best=(p,r)
    return best[1] if best else "ecx"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8(d,p+2),3
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
    return "MEM"

def scan_gbbw_loads(d,fs,fe,thisreg):
    rid=REGS.index(thisreg)
    out=[];p=fs
    while p+6<=fe:
        # mov dst,[this+0x35C]
        if d[p]==0x8B:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; dst=(mr>>3)&7
            if mod==2 and rm==rid and u32(d,p+2)==GBBW_FIELD:
                out.append((p,REGS[dst]))
                p+=6;continue
        p+=1
    return out

def clobbers_reg(d,p,reg):
    rid=REGS.index(reg)
    # Common mov reg,* destination
    if p+2<=len(d) and d[p] in (0x8B,0x8D):
        mr=d[p+1]
        if ((mr>>3)&7)==rid:
            return True
    # pop reg
    if d[p]==0x58+rid:return True
    return False

def uses_obj_as_ecx_before_call(d,loadp,objreg,callp):
    # If loaded directly into ECX and not clobbered, strongest case.
    if objreg=="ecx":
        q=loadp+6
        while q<callp:
            if clobbers_reg(d,q,"ecx"):
                # Allow push/lea? clobber means lost.
                return False,None
            q+=1
        return True,loadp
    rid=REGS.index(objreg)
    pat1=bytes([0x8B,0xC8|rid])           # mov ecx,reg
    pat2=bytes([0x89,0xC1|(rid<<3)])      # mov ecx,reg
    lo=max(loadp+6,callp-32)
    p1=d.rfind(pat1,lo,callp)
    p2=d.rfind(pat2,lo,callp)
    p=max(p1,p2)
    return (p>=0,p if p>=0 else None)

def direct_calls_after_load(d,loadp,objreg,fe,ib,secs,window=0x90):
    out=[]
    z=min(fe,loadp+window)
    p=loadp+6
    while p+5<=z:
        if d[p]==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                ok,prep=uses_obj_as_ecx_before_call(d,loadp,objreg,p)
                if ok:out.append((p,dst,prep))
            p+=5;continue
        p+=1
    return out

def helper_field44(d,va,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return []
    fe=next_prologue(d,fs,0x3000)
    tr=detect_this_reg(d,fs,fe)
    rid=REGS.index(tr)
    rows=[];p=fs
    while p+3<=fe:
        op=d[p]
        if op not in (0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF):
            p+=1;continue
        dec=decode_mem(d,p,fe)
        if not dec:
            p+=1;continue
        rm,disp,ln=dec
        if rm==rid and disp==TARGET_FIELD:
            rows.append((p,classify(op,d[p+1]),tr,op,d[p+1]))
        p+=ln
    return rows

def virtual_calls_on_obj(d,loadp,objreg,fe,window=0x90):
    # Heuristic: detect call [reg+disp] if reg itself is object, or mov tmp,[obj]; call [tmp+disp].
    out=[];z=min(fe,loadp+window)
    rid=REGS.index(objreg)
    p=loadp+6
    while p+3<=z:
        if d[p]==0xFF:
            mr=d[p+1]; ext=(mr>>3)&7; mod=(mr>>6)&3; rm=mr&7
            if ext==2 and rm==rid:
                if mod==1:
                    out.append((p,i8(d,p+2),"direct_obj"))
                elif mod==2 and p+6<=z:
                    out.append((p,u32(d,p+2),"direct_obj"))
        p+=1
    return out

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
    helper_uses=defaultdict(list)
    load_rows=[]
    virtual_rows=[]

    for idx,slot,va in methods:
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x6000)
        tr=detect_this_reg(d,fs,fe)
        loads=scan_gbbw_loads(d,fs,fe,tr)
        for lp,objreg in loads:
            load_rows.append((idx,slot,va,lp,objreg,tr))
            for cp,dst,prep in direct_calls_after_load(d,lp,objreg,fe,ib,secs,0xA0):
                helper_uses[dst].append((idx,slot,va,lp,objreg,cp,prep))
            for vp,vslot,kind in virtual_calls_on_obj(d,lp,objreg,fe,0xA0):
                virtual_rows.append((idx,slot,va,lp,objreg,vp,vslot,kind))

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE75_GBBW_HELPER_CALLS"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE75-GBBW-HELPER-CALLS.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*112)
    w(" ReXtreme Phase 75 - calls made on GS_Garage+0x35C (GarageBottomBarWidget)")
    w("="*112)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Confirmed: GS_Garage+0x35C stores the GarageBottomBarWidget object.")
    w("This phase maps direct helpers invoked with that object in ECX and checks each helper for +0x44.")
    w("")

    w("===== LOADS OF GS_GARAGE+0x35C =====")
    w(f"Count={len(load_rows)}")
    for idx,slot,va,lp,objreg,tr in load_rows:
        marker=" BUILD_HANDLER" if va==BUILD_HANDLER else ""
        w(f"gsSlot=0x{slot:X} method=0x{va:08X}{marker} loadFile=0x{lp:08X} objReg={objreg} gsThis={tr}")
    w("")

    w("===== DIRECT HELPERS CALLED WITH GBBW AS ECX =====")
    w(f"UniqueHelpers={len(helper_uses)}")
    strong=[]
    for dst,uses in sorted(helper_uses.items(),key=lambda kv:(-len(kv[1]),kv[0])):
        f44=helper_field44(d,dst,ib,secs)
        tags=[]
        if dst==BUILD_BUTTON_GETTER:tags.append("BUILD_BUTTON_GETTER")
        if dst==BUILD_CALLBACK:tags.append("BUILD_CALLBACK")
        if f44:tags.append("TOUCHES_+0x44")
        w(f"[helper 0x{dst:08X}] uses={len(uses)} tags={','.join(tags) if tags else '-'}")
        for idx,slot,va,lp,objreg,cp,prep in uses:
            marker=" BUILD_HANDLER" if va==BUILD_HANDLER else ""
            w(f" fromGsSlot=0x{slot:X} method=0x{va:08X}{marker} loadFile=0x{lp:08X} callFile=0x{cp:08X} objReg={objreg} ecxPrep=0x{prep:08X}")
            lines.extend(dump(d,max(v2f(va,ib,secs),lp-32),cp+48))
        hf=v2f(dst,ib,secs)
        if hf is not None:
            he=next_prologue(d,hf,0x3000)
            w(f" helperFile=0x{hf:08X} end=0x{he:08X}")
            for p,kind,tr2,op,mr in f44:
                w(f"  +0x44 {kind} file=0x{p:08X} this={tr2} op=0x{op:02X} modrm=0x{mr:02X}")
                lines.extend(dump(d,p-64,p+128))
            if f44:
                strong.append((dst,uses,f44))
                lines.extend(dump(d,hf,min(he,hf+0x800)))
        w("")

    w("===== VIRTUAL CALLS DIRECTLY ON LOADED GBBW REGISTER =====")
    w(f"Count={len(virtual_rows)}")
    for idx,slot,va,lp,objreg,vp,vslot,kind in virtual_rows:
        w(f"gsSlot=0x{slot:X} method=0x{va:08X} loadFile=0x{lp:08X} objReg={objreg} callFile=0x{vp:08X} gbVslot={vslot:+#x}")
    w("")

    w("===== STRONG +0x44 HELPER CANDIDATES =====")
    w(f"Count={len(strong)}")
    for dst,uses,f44 in strong:
        kinds=sorted({x[1] for x in f44})
        w(f"helper=0x{dst:08X} kinds={','.join(kinds)} gsUses={len(uses)}")
        for idx,slot,va,lp,objreg,cp,prep in uses:
            w(f"  from gsSlot=0x{slot:X} method=0x{va:08X} callFile=0x{cp:08X}")
    w("")

    # Known build handler focused context.
    w("===== BUILD HANDLER -> GBBW FOCUS =====")
    bf=v2f(BUILD_HANDLER,ib,secs); be=next_prologue(d,bf,0x3000)
    lines.extend(dump(d,0x006870F0,min(be,0x00687190)))
    w(f"Known build_button getter VA=0x{BUILD_BUTTON_GETTER:08X}")
    w("")

    obj={
      "phase":"75-gbbw-helper-calls",
      "ams_sha256":cursha,
      "gbbw_load_count":len(load_rows),
      "unique_helpers":len(helper_uses),
      "strong_helpers":[
        {
          "helper_va":f"0x{dst:08X}",
          "field44_kinds":sorted({x[1] for x in f44}),
          "gs_uses":[
            {"slot":f"0x{slot:X}","method_va":f"0x{va:08X}","call_file":f"0x{cp:08X}"}
            for idx,slot,va,lp,objreg,cp,prep in uses
          ]
        } for dst,uses,f44 in strong
      ],
      "virtual_calls_on_loaded_gbbw":len(virtual_rows),
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*112)
    print(" PHASE 75 GBBW HELPER CALL MAP READY")
    print("="*112)
    print("GBBW loads:",len(load_rows))
    print("Unique helpers called with GBBW as ECX:",len(helper_uses))
    print("Strong helpers touching +0x44:",len(strong))
    print("Virtual calls directly on loaded GBBW:",len(virtual_rows))
    if strong:
        print("TOP helper:",hex(strong[0][0]))
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
