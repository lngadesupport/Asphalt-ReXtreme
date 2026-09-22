#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json, bisect
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

GS_VTABLE=0x0186A9CC
GS_CTOR=0x00E00B20
KNOWN_ZERO_CTOR=0x00A722A0
TARGETS={0x354,0x358}
NEAR={0x34C,0x350,0x354,0x358,0x35C,0x360,0x364}
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]
OPS={0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF}

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

def exec_sections(secs):
    return [s for s in secs if s["ch"]&0x20000000]

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in exec_sections(secs):
        if s["raw"]<=f<s["raw"]+s["rs"]: return True
    return False

def build_prologues(d,secs,ib):
    rows=[]
    for s in exec_sections(secs):
        start=s["raw"];end=min(len(d),start+s["rs"]);pos=start
        while True:
            p=d.find(b"\x55\x8B\xEC",pos,end)
            if p<0:break
            rows.append((p,f2v(p,ib,secs),start,end))
            pos=p+3
    rows.sort()
    return rows

def fn_bounds(va,pro,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None,None
    files=[x[0] for x in pro]
    i=bisect.bisect_left(files,fs)
    if i<len(pro) and pro[i][0]==fs:
        end=pro[i+1][0] if i+1<len(pro) and pro[i+1][0]<pro[i][3] else pro[i][3]
        return fs,end
    # fallback within section
    for s in exec_sections(secs):
        if s["raw"]<=fs<s["raw"]+s["rs"]:
            end=min(s["raw"]+s["rs"],fs+0x10000)
            p=d_global.find(b"\x55\x8B\xEC",fs+3,end)
            return fs,p if p>=0 else end
    return fs,min(len(d_global),fs+0x10000)

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
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    return "MEM"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def gs_methods(d,ib,secs,max_slots=160):
    vf=v2f(GS_VTABLE,ib,secs);out=[]
    if vf is None:return out
    for i in range(max_slots):
        o=vf+i*4
        if o+4>len(d):break
        va=u32(d,o)
        if is_exec_va(va,ib,secs):
            out.append((i,i*4,va))
    return out

def incoming_arg_offset(mode):
    if mode=="ecx":return None
    if mode.startswith("arg"):
        n=int(mode[3:])
        return 8+4*(n-1)
    return None

def seed_taint(d,fs,fe,mode,origin):
    if mode=="ecx":
        return {"ecx":origin}
    off=incoming_arg_offset(mode)
    if off is None:return {}
    # Find mov reg,[ebp+off] near prologue. If absent, raw stack use will be handled separately.
    lim=min(fe,fs+0x100)
    for p in range(fs,lim-2):
        if d[p]==0x8B:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==1 and rm==5 and d[p+2]==off:
                return {REGS[dst]:origin}
            if mod==2 and rm==5 and p+6<=lim and i32(d,p+2)==off:
                return {REGS[dst]:origin}
    return {}

def stack_arg_taint(d,fs,pushes,taint):
    # pushes contains recent (file, origin, reg). Last push is arg1.
    out=[]
    for idx,(pp,origin,r) in enumerate(reversed(pushes[-4:]),1):
        out.append((f"arg{idx}",origin,r,pp))
    return out

def scan_fn(d,va,mode,origin,pro,ib,secs):
    fs,fe=fn_bounds(va,pro,ib,secs)
    if fs is None:return None
    taint=seed_taint(d,fs,fe,mode,origin)
    hits=[];calls=[];derived=[];events=[]
    recent_pushes=[]
    p=fs
    while p<fe:
        op=d[p]
        if op in (0xC3,0xCB,0xC2,0xCA):break

        # mov reg,reg
        if op==0x8B and p+2<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=(mr>>3)&7
            if mod==3:
                s=REGS[rm];t=REGS[dst]
                if s in taint:
                    taint[t]=taint[s];events.append((p,"ALIAS",t,s,taint[t]))
                else:
                    taint.pop(t,None)
                p+=2;continue

            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in NEAR:hits.append((p,eff,classify(op,mr),base,disp))
                    taint.pop(t,None)
                else:
                    taint.pop(t,None)
                p+=ln;continue

        # lea derived pointer
        if op==0x8D and p+2<=fe:
            mr=d[p+1];dst=(mr>>3)&7
            dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm];t=REGS[dst]
                if base in taint:
                    taint[t]=taint[base]+disp
                    derived.append((p,t,taint[t],base,disp))
                    if taint[t] in NEAR:hits.append((p,taint[t],"ADDRESS",base,disp))
                else:
                    taint.pop(t,None)
                p+=ln;continue

        # memory operations
        if op in OPS and p+2<=fe:
            mr=d[p+1];dec=decode_mem(d,p,fe)
            if dec:
                rm,disp,ln=dec;base=REGS[rm]
                if base in taint:
                    eff=taint[base]+disp
                    if eff in NEAR:hits.append((p,eff,classify(op,mr),base,disp))
                p+=ln;continue

        # add/sub pointer immediate
        if op in (0x83,0x81) and p+3<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;ext=(mr>>3)&7;r=REGS[rm]
            if mod==3 and r in taint and ext in (0,5):
                if op==0x83: imm=i8v(d[p+2]);ln=3
                else:
                    if p+6>fe:break
                    imm=i32(d,p+2);ln=6
                if ext==5:imm=-imm
                taint[r]+=imm
                derived.append((p,r,taint[r],r,imm))
                p+=ln;continue

        # push tainted register
        if 0x50<=op<=0x57:
            r=REGS[op-0x50]
            if r in taint:
                recent_pushes.append((p,taint[r],r))
                if len(recent_pushes)>8:recent_pushes=recent_pushes[-8:]
            p+=1;continue

        # direct call
        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                # thiscall propagation
                if "ecx" in taint:
                    calls.append((p,dst,"ecx",taint["ecx"],"ecx",p))
                # stack argument propagation (derived pair addresses included)
                for amode,aorigin,areg,pp in stack_arg_taint(d,fs,recent_pushes,taint):
                    calls.append((p,dst,amode,aorigin,areg,pp))
            recent_pushes=[]
            # caller-saved
            for r in ("eax","ecx","edx"):taint.pop(r,None)
            p+=5;continue

        # conservative: clear push window on branches/jumps
        if 0x70<=op<=0x7F or op in (0xE9,0xEB):
            recent_pushes=[]
        p+=1
    return fs,fe,hits,calls,derived,events

def main():
    global d_global
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes();d_global=d

    print("[1/6] Verificando estado...",flush=True)
    for n,o,e in [
        ("Phase53",P53_OFF,P53),("Phase54",P54_OFF,P54),("Phase55",P55_OFF,P55),
        ("Phase63Reverted",P63_OFF,PRE63),("Phase65Reverted",P65_OFF,PRE65),
        ("GlobalIsOnlineFALSE",GLOBAL_OFF,GLOBAL_FALSE),("Phase36Popup",POPUP_OFF,POPUP)
    ]:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    ib,secs=parse_pe(d)
    print("[2/6] Indexando funcoes...",flush=True)
    pro=build_prologues(d,secs,ib)
    methods=gs_methods(d,ib,secs,160)
    print(f"      GS vtable methods: {len(methods)}",flush=True)

    print("[3/6] Seguindo o MESMO GS_Garage this pelos helpers...",flush=True)
    q=deque()
    for idx,slot,va in methods:
        q.append((slot,va,"ecx",0,0,[f"GSslot0x{slot:X}:0x{va:08X}"]))
    # Constructor as a separate typed root, useful for generic post-init helpers reached from ctor.
    q.append((-1,GS_CTOR,"ecx",0,0,[f"GS_CTOR:0x{GS_CTOR:08X}"]))

    seen=set();hits_all=[];calls_all=[];derived_all=[]
    MAX_DEPTH=5;MAX_STATES=6000

    while q and len(seen)<MAX_STATES:
        rootslot,va,mode,origin,depth,path=q.popleft()
        key=(va,mode,origin)
        if key in seen or depth>MAX_DEPTH:continue
        seen.add(key)
        a=scan_fn(d,va,mode,origin,pro,ib,secs)
        if not a:continue
        fs,fe,hits,calls,derived,events=a
        for h in hits:hits_all.append((rootslot,va,mode,origin,depth,path,h))
        for dr in derived:derived_all.append((rootslot,va,mode,origin,depth,path,dr))
        for c in calls:
            calls_all.append((rootslot,va,mode,origin,depth,path,c))
            cp,dst,nmode,noff,r,prep=c
            if depth<MAX_DEPTH and -0x100<=noff<=0x500:
                q.append((rootslot,dst,nmode,noff,depth+1,path+[f"0x{dst:08X}+0x{noff:X}({nmode})"]))

    print(f"      states={len(seen)} calls={len(calls_all)} hits={len(hits_all)}",flush=True)

    target_hits=[x for x in hits_all if x[-1][1] in TARGETS]
    strong=[x for x in target_hits if x[-1][2] in ("WRITE","READ_WRITE","ADDRESS")]
    # Exclude the known base-ctor zero init from post-init shortlist.
    postinit=[x for x in strong if x[1]!=KNOWN_ZERO_CTOR]

    # Pair-address carrying calls: effective origin exactly +354/+358 into helper args/ecx.
    pair_calls=[x for x in calls_all if x[-1][3] in TARGETS]

    score={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":20,"CALL_MEM":10,"MEM":5}
    postinit.sort(key=lambda x:(-score.get(x[-1][2],0),x[4],x[-1][0]))
    pair_calls.sort(key=lambda x:(x[4],x[-1][0]))

    print("[4/6] Classificando setters e helpers do par...",flush=True)
    print(f"      target hits={len(target_hits)} strong={len(strong)} post-init={len(postinit)} pair-carry calls={len(pair_calls)}",flush=True)
    if postinit:
        x=postinit[0]
        print(f"      TOP SETTER: {x[-1][2]} fn=0x{x[1]:08X} file=0x{x[-1][0]:08X} depth={x[4]}",flush=True)
    if pair_calls:
        x=pair_calls[0]
        print(f"      TOP PAIR HELPER: dst=0x{x[-1][1]:08X} origin=0x{x[-1][3]:X} mode={x[-1][2]}",flush=True)

    print("[5/6] Gerando relatorio...",flush=True)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE83_TYPED_GS_THIS_FLOW"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE83-TYPED-GS-THIS-FLOW.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*124)
    w(" ReXtreme Phase 83 - typed GS_Garage this-flow to +0x354/+0x358")
    w("="*124)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Unlike Phase82, this phase does NOT rank by ancestry alone.")
    w("It starts from actual GS_Garage vtable methods/ctor and follows the same object pointer")
    w("through ECX aliases, LEA-derived subobject addresses, and up to four stack arguments.")
    w(f"GSMethods={len(methods)} States={len(seen)} CarryCalls={len(calls_all)}")
    w("")

    w("===== TARGET +0x354/+0x358 HITS ON TYPED GS THIS =====")
    w(f"Count={len(target_hits)}")
    for rec in sorted(target_hits,key=lambda x:(x[-1][1],-score.get(x[-1][2],0),x[4],x[-1][0])):
        rootslot,fn,mode,origin,depth,path,h=rec
        p,eff,kind,base,disp=h
        w(f"field=+0x{eff:X} kind={kind} rootSlot={('CTOR' if rootslot==-1 else '0x%X'%rootslot)} depth={depth} fn=0x{fn:08X} mode={mode} origin=0x{origin:X} file=0x{p:08X} base={base} disp={disp:+#x}")
        w(" path="+" -> ".join(path))
        lines.extend(dump(d,p-64,p+128))
    w("")

    w("===== POST-CONSTRUCTOR STRONG SETTER/ADDRESS CANDIDATES =====")
    w(f"Count={len(postinit)}")
    for rec in postinit[:200]:
        rootslot,fn,mode,origin,depth,path,h=rec
        p,eff,kind,base,disp=h
        w(f"{kind} field=+0x{eff:X} rootSlot={('CTOR' if rootslot==-1 else '0x%X'%rootslot)} depth={depth} fn=0x{fn:08X} file=0x{p:08X}")
        w(" path="+" -> ".join(path))
        lines.extend(dump(d,p-96,p+176))
    w("")

    w("===== CALLS CARRYING &GS+0x354 / &GS+0x358 =====")
    w(f"Count={len(pair_calls)}")
    for rec in pair_calls[:400]:
        rootslot,src,smode,sorigin,depth,path,c=rec
        cp,dst,nmode,noff,r,prep=c
        w(f"origin=+0x{noff:X} rootSlot={('CTOR' if rootslot==-1 else '0x%X'%rootslot)} depth={depth} src=0x{src:08X} callFile=0x{cp:08X} -> dst=0x{dst:08X} mode={nmode} via={r}")
        w(" path="+" -> ".join(path))
        lines.extend(dump(d,cp-56,cp+88))
    w("")

    w("===== ALL NEAR-FIELD HITS (0x34C..0x364) =====")
    w(f"Count={len(hits_all)}")
    for rec in sorted(hits_all,key=lambda x:(x[-1][1],x[4],x[-1][0]))[:1200]:
        rootslot,fn,mode,origin,depth,path,h=rec
        p,eff,kind,base,disp=h
        w(f"+0x{eff:X} {kind} rootSlot={('CTOR' if rootslot==-1 else '0x%X'%rootslot)} depth={depth} fn=0x{fn:08X} file=0x{p:08X}")
    w("")

    obj={
      "phase":"83-typed-gs-this-flow",
      "ams_sha256":cursha,
      "gs_methods":len(methods),
      "states":len(seen),
      "carry_calls":len(calls_all),
      "target_hits":len(target_hits),
      "strong_target_hits":len(strong),
      "postinit_candidates":[
        {
          "kind":x[-1][2],
          "field":f"0x{x[-1][1]:X}",
          "root_slot":"CTOR" if x[0]==-1 else f"0x{x[0]:X}",
          "function_va":f"0x{x[1]:08X}",
          "file":f"0x{x[-1][0]:08X}",
          "depth":x[4],
          "path":x[5]
        } for x in postinit[:100]
      ],
      "pair_carry_helpers":[
        {
          "origin":f"0x{x[-1][3]:X}",
          "root_slot":"CTOR" if x[0]==-1 else f"0x{x[0]:X}",
          "src_va":f"0x{x[1]:08X}",
          "dst_va":f"0x{x[-1][1]:08X}",
          "call_file":f"0x{x[-1][0]:08X}",
          "mode":x[-1][2],
          "depth":x[4],
          "path":x[5]
        } for x in pair_calls[:150]
      ],
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("[6/6] PHASE 83 OK",flush=True)
    print("Report:",report,flush=True)
    print("Summary:",summary,flush=True)

if __name__=="__main__":
    main()
