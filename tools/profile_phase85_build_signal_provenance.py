#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import deque, defaultdict
from pathlib import Path

STABLE_SHA = "7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

GUARDS = [
    ("Phase53", 0x00574FA7, bytes.fromhex("6A 01 90")),
    ("Phase54", 0x0059F3F2, bytes.fromhex("B8 02 00 00 00 90")),
    ("Phase55", 0x00573C45, bytes.fromhex("90 90 90 90 90 90")),
    ("Phase63Reverted", 0x00573CF4, bytes.fromhex("74 0B")),
    ("Phase65Reverted", 0x0056E9CE, bytes.fromhex("0F 94 45 E3")),
    ("GlobalIsOnlineFALSE", 0x00BACDD0, bytes.fromhex("31 C0 C3 90 90 90 90")),
    ("Phase36Popup", 0x009168B0, bytes.fromhex("31 C0 C2 18 00")),
]

# Proven anchors.
GS_VTABLE = 0x0186A9CC
GBBW_VTABLE = 0x01831854
GS_GBBW_FIELD = 0x35C
GS_GBBW_CTRL = 0x360
GBBW_CTOR = 0x0096EB10
GBBW_REGISTER = 0x00972B90
GBBW_BUILD_CB = 0x00973C90
GBBW_DTOR = 0x0096EDF0
GS_BUILD_HANDLER = 0x00A87960
CRAFT_CALLER = 0x0099FF50
CRAFT_CAR = 0x009A4BA0

# GBBW signal/shared_ptr pairs. Build is +44/+48.
PAIR_BASES = (0x34, 0x3C, 0x44, 0x4C, 0x54, 0x5C, 0x64, 0x6C, 0x74)
PAIR_FIELDS = set()
for _x in PAIR_BASES:
    PAIR_FIELDS.add(_x)
    PAIR_FIELDS.add(_x + 4)

BUILD_PAIR = (0x44, 0x48)

REGS = ("eax","ecx","edx","ebx","esp","ebp","esi","edi")
CALLEE_SAVED = {"ebx","esi","edi","ebp"}
CALLER_SAVED = {"eax","ecx","edx"}

def u16(b,o): return struct.unpack_from("<H", b, o)[0]
def u32(b,o): return struct.unpack_from("<I", b, o)[0]
def i32(b,o): return struct.unpack_from("<i", b, o)[0]
def i8v(x): return x - 256 if x >= 128 else x
def sha256(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe = u32(d,0x3C)
    if d[pe:pe+4] != b"PE\0\0":
        raise RuntimeError("invalid PE")
    machine = u16(d,pe+4)
    nsec = u16(d,pe+6)
    optsz = u16(d,pe+20)
    opt = pe+24
    if machine != 0x14C or u16(d,opt) != 0x10B:
        raise RuntimeError("expected x86 PE32")
    ib = u32(d,opt+28)
    so = opt + optsz
    secs=[]
    for i in range(nsec):
        o=so+i*40
        secs.append({
            "name": d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
            "raw":u32(d,o+20),"ch":u32(d,o+36)
        })
    return ib,secs

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"] <= off < s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"] <= rva < s["va"]+max(s["vs"],s["rs"]):
            return s["raw"]+(rva-s["va"])
    return None

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None: return False
    for s in secs:
        if s["raw"] <= f < s["raw"]+s["rs"]:
            return bool(s["ch"] & 0x20000000)
    return False

def next_prologue(d,start,secs,limit=0x18000):
    sec_end=len(d)
    for s in secs:
        if s["raw"] <= start < s["raw"]+s["rs"]:
            sec_end=min(len(d),s["raw"]+s["rs"])
            break
    z=min(sec_end,start+limit)
    p=d.find(b"\x55\x8B\xEC", start+3, z)
    return p if p >= 0 else z

def function_bounds(d,va,ib,secs):
    fs=v2f(va,ib,secs)
    if fs is None:return None,None
    return fs,next_prologue(d,fs,secs)

def dump(d,a,z):
    out=[]
    for p in range(max(0,a),min(len(d),z),16):
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in d[p:min(p+16,z)]))
    return out

def read_vtable(d,va,ib,secs,max_slots=256):
    f=v2f(va,ib,secs)
    out=[]
    if f is None:return out
    for i in range(max_slots):
        if f+i*4+4 > len(d):break
        t=u32(d,f+i*4)
        if not is_exec_va(t,ib,secs):
            break
        out.append((i,i*4,t))
    return out

def direct_target(d,p,ib,secs):
    if p+5 > len(d) or d[p] != 0xE8:return None
    src=f2v(p,ib,secs)
    if src is None:return None
    dst=(src+5+i32(d,p+1)) & 0xFFFFFFFF
    return dst if is_exec_va(dst,ib,secs) else None

def direct_jmp_target(d,p,ib,secs):
    src=f2v(p,ib,secs)
    if src is None:return None
    if d[p]==0xE9 and p+5<=len(d):
        dst=(src+5+i32(d,p+1)) & 0xFFFFFFFF
        return dst if is_exec_va(dst,ib,secs) else None
    if d[p]==0xEB and p+2<=len(d):
        dst=(src+2+i8v(d[p+1])) & 0xFFFFFFFF
        return dst if is_exec_va(dst,ib,secs) else None
    return None

# Memory operand decoder for ModRM, including common SIB forms.
# Returns (base_reg, index_reg, scale, disp, total_bytes_from_opcode)
def decode_mem(d,p,fe):
    if p+2>fe:return None
    mr=d[p+1]
    mod=(mr>>6)&3
    rm=mr&7
    if mod==3:return None
    q=p+2
    base=None; index=None; scale=1
    if rm==4:
        if q>=fe:return None
        sib=d[q];q+=1
        scale=1 << ((sib>>6)&3)
        idx=(sib>>3)&7
        b=sib&7
        if idx != 4:index=REGS[idx]
        if mod==0 and b==5:
            base=None
        else:
            base=REGS[b]
    elif mod==0 and rm==5:
        base=None
    else:
        base=REGS[rm]

    disp=0
    if mod==0:
        if (rm==5) or (rm==4 and base is None):
            if q+4>fe:return None
            disp=i32(d,q);q+=4
    elif mod==1:
        if q>=fe:return None
        disp=i8v(d[q]);q+=1
    elif mod==2:
        if q+4>fe:return None
        disp=i32(d,q);q+=4
    return base,index,scale,disp,q-p

def classify_mem(op,mr):
    ext=(mr>>3)&7
    if op==0x8B:return "READ"
    if op==0x89:return "WRITE"
    if op==0x8D:return "ADDRESS"
    if op in (0xC6,0xC7):return "WRITE"
    if op==0xFF and ext==2:return "CALL_MEM"
    if op==0xFF and ext in (0,1):return "READ_WRITE"
    if op in (0x39,0x3B,0x80,0x81,0x83,0xF6,0xF7):return "READ"
    return "MEM"

def seed_arg_reg(d,fs,fe,argn):
    off=8+4*(argn-1)
    lim=min(fe,fs+0x180)
    p=fs
    while p+3<=lim:
        if d[p]==0x8B:
            mr=d[p+1]; mod=(mr>>6)&3; rm=mr&7; dst=(mr>>3)&7
            if rm==5:
                if mod==1 and p+3<=lim and i8v(d[p+2])==off:
                    return REGS[dst]
                if mod==2 and p+6<=lim and i32(d,p+2)==off:
                    return REGS[dst]
        p+=1
    return None

def recent_push_args(pushes,callp,max_args=8):
    # Keep only pushes reasonably near the call; last push is arg1.
    vals=[x for x in pushes if callp-x[0] <= 96]
    vals=vals[-max_args:]
    out=[]
    for i,(pp,origin,reg) in enumerate(reversed(vals),1):
        out.append((i,origin,reg,pp))
    return out

def find_gbbw_roots_in_gs(d,method_va,slot,ib,secs):
    fs,fe=function_bounds(d,method_va,ib,secs)
    if fs is None:return []
    # Symbolic GS-this offsets. ECX starts as GS+0. Callee-saved copies survive calls.
    regs={"ecx":0}
    locals_={}
    roots=[]
    p=fs
    while p<fe:
        op=d[p]

        # mov r,r or mov r,[mem]
        if op==0x8B and p+2<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=REGS[(mr>>3)&7]
            if mod==3:
                src=REGS[rm]
                if src in regs:regs[dst]=regs[src]
                else:regs.pop(dst,None)
                p+=2;continue
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                # stack local reload
                if base=="ebp" and index is None and disp<0 and disp in locals_:
                    regs[dst]=locals_[disp]
                elif base in regs and index is None:
                    eff=regs[base]+disp
                    if eff==GS_GBBW_FIELD:
                        roots.append({
                            "slot":slot,"method_va":method_va,"file":p,
                            "start_file":p+ln,"reg":dst,
                            "path":[f"GSslot0x{slot:X}:0x{method_va:08X}",f"load GS+0x{GS_GBBW_FIELD:X} @0x{p:08X}"]
                        })
                        regs.pop(dst,None) # it is now GBBW, not GS-this
                    else:
                        regs.pop(dst,None)
                else:
                    regs.pop(dst,None)
                p+=ln;continue

        # lea alias of GS this
        if op==0x8D and p+2<=fe:
            mr=d[p+1];dst=REGS[(mr>>3)&7]
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                if base in regs and index is None:
                    regs[dst]=regs[base]+disp
                else:regs.pop(dst,None)
                p+=ln;continue

        # mov [ebp-local], tainted reg
        if op==0x89 and p+2<=fe:
            mr=d[p+1];src=REGS[(mr>>3)&7]
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                if base=="ebp" and index is None and disp<0:
                    if src in regs:locals_[disp]=regs[src]
                    else:locals_.pop(disp,None)
                p+=ln;continue

        # direct calls clobber volatile aliases only
        if op==0xE8:
            for r in CALLER_SAVED:regs.pop(r,None)
            p+=5;continue

        if op in (0xC3,0xCB):break
        if op in (0xC2,0xCA):break
        p+=1
    return roots

def scan_state(d,va,mode,origin,start_file,seed_reg,gbbw_vtable_entries,ib,secs):
    fs,fe=function_bounds(d,va,ib,secs)
    if fs is None:return None
    p=start_file if start_file is not None else fs

    regs={}
    locals_={}
    vtbl={} # register -> object origin (only origin 0 can resolve as GBBW)
    pushes=[]

    if seed_reg is not None:
        regs[seed_reg]=origin
    elif mode=="ecx":
        regs["ecx"]=origin
    elif mode.startswith("arg"):
        try:n=int(mode[3:])
        except:return None
        r=seed_arg_reg(d,fs,fe,n)
        if r is not None:regs[r]=origin
        else:
            # Keep a synthetic stack seed so a direct mov later can pick it up.
            locals_[8+4*(n-1)]=origin

    hits=[];calls=[];virtuals=[];aliases=[];pairwrites=[]
    steps=0
    while p<fe:
        steps+=1
        if steps>250000:break
        op=d[p]

        if op in (0xC3,0xCB):break
        if op in (0xC2,0xCA):break

        # MOV r,r / MOV r,[mem]
        if op==0x8B and p+2<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;dst=REGS[(mr>>3)&7]
            if mod==3:
                src=REGS[rm]
                if src in regs:
                    regs[dst]=regs[src];aliases.append((p,dst,src,regs[dst]))
                else:regs.pop(dst,None)
                if src in vtbl:vtbl[dst]=vtbl[src]
                else:vtbl.pop(dst,None)
                p+=2;continue
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                # EBP arg/local reload
                if base=="ebp" and index is None:
                    if disp in locals_:
                        regs[dst]=locals_[disp]
                    else:
                        regs.pop(dst,None)
                elif base in regs and index is None:
                    eff=regs[base]+disp
                    if eff in PAIR_FIELDS:
                        hits.append((p,eff,"READ",base,disp))
                    # mov tmp,[object+0] commonly loads vtable
                    if disp==0:
                        vtbl[dst]=regs[base]
                    else:
                        vtbl.pop(dst,None)
                    # loaded value is not an alias of object unless special pair pointer.
                    regs.pop(dst,None)
                else:
                    regs.pop(dst,None);vtbl.pop(dst,None)
                p+=ln;continue

        # LEA r,[tainted+disp]
        if op==0x8D and p+2<=fe:
            mr=d[p+1];dst=REGS[(mr>>3)&7]
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                if base in regs and index is None:
                    regs[dst]=regs[base]+disp
                    aliases.append((p,dst,base,regs[dst]))
                    if regs[dst] in PAIR_FIELDS:
                        hits.append((p,regs[dst],"ADDRESS",base,disp))
                else:
                    regs.pop(dst,None)
                vtbl.pop(dst,None)
                p+=ln;continue

        # MOV [mem],reg / other memory operations
        if op in (0x89,0x39,0x3B,0x80,0x81,0x83,0xC6,0xC7,0xF6,0xF7,0xFF) and p+2<=fe:
            mr=d[p+1]
            mem=decode_mem(d,p,fe)
            if mem:
                base,index,scale,disp,ln=mem
                kind=classify_mem(op,mr)
                if base=="ebp" and index is None and disp<0 and op==0x89:
                    src=REGS[(mr>>3)&7]
                    if src in regs:locals_[disp]=regs[src]
                    else:locals_.pop(disp,None)
                elif base in regs and index is None:
                    eff=regs[base]+disp
                    if eff in PAIR_FIELDS:
                        hits.append((p,eff,kind,base,disp))
                        if kind in ("WRITE","READ_WRITE"):
                            pairwrites.append((p,eff,kind))
                    # call [object+slot] direct form
                    if op==0xFF and ((mr>>3)&7)==2:
                        virtuals.append((p,regs[base],disp,"direct_object",None))
                elif base in vtbl and index is None and op==0xFF and ((mr>>3)&7)==2:
                    objorigin=vtbl[base]
                    target=None
                    if objorigin==0 and disp % 4 == 0 and disp >= 0:
                        idx=disp//4
                        if 0<=idx<len(gbbw_vtable_entries):
                            target=gbbw_vtable_entries[idx][2]
                    virtuals.append((p,objorigin,disp,"via_vtable",target))
                p+=ln;continue

        # ADD/SUB reg,imm for pointer arithmetic.
        if op in (0x83,0x81) and p+3<=fe:
            mr=d[p+1];mod=(mr>>6)&3;rm=mr&7;ext=(mr>>3)&7
            r=REGS[rm]
            if mod==3 and r in regs and ext in (0,5):
                if op==0x83:
                    imm=i8v(d[p+2]);ln=3
                else:
                    if p+6>fe:break
                    imm=i32(d,p+2);ln=6
                if ext==5:imm=-imm
                regs[r]+=imm
                aliases.append((p,r,r,regs[r]))
                p+=ln;continue

        # PUSH tainted register.
        if 0x50<=op<=0x57:
            r=REGS[op-0x50]
            if r in regs:
                pushes.append((p,regs[r],r))
                if len(pushes)>16:pushes=pushes[-16:]
            p+=1;continue

        # PUSH [mem] where mem is a pair field: loaded value is not alias; don't propagate.
        if op==0xFF and p+2<=fe:
            mr=d[p+1]
            if ((mr>>3)&7)==6:
                mem=decode_mem(d,p,fe)
                if mem:
                    _,_,_,_,ln=mem;p+=ln;continue

        # Direct CALL.
        if op==0xE8:
            dst=direct_target(d,p,ib,secs)
            if dst is not None:
                if "ecx" in regs:
                    calls.append((p,dst,"ecx",regs["ecx"],"ecx",p))
                for argn,aorigin,areg,pp in recent_push_args(pushes,p,8):
                    calls.append((p,dst,f"arg{argn}",aorigin,areg,pp))
            pushes=[]
            for r in CALLER_SAVED:
                regs.pop(r,None);vtbl.pop(r,None)
            p+=5;continue

        # Direct JMP tail-call propagation.
        if op in (0xE9,0xEB):
            dst=direct_jmp_target(d,p,ib,secs)
            if dst is not None:
                if "ecx" in regs:
                    calls.append((p,dst,"ecx",regs["ecx"],"ecx",p))
                for argn,aorigin,areg,pp in recent_push_args(pushes,p,8):
                    calls.append((p,dst,f"arg{argn}",aorigin,areg,pp))
            # unconditional jump ends current linear path.
            break

        # POP kills destination register alias.
        if 0x58<=op<=0x5F:
            r=REGS[op-0x58]
            regs.pop(r,None);vtbl.pop(r,None)
            p+=1;continue

        # Branch: keep analysis linear but clear push window to avoid stale args.
        if 0x70<=op<=0x7F:
            pushes=[]
        p+=1

    # Pair assignment signature in this state: both build pair members touched strongly.
    build_strong={eff for _,eff,k,_,_ in hits if eff in BUILD_PAIR and k in ("WRITE","READ_WRITE","ADDRESS")}
    return {
        "fs":fs,"fe":fe,"hits":hits,"calls":calls,"virtuals":virtuals,
        "aliases":aliases,"pairwrites":pairwrites,
        "build_pair_complete":set(BUILD_PAIR).issubset(build_strong)
    }

def global_pair_writer_scan(d,ib,secs):
    # Diagnostic-only global candidates: same base register writes/address-takes both +44 and +48
    # within a small window. These remain UNTYPED until intersecting provenance states.
    rows=[]
    for s in secs:
        if not (s["ch"] & 0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"])
        bybase=defaultdict(list)
        p=a
        while p+3<=b:
            op=d[p]
            if op not in (0x89,0x8D,0xC6,0xC7,0xFF):
                p+=1;continue
            mr=d[p+1]
            mem=decode_mem(d,p,b)
            if not mem:
                p+=1;continue
            base,index,scale,disp,ln=mem
            if base is not None and index is None and disp in BUILD_PAIR:
                kind=classify_mem(op,mr)
                if kind in ("WRITE","READ_WRITE","ADDRESS"):
                    bybase[base].append((p,disp,kind))
            p+=max(1,ln)
        for base,items in bybase.items():
            items.sort()
            for i,x in enumerate(items):
                if x[1]!=0x44:continue
                for y in items[i+1:]:
                    if y[0]-x[0]>0x120:break
                    if y[1]==0x48:
                        va=f2v(x[0],ib,secs)
                        rows.append((x[0],va,base,x,y))
                        break
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ap.add_argument("--max-states",type=int,default=200000)
    ap.add_argument("--max-depth",type=int,default=32)
    ns=ap.parse_args()

    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():
        raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    print("[1/8] Verificando SHA/guards...",flush=True)
    for name,off,expected in GUARDS:
        if d[off:off+len(expected)] != expected:
            raise SystemExit(f"{name} guard failed at 0x{off:08X}")
    cursha=sha256(d)
    if cursha!=STABLE_SHA:
        raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")
    ib,secs=parse_pe(d)

    print("[2/8] Lendo vtables tipadas...",flush=True)
    gs_methods=read_vtable(d,GS_VTABLE,ib,secs,256)
    gbbw_methods=read_vtable(d,GBBW_VTABLE,ib,secs,64)
    print(f"      GS_Garage methods={len(gs_methods)} GBBW methods={len(gbbw_methods)}",flush=True)

    print("[3/8] Encontrando cargas REAIS GS_Garage+0x35C -> GBBW...",flush=True)
    roots=[]
    for idx,slot,va in gs_methods:
        roots.extend(find_gbbw_roots_in_gs(d,va,slot,ib,secs))
    print(f"      typed GBBW roots={len(roots)}",flush=True)
    for r in roots:
        print(f"      GS slot 0x{r['slot']:X} method 0x{r['method_va']:08X} file 0x{r['file']:08X} -> {r['reg']}",flush=True)

    print("[4/8] Proveniencia interprocedural do GBBW (ECX + args + spills + LEA + virtuals)...",flush=True)
    q=deque()
    # Concrete roots loaded from GS+35C, starting mid-function.
    for r in roots:
        q.append({
            "root_slot":r["slot"],"va":r["method_va"],"mode":"reg",
            "origin":0,"depth":0,"start_file":r["start_file"],"seed_reg":r["reg"],
            "path":r["path"]
        })

    # GBBW's own typed methods/ctor as additional roots; marked separately.
    q.append({"root_slot":"GBBW_CTOR","va":GBBW_CTOR,"mode":"ecx","origin":0,"depth":0,
              "start_file":None,"seed_reg":None,"path":[f"GBBW_CTOR:0x{GBBW_CTOR:08X}"]})
    for idx,slot,va in gbbw_methods:
        q.append({"root_slot":f"GBBW_VSLOT_0x{slot:X}","va":va,"mode":"ecx","origin":0,"depth":0,
                  "start_file":None,"seed_reg":None,"path":[f"GBBWslot0x{slot:X}:0x{va:08X}"]})
    q.append({"root_slot":"GBBW_BUILD_CB","va":GBBW_BUILD_CB,"mode":"ecx","origin":0,"depth":0,
              "start_file":None,"seed_reg":None,"path":[f"BUILD_CB:0x{GBBW_BUILD_CB:08X}"]})

    seen=set()
    state_rows=[]
    hit_rows=[]
    edge_rows=[]
    virtual_rows=[]
    strong=[]
    maxdepth=0

    while q and len(seen)<ns.max_states:
        st=q.popleft()
        va=st["va"];mode=st["mode"];origin=st["origin"];depth=st["depth"]
        # start_file only matters for concrete mid-function roots.
        key=(va,mode,origin,st["start_file"],st["seed_reg"])
        if key in seen or depth>ns.max_depth:continue
        seen.add(key);maxdepth=max(maxdepth,depth)

        a=scan_state(d,va,mode,origin,st["start_file"],st["seed_reg"],gbbw_methods,ib,secs)
        if not a:continue
        state_rows.append((st,a))

        for p,eff,kind,base,disp in a["hits"]:
            rec={
                "root_slot":st["root_slot"],"function_va":va,"mode":mode,
                "origin":origin,"depth":depth,"file":p,"field":eff,
                "kind":kind,"base":base,"disp":disp,"path":st["path"]
            }
            hit_rows.append(rec)
            if eff in BUILD_PAIR and kind in ("WRITE","READ_WRITE","ADDRESS"):
                strong.append(rec)

        # Direct call propagation.
        for cp,dst,nmode,noff,via,prep in a["calls"]:
            edge_rows.append((st,cp,dst,nmode,noff,via,prep,"direct"))
            if depth<ns.max_depth and -0x200<=noff<=0x400:
                q.append({
                    "root_slot":st["root_slot"],"va":dst,"mode":nmode,
                    "origin":noff,"depth":depth+1,"start_file":None,"seed_reg":None,
                    "path":st["path"]+[f"0x{dst:08X}+0x{noff:X}({nmode})"]
                })

        # Resolved virtual call on actual GBBW.
        for vp,objorigin,vslot,kind,target in a["virtuals"]:
            virtual_rows.append((st,vp,objorigin,vslot,kind,target))
            if target is not None and depth<ns.max_depth:
                edge_rows.append((st,vp,target,"ecx",objorigin,"virtual",vp,"virtual"))
                q.append({
                    "root_slot":st["root_slot"],"va":target,"mode":"ecx",
                    "origin":objorigin,"depth":depth+1,"start_file":None,"seed_reg":None,
                    "path":st["path"]+[f"virtual+0x{vslot:X}->0x{target:08X}"]
                })

        if len(seen)%5000==0:
            print(f"      states={len(seen)} queue={len(q)} hits={len(hit_rows)} buildStrong={len(strong)} depth={maxdepth}",flush=True)

    exhausted = not q
    print(f"      done states={len(seen)} exhausted={exhausted} maxDepth={maxdepth} edges={len(edge_rows)}",flush=True)

    print("[5/8] Escaneando assinaturas globais +0x44/+0x48 (somente comparacao)...",flush=True)
    global_pairs=global_pair_writer_scan(d,ib,secs)
    typed_functions={x[0]["va"] for x in state_rows}
    typed_global=[x for x in global_pairs if x[1] in typed_functions]
    print(f"      global pair candidates={len(global_pairs)} intersect typed={len(typed_global)}",flush=True)

    print("[6/8] Ranqueando proveniencia BUILD +0x44/+0x48...",flush=True)
    # Deduplicate exact strong hits.
    uniq={}
    for x in strong:
        uniq[(x["function_va"],x["file"],x["field"],x["kind"],x["origin"],x["mode"])]=x
    strong=list(uniq.values())
    score={"WRITE":100,"READ_WRITE":95,"ADDRESS":85,"READ":20}
    strong.sort(key=lambda x:(-score.get(x["kind"],0),x["depth"],x["file"]))
    complete_states=[]
    for st,a in state_rows:
        if a["build_pair_complete"]:
            complete_states.append((st,a))
    print(f"      strong build hits={len(strong)} complete pair states={len(complete_states)}",flush=True)
    if strong:
        x=strong[0]
        print(f"      TOP {x['kind']} fn=0x{x['function_va']:08X} file=0x{x['file']:08X} field=+0x{x['field']:X} depth={x['depth']}",flush=True)

    print("[7/8] Gravando relatorio...",flush=True)
    outdir=root/"_PACKAGE_PHASE5"/"_PHASE85_BUILD_SIGNAL_PROVENANCE"
    outdir.mkdir(parents=True,exist_ok=True)
    report=outdir/"LATEST-PHASE85-BUILD-SIGNAL-PROVENANCE.txt"
    summary=outdir/"SUMMARY.json"
    lines=[];w=lines.append

    w("="*126)
    w(" ReXtreme Phase 85 - typed provenance of GarageBottomBarWidget build-signal shared_ptr +0x44/+0x48")
    w("="*126)
    w(f"AMS_SHA256={cursha}")
    w("Phase53=ACTIVE Phase54=ACTIVE Phase55=ACTIVE Phase63=REVERTED Phase65=REVERTED")
    w("GlobalIsOnline=FALSE Phase36PopupBypass=ACTIVE")
    w("NO GAMEPLAY BYTES CHANGED")
    w("")
    w("MODEL:")
    w("  GBBW+0x44 = build signal shared_ptr.object")
    w("  GBBW+0x48 = build signal shared_ptr.control/refcount")
    w("  Roots come from actual GS_Garage+0x35C loads plus typed GBBW methods.")
    w("  Propagation includes ECX, up to 8 stack args, EBP spills/reloads, LEA-derived pointers, tail calls, and resolved GBBW virtual calls.")
    w("")

    w("===== ROOTS: GS_GARAGE+0x35C -> GBBW =====")
    w(f"Count={len(roots)}")
    for r in roots:
        w(f"GSslot=0x{r['slot']:X} method=0x{r['method_va']:08X} loadFile=0x{r['file']:08X} reg={r['reg']}")
    w("")

    w("===== SEARCH COVERAGE =====")
    w(f"states={len(seen)}")
    w(f"queue_exhausted={exhausted}")
    w(f"max_depth_reached={maxdepth}")
    w(f"configured_max_depth={ns.max_depth}")
    w(f"configured_max_states={ns.max_states}")
    w(f"edges={len(edge_rows)}")
    w(f"virtual_edges={len(virtual_rows)}")
    w(f"all_pair_hits={len(hit_rows)}")
    w("")

    w("===== ALL TYPED SIGNAL-PAIR HITS (+34..+78) =====")
    w(f"Count={len(hit_rows)}")
    for x in sorted(hit_rows,key=lambda y:(y["field"],-score.get(y["kind"],0),y["depth"],y["file"])):
        w(f"field=+0x{x['field']:X} kind={x['kind']} root={x['root_slot']} depth={x['depth']} fn=0x{x['function_va']:08X} mode={x['mode']} origin=0x{x['origin']:X} file=0x{x['file']:08X}")
        if x["field"] in BUILD_PAIR or x["kind"] in ("WRITE","READ_WRITE","ADDRESS"):
            w(" path="+" -> ".join(x["path"]))
            lines.extend(dump(d,x["file"]-80,x["file"]+160))
    w("")

    w("===== STRONG BUILD +0x44/+0x48 HITS =====")
    w(f"Count={len(strong)}")
    for x in strong:
        w(f"{x['kind']} field=+0x{x['field']:X} root={x['root_slot']} depth={x['depth']} fn=0x{x['function_va']:08X} file=0x{x['file']:08X} mode={x['mode']} origin=0x{x['origin']:X}")
        w(" path="+" -> ".join(x["path"]))
        lines.extend(dump(d,x["file"]-112,x["file"]+208))
    w("")

    w("===== STATES TOUCHING BOTH BUILD PAIR MEMBERS STRONGLY =====")
    w(f"Count={len(complete_states)}")
    for st,a in complete_states:
        w(f"root={st['root_slot']} depth={st['depth']} fn=0x{st['va']:08X} mode={st['mode']} origin=0x{st['origin']:X}")
        w(" path="+" -> ".join(st["path"]))
        lines.extend(dump(d,a["fs"],min(a["fe"],a["fs"]+0x1200)))
    w("")

    w("===== GLOBAL +0x44/+0x48 PAIR-WRITER SIGNATURES =====")
    w(f"Count={len(global_pairs)}")
    w("NOTE: these are untyped unless marked TYPED_INTERSECTION.")
    for off,va,base,x,y in global_pairs[:1000]:
        tag=" TYPED_INTERSECTION" if va in typed_functions else ""
        w(f"candidateVA={('0x%08X'%va) if va else 'N/A'} file=0x{off:08X} base={base} +44={x[2]}@0x{x[0]:08X} +48={y[2]}@0x{y[0]:08X}{tag}")
        if tag:
            lines.extend(dump(d,off-96,y[0]+176))
    w("")

    w("===== INTERPROCEDURAL CARRY EDGES =====")
    w(f"Count={len(edge_rows)}")
    for st,cp,dst,nmode,noff,via,prep,etype in edge_rows[:12000]:
        w(f"{etype} root={st['root_slot']} depth={st['depth']} src=0x{st['va']:08X} callFile=0x{cp:08X} -> dst=0x{dst:08X} mode={nmode} origin=0x{noff:X} via={via}")
    w("")

    summary={
        "phase":"85-build-signal-provenance",
        "ams_sha256":cursha,
        "model":{
            "build_signal_object_field":"0x44",
            "build_signal_control_field":"0x48",
            "gs_gbbw_field":"0x35C"
        },
        "gs_gbbw_roots":len(roots),
        "states":len(seen),
        "queue_exhausted":exhausted,
        "max_depth_reached":maxdepth,
        "configured_max_depth":ns.max_depth,
        "configured_max_states":ns.max_states,
        "edges":len(edge_rows),
        "virtual_edges":len(virtual_rows),
        "typed_pair_hits":len(hit_rows),
        "strong_build_hits":[
            {
                "kind":x["kind"],"field":f"0x{x['field']:X}",
                "root":str(x["root_slot"]),"depth":x["depth"],
                "function_va":f"0x{x['function_va']:08X}",
                "file":f"0x{x['file']:08X}","mode":x["mode"],
                "origin":f"0x{x['origin']:X}","path":x["path"]
            } for x in strong[:250]
        ],
        "complete_build_pair_states":[
            {
                "root":str(st["root_slot"]),"depth":st["depth"],
                "function_va":f"0x{st['va']:08X}","mode":st["mode"],
                "origin":f"0x{st['origin']:X}","path":st["path"]
            } for st,a in complete_states[:100]
        ],
        "global_pair_candidates":len(global_pairs),
        "typed_global_pair_candidates":len(typed_global),
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    report.write_text("\n".join(lines),encoding="utf-8")
    (outdir/"SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("[8/8] PHASE 85 OK",flush=True)
    print("Report:",report,flush=True)
    print("Summary:",outdir/"SUMMARY.json",flush=True)
    print("No gameplay bytes were changed.",flush=True)

if __name__=="__main__":
    main()
