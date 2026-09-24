#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json, bisect
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
TARGETS=(0x354,0x358)
NEAR=(0x350,0x354,0x358,0x35C,0x360,0x364,0x368)
REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]
OPS={0x8B,0x89,0x8D,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF}

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
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

def exec_sections(secs): return [s for s in secs if s["ch"]&0x20000000]

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    return any(s["raw"]<=f<s["raw"]+s["rs"] for s in exec_sections(secs))

def build_prologues(d,secs,ib):
    rows=[]
    for s in exec_sections(secs):
        a=s["raw"];b=min(len(d),a+s["rs"]);p=a
        while True:
            q=d.find(b"\x55\x8B\xEC",p,b)
            if q<0:break
            rows.append((q,f2v(q,ib,secs),a,b));p=q+3
    rows.sort()
    return rows

def fn_for_file(off,pro):
    files=[x[0] for x in pro]
    i=bisect.bisect_right(files,off)-1
    if i<0:return None
    fs,va,a,b=pro[i]
    if a<=off<b:return va
    return None

def fn_bounds(va,pro,ib,secs,d):
    fs=v2f(va,ib,secs)
    if fs is None:return None,None
    files=[x[0] for x in pro]
    i=bisect.bisect_left(files,fs)
    if i<len(pro) and pro[i][0]==fs:
        end=pro[i+1][0] if i+1<len(pro) and pro[i+1][0]<pro[i][3] else pro[i][3]
        return fs,end
    return fs,min(len(d),fs+0x10000)

def dump(d,a,z):
    return [f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)])
            for p in range(max(0,a),min(len(d),z),16)]

def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
    if rm==4:return None
    if mod==0:return rm,0,2
    if mod==1 and p+3<=fe:
        x=d[p+2];return rm,(x-256 if x>=128 else x),3
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
    return "READ"

def direct_target(d,p,ib,secs):
    if p+5>len(d) or d[p]!=0xE8:return None
    sva=f2v(p,ib,secs)
    if sva is None:return None
    dst=(sva+5+i32(d,p+1))&0xffffffff
    return dst if is_exec_va(dst,ib,secs) else None

def build_call_index(d,secs,ib,pro):
    callers=defaultdict(list)
    for s in exec_sections(secs):
        a=s["raw"];b=min(len(d)-5,a+s["rs"]-5);p=a
        while True:
            q=d.find(b"\xE8",p,b+1)
            if q<0:break
            dst=direct_target(d,q,ib,secs)
            if dst is not None:
                callers[dst].append((q,fn_for_file(q,pro)))
            p=q+1
    return callers

def scan_candidate_functions(d,secs,ib,pro):
    byfn=defaultdict(list)
    pats={disp:struct.pack("<I",disp) for disp in NEAR}
    for disp,pat in pats.items():
        for s in exec_sections(secs):
            a=s["raw"];b=min(len(d),a+s["rs"]);pos=a
            while True:
                q=d.find(pat,pos,b)
                if q<0:break
                p=q-2
                if p>=a and d[p] in OPS:
                    mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
                    if mod==2 and rm!=4:
                        fn=fn_for_file(p,pro)
                        if fn is not None:
                            byfn[fn].append((p,disp,d[p],mr,REGS[rm]))
                pos=q+1
    return byfn

def backtrace_reg_source(d,fs,p,reg,max_back=48):
    rid=REGS.index(reg)
    lo=max(fs,p-max_back)
    q=p-1
    while q>=lo:
        # mov reg,[ebp+disp8/disp32]
        if q+3<=p and d[q]==0x8B:
            mr=d[q+1];dst=(mr>>3)&7;mod=(mr>>6)&3;rm=mr&7
            if dst==rid and rm==5:
                if mod==1:
                    off=d[q+2];off=off-256 if off>=128 else off
                    if off>=8 and off%4==0:return ("ARG",off,q)
                elif mod==2 and q+6<=p:
                    off=i32(d,q+2)
                    if off>=8 and off%4==0:return ("ARG",off,q)
            if dst==rid and mod==3:
                return ("REG",REGS[rm],q)
        # xor reg,reg => zero
        if q+2<=p and d[q]==0x31:
            mr=d[q+1]
            if ((mr>>3)&7)==rid and (mr&7)==rid and ((mr>>6)&3)==3:
                return ("ZERO",0,q)
        q-=1
    return ("UNKNOWN",reg,None)

def classify_write(d,fs,fe,p,disp,op,mr):
    if op==0xC7:
        dec=decode_mem(d,p,fe)
        if dec:
            _,_,ln=dec
            if p+ln+4<=fe:
                imm=u32(d,p+ln)
                if imm==0:return ("ZERO_INIT",0)
                return ("CONST_INIT",imm)
    if op==0xC6:
        return ("BYTE_CONST",d[p+3] if p+4<=fe else None)
    if op==0x89:
        src=REGS[(mr>>3)&7]
        st,val,where=backtrace_reg_source(d,fs,p,src,64)
        if st=="ARG": return ("ARG_COPY",val)
        if st=="ZERO": return ("ZERO_INIT",0)
        if src=="eax":
            # nearest preceding CALL within 16 bytes -> call return
            for q in range(max(fs,p-20),p):
                if d[q]==0xE8:
                    return ("CALL_RETURN","eax")
        return ("REG_COPY",src)
    return ("OTHER",None)

def has_vtable_store(d,fs,fe,ib,secs):
    # constructor-like signal: immediate executable/data-looking pointer stored at [this+0] near first 0x100 bytes.
    lim=min(fe,fs+0x120)
    for p in range(fs,lim-9):
        if d[p]==0xC7:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7
            if mod==0 and rm!=5:
                imm=u32(d,p+2)
                # C7 /0 [reg], imm32 is 6 bytes, modrm ext must 0
                if ((mr>>3)&7)==0 and 0x00400000<=imm<=0x02000000:
                    return True,p,imm
    return False,None,None

def shared_ptr_signature(d,p,fe):
    # Look after +358 write for refcount idioms: test reg/eax, add +4, lock xadd/inc.
    z=min(fe,p+48)
    chunk=d[p:z]
    score=0;why=[]
    if b"\x85\xC0" in chunk or b"\x85\xC9" in chunk or b"\x85\xD2" in chunk:
        score+=10;why.append("NULL_TEST")
    if b"\x83\xC0\x04" in chunk or b"\x83\xC1\x04" in chunk or b"\x83\xC2\x04" in chunk:
        score+=15;why.append("ADD4")
    if b"\xF0\x0F\xC1" in chunk:
        score+=25;why.append("LOCK_XADD")
    if b"\xF0\xFF" in chunk:
        score+=20;why.append("LOCK_INCDEC")
    return score,why

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args();root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

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

    print("[2/6] Indexando funcoes e callers...",flush=True)
    pro=build_prologues(d,secs,ib)
    callers=build_call_index(d,secs,ib,pro)
    print(f"      prologos={len(pro)} destinosCall={len(callers)}",flush=True)

    print("[3/6] Localizando writers de +0x354/+0x358...",flush=True)
    byfn=scan_candidate_functions(d,secs,ib,pro)
    candidates=[]
    for fn,rows in byfn.items():
        trows=[r for r in rows if r[1] in TARGETS and classify(r[2],r[3]) in ("WRITE","READ_WRITE","ADDRESS")]
        if not trows:continue
        fs,fe=fn_bounds(fn,pro,ib,secs,d)
        if fs is None:continue
        writes=[]
        for p,disp,op,mr,base in trows:
            kind=classify(op,mr)
            semantic=None
            if kind=="WRITE":
                semantic=classify_write(d,fs,fe,p,disp,op,mr)
            elif kind=="ADDRESS":
                semantic=("ADDRESS",None)
            else:
                semantic=(kind,None)
            sp_score,sp_why=shared_ptr_signature(d,p,fe) if disp==0x358 else (0,[])
            writes.append((p,disp,kind,base,semantic,sp_score,sp_why))
        vtbl=has_vtable_store(d,fs,fe,ib,secs)
        candidates.append((fn,fs,fe,writes,vtbl,callers.get(fn,())))

    print(f"      candidatos={len(candidates)}",flush=True)

    print("[4/6] Classificando semantica...",flush=True)
    ranked=[]
    for fn,fs,fe,writes,vtbl,calls in candidates:
        sems=[w[4][0] for w in writes]
        score=0;why=[]
        if "ARG_COPY" in sems:
            score+=100;why.append("ARG_COPY")
        if "CALL_RETURN" in sems:
            score+=90;why.append("CALL_RETURN")
        if "REG_COPY" in sems:
            score+=45;why.append("REG_COPY")
        if "ADDRESS" in sems:
            score+=35;why.append("ADDRESS")
        if all(s=="ZERO_INIT" for s in sems if s not in ("ADDRESS",)):
            score-=100;why.append("ZERO_ONLY")
        if any(s=="CONST_INIT" for s in sems):
            score-=50;why.append("CONST_INIT")
        sp=sum(w[5] for w in writes)
        if sp:
            score+=sp;why.append("SHAREDPTR_PATTERN")
        if vtbl[0]:
            score-=35;why.append("CTOR_LIKE_VTABLE")
        # Pair completeness
        fields={w[1] for w in writes}
        if 0x354 in fields and 0x358 in fields:
            score+=20;why.append("PAIR")
        ranked.append((score,fn,fs,fe,writes,vtbl,calls,why))
    ranked.sort(key=lambda x:(-x[0],x[1]))

    strong=[x for x in ranked if x[0]>=80 and "ZERO_ONLY" not in x[7]]
    print(f"      strong={len(strong)}",flush=True)
    if strong:
        x=strong[0]
        print(f"      TOP=0x{x[1]:08X} score={x[0]} why={','.join(x[7])}",flush=True)

    print("[5/6] Gravando relatorio...",flush=True)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE84_OWNER_PAIR_SEMANTICS"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE84-OWNER-PAIR-SEMANTICS.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*124)
    w(" ReXtreme Phase 84 - semantic classification of +0x354/+0x358 writers")
    w("="*124)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("Goal: distinguish zero/constant constructors from real shared_ptr assignments.")
    w("ARG_COPY and CALL_RETURN candidates are prioritized; constructor-like vtable stores are penalized.")
    w("")

    w("===== RANKED WRITER SEMANTICS =====")
    w(f"Count={len(ranked)}")
    for rank,x in enumerate(ranked[:120],1):
        score,fn,fs,fe,writes,vtbl,calls,why=x
        w(f"#{rank} score={score} fn=0x{fn:08X} file=0x{fs:08X} end=0x{fe:08X} why={','.join(why) if why else '-'}")
        if vtbl[0]:
            w(f"  ctorLikeVtable file=0x{vtbl[1]:08X} imm=0x{vtbl[2]:08X}")
        for p,disp,kind,base,semantic,sp_score,sp_why in writes:
            sval=semantic[1]
            if isinstance(sval,int):sval=f"0x{sval:X}"
            w(f"  field=+0x{disp:X} kind={kind} semantic={semantic[0]} source={sval} file=0x{p:08X} base={base} spScore={sp_score} spWhy={','.join(sp_why) if sp_why else '-'}")
            lines.extend(dump(d,p-72,p+144))
        w(f"  directCallers={len(calls)}")
        for cp,cfn in calls[:50]:
            w(f"   callerFile=0x{cp:08X} callerFn={('0x%08X'%cfn) if cfn else 'N/A'}")
        w("")
        if rank<=20:
            lines.extend(dump(d,fs,min(fe,fs+0x800)))
            w("")

    w("===== STRONG SHARED_PTR ASSIGNMENT CANDIDATES =====")
    w(f"Count={len(strong)}")
    for score,fn,fs,fe,writes,vtbl,calls,why in strong[:100]:
        w(f"score={score} fn=0x{fn:08X} why={','.join(why)} callers={len(calls)}")
        for p,disp,kind,base,semantic,sp_score,sp_why in writes:
            sval=semantic[1]
            if isinstance(sval,int):sval=f"0x{sval:X}"
            w(f"  +0x{disp:X} {semantic[0]} source={sval} file=0x{p:08X} sp={','.join(sp_why) if sp_why else '-'}")
    w("")

    obj={
      "phase":"84-owner-pair-semantics",
      "ams_sha256":cursha,
      "candidate_count":len(ranked),
      "strong_candidates":[
        {
          "score":x[0],
          "function_va":f"0x{x[1]:08X}",
          "why":x[7],
          "direct_callers":[
             {"call_file":f"0x{cp:08X}","caller_fn":f"0x{cfn:08X}" if cfn else None}
             for cp,cfn in x[6][:50]
          ],
          "writes":[
            {
              "field":f"0x{w0[1]:X}",
              "file":f"0x{w0[0]:08X}",
              "kind":w0[2],
              "semantic":w0[4][0],
              "source":(f"0x{w0[4][1]:X}" if isinstance(w0[4][1],int) else w0[4][1]),
              "shared_ptr_markers":w0[6]
            } for w0 in x[4]
          ]
        } for x in strong[:80]
      ],
      "no_gameplay_bytes_changed":True,
      "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    summary.write_text(json.dumps(obj,indent=2),encoding="utf-8")

    print("[6/6] PHASE 84 OK",flush=True)
    print("Report:",report,flush=True)
    print("Summary:",summary,flush=True)

if __name__=="__main__":
    main()
