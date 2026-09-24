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

GS_VTABLE=0x0186A9CC
GBBW_OWNER_FIELD=0x35C
BUILD_HANDLER=0x00A87960
BUILD_CALLBACK=0x00973C90
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

def scan_alias_window(d,start,fe,objreg,ib,secs,window=0x220):
    z=min(fe,start+window)
    taint={objreg:0}
    hits=[];calls=[];vcalls=[];derived=[]
    p=start
    while p<z:
        op=d[p]

        # register copy
        if op==0x8B and p+2<=z:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint: taint[t]=taint[s]
                else: taint.pop(t,None)
                p+=2;continue

            dec=decode_mem(d,p,z)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in CALLBACK_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                    # value load kills pointer taint in dst
                    taint.pop(REGS[dst],None)
                p+=ln;continue

        # lea derived pointer
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
                else: taint.pop(t,None)
                p+=ln;continue

        # memory op on tainted alias
        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=z:
            mr=d[p+1];dec=decode_mem(d,p,z)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in CALLBACK_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                    # virtual call directly on alias: call [reg+slot]
                    ext=(mr>>3)&7
                    if op==0xFF and ext==2:
                        vcalls.append((p,eff,base))
                p+=ln;continue

        # direct call; record any tainted reg moved to ECX or pushed within 32 bytes
        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                lo=max(start,p-36)
                cands=[]
                for r,off in list(taint.items()):
                    rid=REGS.index(r)
                    pat1=bytes([0x8B,0xC8|rid])     # mov ecx,r
                    pat2=bytes([0x89,0xC1|(rid<<3)])# mov ecx,r
                    q=max(d.rfind(pat1,lo,p),d.rfind(pat2,lo,p))
                    if q>=0:cands.append((q,"ecx",off,r))
                    q2=d.rfind(bytes([0x50+rid]),lo,p)
                    if q2>=0:cands.append((q2,"arg1",off,r))
                if cands:
                    cands.sort(reverse=True)
                    prep,mode,off,r=cands[0]
                    calls.append((p,dst,mode,off,r,prep))
            p+=5;continue

        p+=1
    return hits,calls,vcalls,derived

def analyze_helper(d,va,mode,origin,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,0x5000)
    # identify incoming object register
    obj=None
    lim=min(fe,fs+0x80)
    if mode=="ecx":
        pats=[(b"\x8B\xF1","esi"),(b"\x8B\xF9","edi"),(b"\x8B\xD9","ebx"),(b"\x8B\xC1","eax")]
        best=None
        for pat,r in pats:
            p=d.find(pat,fs,lim)
            if p>=0 and (best is None or p<best[0]):best=(p,r)
        obj=best[1] if best else "ecx"
    else:
        for p in range(fs,lim-2):
            if d[p]==0x8B:
                mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
                if mod==1 and rm==5 and d[p+2]==0x08:
                    obj=REGS[dst];break
    if obj is None:return fs,fe,None,[],[],[],[]
    hits,calls,vcalls,derived=scan_alias_window(d,fs,fe,obj,ib,secs,window=min(0x700,fe-fs))
    # adjust effective offsets by origin
    adj=[]
    for p,eff,kind,base,disp in hits:
        adj.append((p,origin+eff,kind,base,disp))
    adjd=[]
    for p,r,eff,base,disp in derived:
        adjd.append((p,r,origin+eff,base,disp))
    adjc=[]
    for p,dst,nmode,off,r,prep in calls:
        adjc.append((p,dst,nmode,origin+off,r,prep))
    adjv=[]
    for p,eff,base in vcalls:
        adjv.append((p,origin+eff,base))
    return fs,fe,obj,adj,adjc,adjv,adjd

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
    all_hits=[]
    all_calls=[]
    all_vcalls=[]
    all_derived=[]
    q=deque()
    seen=set()

    # Concrete starts: every load of GS_Garage+0x35C.
    for idx,slot,va in methods:
        fs=v2f(va,ib,secs)
        if fs is None:continue
        fe=next_prologue(d,fs,0x7000)
        tr=detect_this_reg(d,fs,fe)
        for lp,objreg in find_gbbw_loads(d,fs,fe,tr):
            roots.append((idx,slot,va,lp,objreg))
            hits,calls,vcalls,derived=scan_alias_window(d,lp+6,fe,objreg,ib,secs,0x260)
            for h in hits:all_hits.append(("GS",slot,va,lp,objreg,0,[f"GSslot0x{slot:X}:0x{va:08X}"],h))
            for c in calls:
                all_calls.append(("GS",slot,va,lp,objreg,0,c))
                cp,dst,mode,origin,r,prep=c
                if -0x100<=origin<=0x180:
                    q.append((slot,va,dst,mode,origin,1,[f"GSslot0x{slot:X}:0x{va:08X}",f"0x{dst:08X}+0x{origin:X}({mode})"]))
            for v in vcalls:all_vcalls.append(("GS",slot,va,lp,objreg,0,v))
            for dr in derived:all_derived.append(("GS",slot,va,lp,objreg,0,dr))

    # Follow a narrow helper chain from those concrete roots.
    MAX_DEPTH=4
    while q:
        rootslot,rootva,va,mode,origin,depth,path=q.popleft()
        key=(va,mode,origin)
        if key in seen:continue
        seen.add(key)
        if depth>MAX_DEPTH:continue
        a=analyze_helper(d,va,mode,origin,ib,secs)
        if not a:continue
        fs,fe,obj,hits,calls,vcalls,derived=a
        for h in hits:all_hits.append(("HELPER",rootslot,va,fs,obj,depth,path,h))
        for c in calls:
            all_calls.append(("HELPER",rootslot,va,fs,obj,depth,c))
            cp,dst,nmode,noff,r,prep=c
            if depth<MAX_DEPTH and -0x100<=noff<=0x180:
                q.append((rootslot,rootva,dst,nmode,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}({nmode})"]))
        for v in vcalls:all_vcalls.append(("HELPER",rootslot,va,fs,obj,depth,v))
        for dr in derived:all_derived.append(("HELPER",rootslot,va,fs,obj,depth,dr))

    score={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":20,"CALL_MEM":10,"MEM":5}
    field44=[]
    strong=[]
    for rec in all_hits:
        h=rec[-1];p,eff,kind,base,disp=h
        if eff==0x44:
            field44.append(rec)
            if kind in ("WRITE","READ_WRITE","ADDRESS"):strong.append(rec)
    field44.sort(key=lambda rec:(-score.get(rec[-1][2],0),rec[5],rec[-1][0]))
    strong.sort(key=lambda rec:(-score.get(rec[-1][2],0),rec[5],rec[-1][0]))

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE78_GS_OWNER_ALIAS_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE78-GS-OWNER-ALIAS-FLOW.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*116)
    w(" ReXtreme Phase 78 - GS_Garage owner-side alias flow from field +0x35C to GBBW callback fields")
    w("="*116)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Starts only from confirmed GS_Garage+0x35C loads, then tracks aliases, LEA-derived pointers,")
    w("direct memory ops, virtual calls, and a narrow direct-helper chain.")
    w("")

    w("===== CONFIRMED ROOT LOADS =====")
    w(f"Count={len(roots)}")
    for idx,slot,va,lp,objreg in roots:
        marker=" BUILD_HANDLER" if va==BUILD_HANDLER else ""
        w(f"slot=0x{slot:X} method=0x{va:08X}{marker} loadFile=0x{lp:08X} objReg={objreg}")
    w("")

    w("===== CALLBACK-FIELD HITS FROM OWNER-SIDE ALIAS FLOW =====")
    w(f"Count={len(all_hits)}")
    for rec in sorted(all_hits,key=lambda r:(r[-1][1],-score.get(r[-1][2],0),r[5],r[-1][0])):
        origin_kind,rootslot,fn,basefile,obj,depth,path,h=rec
        p,eff,kind,basereg,disp=h
        w(f"field=+0x{eff:X} kind={kind} origin={origin_kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X} baseReg={basereg} localDisp={disp:+#x}")
        if eff==0x44 or kind in ("WRITE","READ_WRITE","ADDRESS"):
            lines.extend(dump(d,p-64,p+128))
    w("")

    w("===== EFFECTIVE +0x44 HITS =====")
    w(f"Count={len(field44)}")
    for rec in field44:
        origin_kind,rootslot,fn,basefile,obj,depth,path,h=rec
        p,eff,kind,basereg,disp=h
        w(f"{kind} origin={origin_kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X}")
        if isinstance(path,list):w(" path="+" -> ".join(path))
        lines.extend(dump(d,p-80,p+144))
    w("")

    w("===== STRONG +0x44 SETTER/ADDRESS CANDIDATES =====")
    w(f"Count={len(strong)}")
    for rec in strong:
        origin_kind,rootslot,fn,basefile,obj,depth,path,h=rec
        p,eff,kind,basereg,disp=h
        w(f"{kind} origin={origin_kind} rootSlot=0x{rootslot:X} depth={depth} fn=0x{fn:08X} file=0x{p:08X}")
        if isinstance(path,list):w(" path="+" -> ".join(path))
    w("")

    w("===== DIRECT CALLS CARRYING GBBW OR DERIVED POINTER =====")
    w(f"Count={len(all_calls)}")
    for rec in all_calls[:2400]:
        origin_kind,rootslot,src,basefile,obj,depth,c=rec
        cp,dst,mode,off,r,prep=c
        w(f"origin={origin_kind} rootSlot=0x{rootslot:X} depth={depth} src=0x{src:08X} prep=0x{prep:08X} call=0x{cp:08X} -> dst=0x{dst:08X} mode={mode} effectiveOrigin=0x{off:X} via={r}")
    w("")

    w("===== VIRTUAL CALLS ON GBBW/DERIVED ALIASES =====")
    w(f"Count={len(all_vcalls)}")
    for rec in all_vcalls[:1200]:
        origin_kind,rootslot,src,basefile,obj,depth,v=rec
        p,eff,base=v
        w(f"origin={origin_kind} rootSlot=0x{rootslot:X} depth={depth} src=0x{src:08X} callFile=0x{p:08X} effectiveSlotOrDisp=0x{eff:X} base={base}")
    w("")

    objout={
        "phase":"78-gs-owner-alias-flow",
        "ams_sha256":cursha,
        "root_loads":len(roots),
        "helper_states":len(seen),
        "callback_field_hits":len(all_hits),
        "field44_hits":len(field44),
        "strong_field44_candidates":[
            {
                "kind":rec[-1][2],
                "root_slot":f"0x{rec[1]:X}",
                "function_va":f"0x{rec[2]:08X}",
                "file":f"0x{rec[-1][0]:08X}",
                "depth":rec[5],
                "path":rec[6] if isinstance(rec[6],list) else []
            } for rec in strong[:120]
        ],
        "direct_carry_calls":len(all_calls),
        "virtual_alias_calls":len(all_vcalls),
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(objout,indent=2),encoding="utf-8")

    print("="*116)
    print(" PHASE 78 GS OWNER ALIAS FLOW READY")
    print("="*116)
    print("Root GBBW loads:",len(roots))
    print("Helper states:",len(seen))
    print("Callback-field hits:",len(all_hits))
    print("+0x44 hits:",len(field44))
    print("Strong +0x44 candidates:",len(strong))
    print("Direct carry calls:",len(all_calls))
    print("Virtual alias calls:",len(all_vcalls))
    if strong:
        r=strong[0]
        print("TOP:",r[-1][2],hex(r[2]),hex(r[-1][0]),"rootSlot",hex(r[1]),"depth",r[5])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
