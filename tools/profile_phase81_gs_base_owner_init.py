#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json
from pathlib import Path
from collections import deque

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

P53_OFF=0x00574FA7; P53=bytes.fromhex("6A 01 90")
P54_OFF=0x0059F3F2; P54=bytes.fromhex("B8 02 00 00 00 90")
P55_OFF=0x00573C45; P55=bytes.fromhex("90 90 90 90 90 90")
P63_OFF=0x00573CF4; PRE63=bytes.fromhex("74 0B")
P65_OFF=0x0056E9CE; PRE65=bytes.fromhex("0F 94 45 E3")
GLOBAL_OFF=0x00BACDD0; GLOBAL_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")
POPUP_OFF=0x009168B0; POPUP=bytes.fromhex("31 C0 C2 18 00")

GS_CTOR=0x00E00B20
GS_BASE_CTOR=0x00B070C0
GS_VTABLE=0x0186A9CC
TARGET_FIELDS={0x354,0x358}
NEAR_FIELDS={0x34C,0x350,0x354,0x358,0x35C,0x360,0x364}
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

def next_prologue(d,start,limit=0x12000):
    p=d.find(b"\x55\x8B\xEC",start+3,min(len(d),start+limit))
    return p if p>=0 else min(len(d),start+limit)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:return rm,i8v(d[p+2]),3
    if mod==2 and p+6<=fe:return rm,i32(d,p+2),6
    return None

def classify(op,mr):
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op==0xFF and ((mr>>3)&7)==2:return "CALL_MEM"
    if op==0xFF and ((mr>>3)&7) in (0,1):return "READ_WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    return "MEM"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def find_this_alias(d,fs,fe):
    # Preserve ECX and common copies from ECX near prologue.
    taint={"ecx":0}
    lim=min(fe,fs+0x120)
    p=fs
    while p<lim:
        if d[p]==0x8B and p+2<=lim:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint: taint[t]=taint[s]
        p+=1
    return taint

def scan_function(d,va,origin,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None
    fe=next_prologue(d,fs,0x12000)
    taint=find_this_alias(d,fs,fe)
    # apply inherited origin to all current this aliases
    taint={r:origin for r in taint}
    hits=[];calls=[];ptrstores=[];p=fs
    while p<fe:
        op=d[p]

        if op==0x8B and p+2<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint: taint[t]=taint[s]
                else: taint.pop(t,None)
                p+=2;continue
            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in NEAR_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                    taint.pop(REGS[dst],None)
                p+=ln;continue

        if op==0x8D and p+2<=fe:
            mr=d[p+1];dst=(mr>>3)&7
            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    taint[t]=taint[base]+disp
                    if taint[t] in NEAR_FIELDS:
                        hits.append((p,taint[t],"ADDRESS",base,disp))
                else: taint.pop(t,None)
                p+=ln;continue

        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=fe:
            mr=d[p+1];dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in NEAR_FIELDS:
                        hits.append((p,eff,classify(op,mr),base,disp))
                        # Record source register/value form for writes.
                        if op==0x89:
                            src=REGS[(mr>>3)&7]
                            ptrstores.append((p,eff,"REG",src))
                        elif op==0xC7 and p+ln+4<=fe:
                            imm=u32(d,p+ln)
                            ptrstores.append((p,eff,"IMM",imm))
                p+=ln;continue

        if op in (0x83,0x81) and p+3<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;ext=(mr>>3)&7
            r=REGS[rm]
            if mod==3 and r in taint and ext in (0,5):
                if op==0x83:
                    imm=i8v(d[p+2]);ln=3
                else:
                    if p+6>fe:break
                    imm=i32(d,p+2);ln=6
                if ext==5:imm=-imm
                taint[r]+=imm
                p+=ln;continue

        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                # thiscall preservation: current ECX alias wins.
                if "ecx" in taint:
                    calls.append((p,dst,taint["ecx"],"ecx"))
                else:
                    lo=max(fs,p-32)
                    cands=[]
                    for r,off in taint.items():
                        rid=REGS.index(r)
                        pat1=bytes([0x8B,0xC8|rid])
                        pat2=bytes([0x89,0xC1|(rid<<3)])
                        q=max(d.rfind(pat1,lo,p),d.rfind(pat2,lo,p))
                        if q>=0:cands.append((q,dst,off,r))
                    if cands:
                        cands.sort(reverse=True)
                        q0,dst0,off0,r0=cands[0]
                        calls.append((p,dst0,off0,r0))
                for r in ("eax","ecx","edx"): taint.pop(r,None)
            p+=5;continue

        p+=1
    return fs,fe,hits,calls,ptrstores

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

    q=deque([(GS_BASE_CTOR,0,0,[f"0x{GS_BASE_CTOR:08X}+0x0"])])
    seen=set()
    nodes=[]
    edges=[]
    hits_all=[]
    stores_all=[]
    MAX_DEPTH=7
    MAX_NODES=1200

    while q and len(seen)<MAX_NODES:
        va,origin,depth,path=q.popleft()
        key=(va,origin)
        if key in seen or depth>MAX_DEPTH:continue
        seen.add(key)
        a=scan_function(d,va,origin,ib,secs)
        if not a:continue
        fs,fe,hits,calls,stores=a
        nodes.append((va,origin,depth,fs,fe,path))
        for h in hits:
            hits_all.append((va,origin,depth,path,h))
        for st in stores:
            stores_all.append((va,origin,depth,path,st))
        for cp,dst,noff,via in calls:
            edges.append((va,origin,depth,cp,dst,noff,via,path))
            if -0x100<=noff<=0x500:
                q.append((dst,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}"]))

    target_hits=[x for x in hits_all if x[-1][1] in TARGET_FIELDS]
    target_stores=[x for x in stores_all if x[-1][1] in TARGET_FIELDS]

    outdir=root/"_PACKAGE_PHASE5"/"_PHASE81_GS_BASE_OWNER_INIT"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE81-GS-BASE-OWNER-INIT.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*120)
    w(" ReXtreme Phase 81 - GS_Garage base-constructor chain -> owner pair +0x354/+0x358")
    w("="*120)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w(f"GS_Garage ctor=0x{GS_CTOR:08X}")
    w(f"first base ctor=0x{GS_BASE_CTOR:08X}")
    w("")

    w("===== BASE-CTOR GRAPH =====")
    w(f"Nodes={len(nodes)} Edges={len(edges)}")
    for va,origin,depth,fs,fe,path in nodes:
        w(f"node=0x{va:08X} origin=0x{origin:X} depth={depth} file=0x{fs:08X} end=0x{fe:08X}")
    w("")

    w("===== EFFECTIVE FIELD HITS NEAR OWNER PAIR =====")
    w(f"Count={len(hits_all)}")
    for va,origin,depth,path,h in sorted(hits_all,key=lambda x:(x[-1][1],x[2],x[-1][0])):
        p,eff,kind,base,disp=h
        w(f"field=+0x{eff:X} kind={kind} fn=0x{va:08X} origin=0x{origin:X} depth={depth} file=0x{p:08X} base={base} disp={disp:+#x}")
        if eff in TARGET_FIELDS or kind in ("WRITE","READ_WRITE","ADDRESS"):
            w(" path="+" -> ".join(path))
            lines.extend(dump(d,p-72,p+144))
    w("")

    w("===== TARGET +0x354/+0x358 HITS =====")
    w(f"Count={len(target_hits)}")
    for va,origin,depth,path,h in target_hits:
        p,eff,kind,base,disp=h
        w(f"{kind} field=+0x{eff:X} fn=0x{va:08X} origin=0x{origin:X} depth={depth} file=0x{p:08X}")
        w(" path="+" -> ".join(path))
    w("")

    w("===== TARGET WRITES WITH SOURCE FORM =====")
    w(f"Count={len(target_stores)}")
    for va,origin,depth,path,st in target_stores:
        p,eff,stype,src=st
        if stype=="REG":
            sval=src
        else:
            sval=f"0x{src:08X}"
        w(f"WRITE field=+0x{eff:X} fn=0x{va:08X} file=0x{p:08X} sourceType={stype} source={sval} depth={depth}")
        w(" path="+" -> ".join(path))
        lines.extend(dump(d,p-96,p+176))
    w("")

    # Dump first base ctor body explicitly.
    bf=v2f(GS_BASE_CTOR,ib,secs);be=next_prologue(d,bf,0x12000)
    w("===== FIRST BASE CTOR BODY =====")
    lines.extend(dump(d,bf,be))
    w("")

    obj={
      "phase":"81-gs-base-owner-init",
      "ams_sha256":cursha,
      "gs_ctor":f"0x{GS_CTOR:08X}",
      "first_base_ctor":f"0x{GS_BASE_CTOR:08X}",
      "nodes":len(nodes),
      "edges":len(edges),
      "target_hits":len(target_hits),
      "target_writes":[
        {
          "function_va":f"0x{x[0]:08X}",
          "file":f"0x{x[-1][0]:08X}",
          "field":f"0x{x[-1][1]:X}",
          "source_type":x[-1][2],
          "source":x[-1][3] if isinstance(x[-1][3],str) else f"0x{x[-1][3]:08X}",
          "depth":x[2],
          "path":x[3]
        } for x in target_stores
      ],
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("="*120)
    print(" PHASE 81 GS BASE OWNER INIT READY")
    print("="*120)
    print("Base-ctor nodes:",len(nodes))
    print("Edges:",len(edges))
    print("Target +0x354/+0x358 hits:",len(target_hits))
    print("Target writes:",len(target_stores))
    if target_stores:
        x=target_stores[0]
        print("TOP WRITE:",hex(x[-1][1]),hex(x[0]),hex(x[-1][0]),x[-1][2],x[-1][3])
    print("No gameplay bytes were changed.")
    print("Report:",report)
    print("Summary:",summary)

if __name__=="__main__":
    main()
