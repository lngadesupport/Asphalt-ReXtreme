#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import deque, defaultdict

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

GS_VTABLE=0x0186A9CC
GBBW_OWNER_FIELD=0x35C
BUILD_HANDLER=0x00A87960
BUILD_BUTTON_GETTER=0x00973510
BUILD_CALLBACK=0x00973C90
TARGET_FIELD=0x44
CALLBACK_FIELDS={0x34,0x3C,0x44,0x4C,0x54,0x5C,0x64}

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
    vf=v2f(vva,ib,secs); out=[]
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
    return "MEM"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def find_gbbw_loads(d,fs,fe,thisreg):
    rid=REGS.index(thisreg)
    out=[];p=fs
    while p+6<=fe:
        if d[p]==0x8B:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==2 and rm==rid and u32(d,p+2)==GBBW_OWNER_FIELD:
                out.append((p,REGS[dst]))
                p+=6;continue
        p+=1
    return out

def is_conditional_branch(op):
    return 0x70<=op<=0x7F

def scan_flow(d,start,fe,objreg,origin,ib,secs,window=0x260):
    z=min(fe,start+window)
    taint={objreg:origin}
    vtable_of={}  # register -> object effective origin
    hits=[];calls=[];vcalls=[];derived=[];events=[]
    p=start
    while p<z:
        op=d[p]

        # Stop on RET; don't cross function exits.
        if op in (0xC3,0xCB):
            break
        if op in (0xC2,0xCA):
            break

        # mov reg,reg
        if op==0x8B and p+2<=z:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint:
                    taint[t]=taint[s]
                    events.append((p,"ALIAS",f"{t}={s}",taint[t]))
                else:
                    taint.pop(t,None)
                if s in vtable_of:vtable_of[t]=vtable_of[s]
                else:vtable_of.pop(t,None)
                p+=2;continue

            dec=decode_mem(d,p,z)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    eff=taint[base]+disp
                    if disp==0:
                        # Common "mov eax,[ecx]" can be vtable load if ECX is object.
                        vtable_of[t]=taint[base]
                    else:
                        vtable_of.pop(t,None)
                    if eff in CALLBACK_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                    taint.pop(t,None)  # loaded value is not the original object pointer
                else:
                    taint.pop(t,None);vtable_of.pop(t,None)
                p+=ln;continue

        # mov [mem],reg and other memory ops on tainted object/derived ptr
        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=z:
            mr=d[p+1];dec=decode_mem(d,p,z)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];ext=(mr>>3)&7
                if base in taint:
                    eff=taint[base]+disp
                    if eff in CALLBACK_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                    if op==0xFF and ext==2:
                        # call [object+slot] (rare direct form)
                        vcalls.append((p,eff,base,"direct_object"))
                elif base in vtable_of and op==0xFF and ext==2:
                    # call [vtableReg+slot]
                    eff_origin=vtable_of[base]
                    vcalls.append((p,disp,base,"via_vtable",eff_origin))
                p+=ln;continue

        # lea reg,[tainted+disp] -> derived pointer
        if op==0x8D and p+2<=z:
            mr=d[p+1];dst=(mr>>3)&7
            dec=decode_mem(d,p,z)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    taint[t]=taint[base]+disp
                    derived.append((p,t,taint[t],base,disp))
                    if taint[t] in CALLBACK_FIELDS:
                        hits.append((p,taint[t],"ADDRESS",base,disp))
                else:
                    taint.pop(t,None)
                vtable_of.pop(t,None)
                p+=ln;continue

        # add/sub immediate to tainted pointer
        if op in (0x83,0x81) and p+3<=z:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;ext=(mr>>3)&7
            r=REGS[rm]
            if mod==3 and r in taint and ext in (0,5):
                if op==0x83:
                    imm=i8v(d[p+2]);ln=3
                else:
                    if p+6>z:break
                    imm=i32(d,p+2);ln=6
                if ext==5:imm=-imm
                taint[r]+=imm
                derived.append((p,r,taint[r],r,imm))
                p+=ln;continue

        # Direct relative call.
        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                # FIX vs Phase78: if ECX itself is currently tainted, thiscall carries the object
                # even if there was no explicit mov ecx,reg immediately before the call.
                if "ecx" in taint:
                    calls.append((p,dst,"ecx",taint["ecx"],"ecx",p))
                else:
                    lo=max(start,p-40)
                    candidates=[]
                    for r,off in list(taint.items()):
                        rid=REGS.index(r)
                        pat1=bytes([0x8B,0xC8|rid])        # mov ecx,r
                        pat2=bytes([0x89,0xC1|(rid<<3)])  # mov ecx,r
                        q=max(d.rfind(pat1,lo,p),d.rfind(pat2,lo,p))
                        if q>=0:candidates.append((q,"ecx",off,r))
                        q2=d.rfind(bytes([0x50+rid]),lo,p)
                        if q2>=0:candidates.append((q2,"arg1",off,r))
                    if candidates:
                        candidates.sort(reverse=True)
                        prep,mode,off,r=candidates[0]
                        calls.append((p,dst,mode,off,r,prep))
                # ABI: EAX/ECX/EDX are caller-saved. After call, don't keep stale aliases in them.
                for r in ("eax","ecx","edx"):
                    taint.pop(r,None);vtable_of.pop(r,None)
            p+=5;continue

        # push/pop can preserve or clobber aliases but no need to model stack globally here.
        if 0x58<=op<=0x5F:
            r=REGS[op-0x58]
            taint.pop(r,None);vtable_of.pop(r,None)
            p+=1;continue

        p+=1
    return hits,calls,vcalls,derived,events

def incoming_reg(d,fs,fe,mode):
    lim=min(fe,fs+0x90)
    if mode=="ecx":
        # Preserve raw ECX as valid even if helper doesn't copy it.
        return "ecx"
    if mode=="arg1":
        for p in range(fs,lim-2):
            if d[p]==0x8B:
                mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
                if mod==1 and rm==5 and d[p+2]==0x08 and dst not in (4,5):
                    return REGS[dst]
    return None

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

    roots=[]
    q=deque()
    states=set()
    hits_all=[]
    calls_all=[]
    vcalls_all=[]
    derived_all=[]

    # Concrete roots from owner field.
    for idx,slot,va in methods:
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x7000)
        tr=detect_this_reg(d,fs,fe)
        for lp,objreg in find_gbbw_loads(d,fs,fe,tr):
            roots.append((idx,slot,va,lp,objreg))
            h,c,v,dr,ev=scan_flow(d,lp+6,fe,objreg,0,ib,secs,0x260)
            path=[f"GSslot0x{slot:X}:0x{va:08X}"]
            for row in h:hits_all.append((slot,va,0,path,row))
            for row in c:
                calls_all.append((slot,va,0,path,row))
                cp,dst,mode,origin,r,prep=row
                if -0x100<=origin<=0x180:
                    q.append((slot,dst,mode,origin,1,path+[f"0x{dst:08X}+0x{origin:X}({mode})"]))
            for row in v:vcalls_all.append((slot,va,0,path,row))
            for row in dr:derived_all.append((slot,va,0,path,row))

    MAX_DEPTH=5
    MAX_STATES=1200
    while q and len(states)<MAX_STATES:
        rootslot,va,mode,origin,depth,path=q.popleft()
        key=(va,mode,origin)
        if key in states or depth>MAX_DEPTH:continue
        states.add(key)
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x5000)
        obj=incoming_reg(d,fs,fe,mode)
        if obj is None:continue
        h,c,v,dr,ev=scan_flow(d,fs,fe,obj,origin,ib,secs,min(0x900,fe-fs))
        for row in h:hits_all.append((rootslot,va,depth,path,row))
        for row in c:
            calls_all.append((rootslot,va,depth,path,row))
            cp,dst,nmode,noff,r,prep=row
            if -0x100<=noff<=0x180:
                q.append((rootslot,dst,nmode,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}({nmode})"]))
        for row in v:vcalls_all.append((rootslot,va,depth,path,row))
        for row in dr:derived_all.append((rootslot,va,depth,path,row))

    score={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":20,"CALL_MEM":10,"MEM":5}
    field44=[x for x in hits_all if x[-1][1]==TARGET_FIELD]
    field44.sort(key=lambda x:(-score.get(x[-1][2],0),x[2],x[-1][0]))
    strong=[x for x in field44 if x[-1][2] in ("WRITE","READ_WRITE","ADDRESS")]

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE79_FIXED_ECX_OWNER_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE79-FIXED-ECX-OWNER-FLOW.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*118)
    w(" ReXtreme Phase 79 - FIXED ECX owner-flow from GS_Garage+0x35C")
    w("="*118)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Phase78 bug fixed: a tainted ECX now propagates directly across thiscall CALLs without requiring")
    w("an extra mov ecx,reg. Also tracks common vtable-load -> call [vtable+slot] sequences.")
    w("")

    w("===== ROOT LOADS =====")
    w(f"Count={len(roots)}")
    for idx,slot,va,lp,objreg in roots:
        marker=" BUILD_HANDLER" if va==BUILD_HANDLER else ""
        w(f"slot=0x{slot:X} method=0x{va:08X}{marker} loadFile=0x{lp:08X} objReg={objreg}")
    w("")

    w("===== DIRECT CALLS CARRYING GBBW/DERIVED POINTER =====")
    w(f"Count={len(calls_all)}")
    for rootslot,src,depth,path,row in calls_all[:3000]:
        cp,dst,mode,origin,r,prep=row
        tags=[]
        if dst==BUILD_BUTTON_GETTER:tags.append("BUILD_BUTTON_GETTER")
        if dst==BUILD_CALLBACK:tags.append("BUILD_CALLBACK")
        w(f"rootSlot=0x{rootslot:X} depth={depth} src=0x{src:08X} callFile=0x{cp:08X} -> dst=0x{dst:08X} mode={mode} origin=0x{origin:X} via={r} tags={','.join(tags) if tags else '-'}")
    w("")

    w("===== VIRTUAL CALLS ON GBBW/DERIVED POINTER =====")
    w(f"Count={len(vcalls_all)}")
    for rootslot,src,depth,path,row in vcalls_all[:1800]:
        if len(row)==4:
            p,slot_or_disp,base,kind=row
            w(f"rootSlot=0x{rootslot:X} depth={depth} src=0x{src:08X} callFile=0x{p:08X} kind={kind} slotOrDisp=0x{slot_or_disp:X} base={base}")
        else:
            p,slot_or_disp,base,kind,objorigin=row
            w(f"rootSlot=0x{rootslot:X} depth={depth} src=0x{src:08X} callFile=0x{p:08X} kind={kind} slot=0x{slot_or_disp:X} objOrigin=0x{objorigin:X} base={base}")
    w("")

    w("===== CALLBACK-FIELD HITS =====")
    w(f"Count={len(hits_all)}")
    for rootslot,fn,depth,path,row in sorted(hits_all,key=lambda x:(x[-1][1],-score.get(x[-1][2],0),x[2],x[-1][0])):
        p,eff,kind,base,disp=row
        w(f"field=+0x{eff:X} kind={kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X} base={base} disp={disp:+#x}")
        if eff==TARGET_FIELD or kind in ("WRITE","READ_WRITE","ADDRESS"):
            w(" path="+" -> ".join(path))
            lines.extend(dump(d,p-72,p+144))
    w("")

    w("===== EFFECTIVE +0x44 HITS =====")
    w(f"Count={len(field44)}")
    for rootslot,fn,depth,path,row in field44:
        p,eff,kind,base,disp=row
        w(f"{kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X} base={base} disp={disp:+#x}")
        w(" path="+" -> ".join(path))
    w("")

    w("===== STRONG +0x44 CANDIDATES =====")
    w(f"Count={len(strong)}")
    for rootslot,fn,depth,path,row in strong:
        p,eff,kind,base,disp=row
        w(f"{kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X}")
        w(" path="+" -> ".join(path))
        lines.extend(dump(d,p-96,p+176))
    w("")

    obj={
        "phase":"79-fixed-ecx-owner-flow",
        "ams_sha256":cursha,
        "root_loads":len(roots),
        "helper_states":len(states),
        "direct_carry_calls":len(calls_all),
        "virtual_alias_calls":len(vcalls_all),
        "callback_field_hits":len(hits_all),
        "field44_hits":len(field44),
        "strong_field44_candidates":[
            {
                "kind":x[-1][2],
                "root_slot":f"0x{x[0]:X}",
                "function_va":f"0x{x[1]:08X}",
                "file":f"0x{x[-1][0]:08X}",
                "depth":x[2],
                "path":x[3],
            } for x in strong[:120]
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*118)
    print(" PHASE 79 FIXED ECX OWNER FLOW READY")
    print("="*118)
    print("Root GBBW loads:",len(roots))
    print("Helper states:",len(states))
    print("Direct carry calls:",len(calls_all))
    print("Virtual alias calls:",len(vcalls_all))
    print("Callback-field hits:",len(hits_all))
    print("+0x44 hits:",len(field44))
    print("Strong +0x44 candidates:",len(strong))
    if strong:
        x=strong[0]
        print("TOP:",x[-1][2],hex(x[1]),hex(x[-1][0]),"rootSlot",hex(x[0]),"depth",x[2])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
