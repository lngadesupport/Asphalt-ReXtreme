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

REG_HELPER=0x0096E4B0
DELEGATE_COPY=0x0096E2D0
EVENT_ATTACH=0x00905680
EVENT_FINALIZE=0x009077D0
BUILD_CALLBACK=0x00973C90
BUTTON_REGISTRY=0x00972B90

CALLBACKS={
    "cb_00973D20":0x00973D20,
    "cb_00973E40":0x00973E40,
    "build_cb_00973C90":BUILD_CALLBACK,
    "cb_0097B7E0":0x0097B7E0,
    "cb_00973ED0":0x00973ED0,
}
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
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

def is_exec_file(off,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return bool(s["ch"]&0x20000000)
    return False

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    return f is not None and is_exec_file(f,secs)

def next_prologue(d,start,limit=0x5000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

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
    out=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        p=s["raw"];end=min(len(d)-5,s["raw"]+s["rs"]-5)
        while p<=end:
            if d[p]==0xE8:
                sva=f2v(p,ib,secs)
                if sva is not None and ((sva+5+i32(d,p+1))&0xffffffff)==target:
                    out.append(p);p+=5;continue
            p+=1
    return out

def find_callback_blocks(d,fs,fe,callbacks):
    rows=[]
    for name,va in callbacks.items():
        pat=struct.pack("<I",va)
        pos=fs
        while True:
            j=d.find(pat,pos,fe)
            if j<0:break
            # Search forward for direct call to register helper within 0x60 bytes.
            call=None
            q=j
            while q+5<=min(fe,j+0x70):
                if d[q]==0xE8:
                    sva=f2v(q,ib,secs)
                    if sva is not None:
                        dst=(sva+5+i32(d,q+1))&0xffffffff
                        if dst==REG_HELPER:
                            call=q;break
                q+=1
            rows.append((name,va,j,call))
            pos=j+4
    return rows

def scan_stack_local_refs(d,a,z):
    # Heuristic dump of EBP-relative accesses in a small block.
    out=[]
    p=a
    while p+3<=z:
        op=d[p]
        if op in (0x8B,0x89,0x8D,0xC7,0xC6,0xFF):
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
            if rm==5 and mod==1:
                disp=d[p+2]
                if disp>=128:disp-=256
                out.append((p,op,mr,disp))
                p+=3;continue
            if rm==5 and mod==2 and p+6<=z:
                disp=struct.unpack_from("<i",d,p+2)[0]
                out.append((p,op,mr,disp))
                p+=6;continue
        p+=1
    return out

def helper_body(lines,d,label,va,ib,secs):
    w=lines.append
    fs=v2f(va,ib,secs); fe=next_prologue(d,fs,0x5000)
    w(f"===== {label} =====")
    w(f"VA=0x{va:08X} file=0x{fs:08X} end=0x{fe:08X} len=0x{fe-fs:X}")
    lines.extend(dump(d,fs,fe))
    w("-- direct calls --")
    for p,dst in direct_calls(d,fs,fe,ib,secs):
        tag=""
        if dst==DELEGATE_COPY:tag=" DELEGATE_COPY"
        elif dst==EVENT_ATTACH:tag=" EVENT_ATTACH"
        elif dst==EVENT_FINALIZE:tag=" EVENT_FINALIZE"
        w(f"CALL file=0x{p:08X} -> VA=0x{dst:08X}{tag}")
    w(f"directCallers={len(direct_callers(d,va,ib,secs))}")
    w("")

def main():
    global ib,secs
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
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE76_DELEGATE_REGISTRATION"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE76-DELEGATE-REGISTRATION.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*112)
    w(" ReXtreme Phase 76 - build_button delegate registration / connection-handle map")
    w("="*112)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w(f"slot04=0x{BUTTON_REGISTRY:08X}")
    w(f"register_helper=0x{REG_HELPER:08X}")
    w(f"delegate_copy=0x{DELEGATE_COPY:08X}")
    w(f"event_attach=0x{EVENT_ATTACH:08X}")
    w(f"event_finalize=0x{EVENT_FINALIZE:08X}")
    w("")

    # Full slot04 region including all callback registrations.
    sf=v2f(BUTTON_REGISTRY,ib,secs)
    se=next_prologue(d,sf,0x1800)
    w("===== GBBW SLOT04 FULL REGISTRATION BODY =====")
    w(f"file=0x{sf:08X} end=0x{se:08X}")
    lines.extend(dump(d,sf,se))
    w("")

    blocks=find_callback_blocks(d,sf,se,CALLBACKS)
    w("===== CALLBACK REGISTRATION BLOCKS =====")
    w(f"Count={len(blocks)}")
    block_objs=[]
    for name,va,j,call in sorted(blocks,key=lambda x:x[2]):
        w(f"[{name}] callbackVA=0x{va:08X} immFile=0x{j:08X} registerCall={('0x%08X'%call) if call else 'NOT_FOUND'}")
        a=max(sf,j-0x30); z=min(se,(call+0x60) if call else j+0x90)
        lines.extend(dump(d,a,z))
        if call:
            locals_=scan_stack_local_refs(d,max(sf,j-0x20),min(se,call+0x50))
            for p,op,mr,disp in locals_:
                w(f"  ebpLocal file=0x{p:08X} op=0x{op:02X} modrm=0x{mr:02X} disp={disp:+#x}")
            block_objs.append({
                "name":name,"callback":f"0x{va:08X}","imm_file":f"0x{j:08X}",
                "register_call":f"0x{call:08X}"
            })
        w("")

    helper_body(lines,d,"REGISTER_HELPER",REG_HELPER,ib,secs)
    helper_body(lines,d,"DELEGATE_COPY",DELEGATE_COPY,ib,secs)
    helper_body(lines,d,"EVENT_ATTACH",EVENT_ATTACH,ib,secs)
    helper_body(lines,d,"EVENT_FINALIZE",EVENT_FINALIZE,ib,secs)

    # For each internal helper, dump all direct callers inside slot04 and register helper.
    w("===== INTERNAL EDGE CROSSCHECK =====")
    for label,va in [("REG_HELPER",REG_HELPER),("DELEGATE_COPY",DELEGATE_COPY),("EVENT_ATTACH",EVENT_ATTACH),("EVENT_FINALIZE",EVENT_FINALIZE)]:
        callers=direct_callers(d,va,ib,secs)
        w(f"{label} 0x{va:08X} callers={len(callers)}")
        for p in callers[:120]:
            pva=f2v(p,ib,secs)
            in_slot = sf<=p<se
            rf=v2f(REG_HELPER,ib,secs); re=next_prologue(d,rf,0x5000)
            in_reg = rf<=p<re
            w(f" callFile=0x{p:08X} callVA=0x{pva:08X} inSlot04={in_slot} inRegisterHelper={in_reg}")
        w("")

    # Compare local/out handling after each callback registration call.
    w("===== POST-REGISTER COMPARISON =====")
    for name,va,j,call in sorted(blocks,key=lambda x:x[2]):
        if not call:continue
        w(f"[{name}] callFile=0x{call:08X}")
        lines.extend(dump(d,call,min(se,call+0x90)))
        w("")

    obj={
      "phase":"76-delegate-registration",
      "ams_sha256":cursha,
      "callback_blocks":block_objs,
      "register_helper":f"0x{REG_HELPER:08X}",
      "delegate_copy":f"0x{DELEGATE_COPY:08X}",
      "event_attach":f"0x{EVENT_ATTACH:08X}",
      "event_finalize":f"0x{EVENT_FINALIZE:08X}",
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*112)
    print(" PHASE 76 DELEGATE REGISTRATION MAP READY")
    print("="*112)
    print("Callback registration blocks:",len(blocks))
    for x in block_objs:
        print(x["name"],x["register_call"])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
