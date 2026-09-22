#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,struct,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

EXPECTED_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

GS_CTOR=0x00E00B20
GS_PRIMARY_VT=0x0186A9CC
PATCH_FILE=0x005730B4
PATCH_VA=0x00973CB4
PATCH_ORIGINAL=bytes.fromhex("8B 49 44 C7 45")
CONTINUE_VA=0x00973CCA
SIGNAL_HELPER=0x00936BE0
MIN_REQUIRED_SLOTS=0xE0 // 4  # must support at least through +0xDC

def u16(b,o):return struct.unpack_from("<H",b,o)[0]
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def p32(x):return struct.pack("<I",x&0xffffffff)
def sha(b):return hashlib.sha256(b).hexdigest()
def rel32(src_after,target):return p32((target-src_after)&0xffffffff)

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0":raise RuntimeError("invalid PE")
    n=u16(d,pe+6);optsz=u16(d,pe+20);opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28);so=opt+optsz;secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({"name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
                     "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
                     "raw":u32(d,o+20),"ch":u32(d,o+36)})
    return ib,secs

def v2f(va,ib,secs):
    rva=va-ib
    for s in secs:
        if s["va"]<=rva<s["va"]+max(s["vs"],s["rs"]):
            f=s["raw"]+(rva-s["va"])
            if s["raw"]<=f<s["raw"]+s["rs"]:return f
    return None

def f2v(off,ib,secs):
    for s in secs:
        if s["raw"]<=off<s["raw"]+s["rs"]:return ib+s["va"]+(off-s["raw"])
    return None

def is_exec_va(va,ib,secs):
    f=v2f(va,ib,secs)
    if f is None:return False
    for s in secs:
        if s["raw"]<=f<s["raw"]+s["rs"]:return bool(s["ch"]&0x20000000)
    return False

def next_prologue(d,start,secs,limit=0x4000):
    end=min(len(d),start+limit)
    for s in secs:
        if s["raw"]<=start<s["raw"]+s["rs"]:
            end=min(end,s["raw"]+s["rs"]);break
    p=d.find(b"\x55\x8B\xEC",start+3,end)
    return p if p>=0 else end

def read_vtable_len(d,vt,ib,secs,max_slots=128):
    f=v2f(vt,ib,secs)
    if f is None:return 0
    n=0
    for i in range(max_slots):
        if f+i*4+4>len(d):break
        t=u32(d,f+i*4)
        if not is_exec_va(t,ib,secs):break
        n+=1
    return n

def plausible_vtable(d,vt,ib,secs):
    return read_vtable_len(d,vt,ib,secs,8)>=2

def gs_final_vtables(md,d,ib,secs):
    fs=v2f(GS_CTOR,ib,secs)
    if fs is None:raise RuntimeError("GS ctor not mapped")
    fe=next_prologue(d,fs,secs)
    ins=list(md.disasm(d[fs:fe],GS_CTOR))
    aliases={"ecx":0}
    out=[]
    for x in ins:
        ops=x.operands
        if x.mnemonic=="mov" and len(ops)==2 and ops[0].type==X86_OP_REG:
            dst=md.reg_name(ops[0].reg)
            if ops[1].type==X86_OP_REG:
                src=md.reg_name(ops[1].reg)
                if src in aliases:aliases[dst]=aliases[src]
                else:aliases.pop(dst,None)
        if x.mnemonic=="mov" and len(ops)==2 and ops[0].type==X86_OP_MEM and ops[1].type==X86_OP_IMM:
            m=ops[0].mem;base=md.reg_name(m.base) if m.base else ""
            if base in aliases and not m.index:
                off=aliases[base]+m.disp
                vt=ops[1].imm&0xffffffff
                if 0<=off<=0x1000 and plausible_vtable(d,vt,ib,secs):
                    out.append({
                        "offset":off,"vtable":vt,"write_va":x.address,
                        "slot_count":read_vtable_len(d,vt,ib,secs,128)
                    })
    # Last write at each subobject offset wins in most-derived ctor.
    final={}
    for x in out:final[x["offset"]]=x
    vals=sorted(final.values(),key=lambda x:x["offset"])
    # Primary is validated separately. Owner interface must expose +DC.
    candidates=[x for x in vals if x["slot_count"]>=MIN_REQUIRED_SLOTS]
    return vals,candidates

def code_references(md,d,ib,secs):
    out=set()
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);va=ib+s["va"]
        for x in md.disasm(d[a:b],va):
            if x.mnemonic in ("call","jmp","je","jne","jz","jnz","ja","jae","jb","jbe","jg","jge","jl","jle"):
                if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                    out.add(x.operands[0].imm&0xffffffff)
            for op in x.operands:
                ref=None
                if op.type==X86_OP_IMM:ref=op.imm&0xffffffff
                elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index:ref=op.mem.disp&0xffffffff
                if ref is not None and v2f(ref,ib,secs) is not None:out.add(ref)
    return out

def scan_runs(d,a,b,allowed,minlen,ib,secs,refs,tier,section):
    out=[];p=a
    while p<b:
        if d[p] not in allowed:p+=1;continue
        q=p
        while q<b and d[q] in allowed:q+=1
        n=q-p
        if n>=minlen:
            va=f2v(p,ib,secs)
            if va is not None and not any(va<=r<va+n for r in refs):
                out.append({"file":p,"va":va,"length":n,"section":section,"tier":tier,
                            "padding":"mixed-"+"/".join(f"{x:02X}" for x in sorted(allowed))})
        p=max(q,p+1)
    return out

def find_caves(d,ib,secs,refs,minlen):
    out=[]
    tiers=[({0xCC},1),({0x90},2),({0xCC,0x90},3),({0x00,0x90,0xCC},4)]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"])
        for allowed,tier in tiers:out+=scan_runs(d,a,b,allowed,minlen,ib,secs,refs,tier,s["name"])
    best={}
    for x in out:
        k=(x["file"],x["va"])
        if k not in best or x["tier"]<best[k]["tier"]:best[k]=x
    out=list(best.values())
    out.sort(key=lambda x:(x["tier"],x["length"],abs(x["va"]-PATCH_VA)))
    return out

class Stub:
    def __init__(self,base):
        self.base=base;self.b=bytearray();self.labels={};self.rel8=[];self.rel32fix=[]
    @property
    def va(self):return self.base+len(self.b)
    def emit(self,h):self.b+=bytes.fromhex(h)
    def label(self,n):self.labels[n]=self.va
    def jcc8(self,op,label):
        after=self.va+2;self.b+=bytes([op,0]);self.rel8.append((len(self.b)-1,after,label))
    def jmp_label32(self,label):
        after=self.va+5;self.b+=b"\xE9"+b"\0\0\0\0";self.rel32fix.append((len(self.b)-4,after,label))
    def jcc32(self,op2,label):
        # 0F 8x rel32
        after=self.va+6;self.b+=bytes([0x0F,op2])+b"\0\0\0\0";self.rel32fix.append((len(self.b)-4,after,label))
    def call_abs(self,target):
        after=self.va+5;self.b+=b"\xE8"+rel32(after,target)
    def jmp_abs(self,target):
        after=self.va+5;self.b+=b"\xE9"+rel32(after,target)
    def finish(self):
        for idx,after,label in self.rel8:
            delta=self.labels[label]-after
            if not -128<=delta<=127:raise RuntimeError("rel8 overflow "+label)
            self.b[idx]=delta&0xff
        for idx,after,label in self.rel32fix:
            self.b[idx:idx+4]=rel32(after,self.labels[label])
        return bytes(self.b)

def build_stub(base,candidates):
    s=Stub(base)
    # preserve GBBW this in EDI (EDI is saved by original prologue)
    s.emit("8B F9")                         # mov edi,ecx
    s.emit("8B 41 44")                      # mov eax,[ecx+44]
    s.emit("C7 45 FC 00 00 00 00")          # replay original SEH state
    s.emit("85 C0")
    s.jcc8(0x74,"fallback")
    s.emit("8B 48 08")
    s.call_abs(SIGNAL_HELPER)
    s.jmp_abs(CONTINUE_VA)

    s.label("fallback")
    s.emit("8B 57 04")                      # mov edx,[edi+4] owner/base iface
    s.emit("85 D2")
    s.jcc32(0x84,"cleanup")
    s.emit("8B 02")                         # eax=[owner] vtable

    # Dispatch by exact GS_Garage secondary vtable.
    for i,c in enumerate(candidates):
        s.emit("3D "+p32(c["vtable"]).hex(" "))   # cmp eax,vt
        s.jcc32(0x84,f"match_{i}")
    s.jmp_label32("cleanup")

    for i,c in enumerate(candidates):
        s.label(f"match_{i}")
        s.emit("8B CA")                     # mov ecx,edx
        off=c["offset"]
        if off:
            s.emit("81 E9 "+p32(off).hex(" "))   # sub ecx,offset -> primary GS
        s.emit("8B 01")                     # eax=[gs]
        s.emit("3D "+p32(GS_PRIMARY_VT).hex(" "))
        s.jcc32(0x85,"cleanup")
        s.emit("FF 90 10 01 00 00")         # call [eax+110]
        s.jmp_label32("cleanup")

    s.label("cleanup")
    s.jmp_abs(CONTINUE_VA)
    return s.finish()

def patch_bytes(cave_va):return b"\xE9"+rel32(PATCH_VA+5,cave_va)

def write_cmds(root):
    (root/"R11-APPLY-SUBOBJECT-OWNER-FALLBACK.cmd").write_text(r'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "tools\reconstruct_source_r11.py" --project-root "%CD%" --apply
if errorlevel 1 (
  echo.
  echo [ERRO] R11 nao foi aplicado.
  pause
  exit /b 1
)
echo.
echo R11 aplicado. Abra o jogo pelo launcher normal e teste MONTAR.
pause
''',encoding="utf-8")
    (root/"R11-REVERT-SUBOBJECT-OWNER-FALLBACK.cmd").write_text(r'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "tools\reconstruct_source_r11.py" --project-root "%CD%" --revert
if errorlevel 1 (
  echo.
  echo [ERRO] R11 nao foi revertido.
  pause
  exit /b 1
)
echo.
echo R11 revertido.
pause
''',encoding="utf-8")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    g=ap.add_mutually_exclusive_group();g.add_argument("--plan",action="store_true");g.add_argument("--apply",action="store_true");g.add_argument("--revert",action="store_true")
    ns=ap.parse_args()
    if not(ns.plan or ns.apply or ns.revert):ns.plan=True
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    out=root/"src-reconstructed"/"reverse"/"r11";out.mkdir(parents=True,exist_ok=True)
    state_path=out/"SUBOBJECT_OWNER_FALLBACK.json"
    backup=root/"_PACKAGE_PHASE5"/"AMS.exe.r11-subobject-owner.bak"
    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")

    if ns.revert:
        if backup.is_file():
            shutil.copy2(backup,ams)
            print("[R11] Revertido usando backup.")
            print("SHA:",sha(ams.read_bytes()));return
        if not state_path.is_file():raise SystemExit("R11 backup/state nao encontrado")
        st=json.loads(state_path.read_text(encoding="utf-8"))
        d=bytearray(ams.read_bytes())
        pf=int(st["patch_file"],16);cf=int(st["cave_file"],16)
        orig=bytes.fromhex(st["patch_original"]);cave_orig=bytes.fromhex(st["cave_original"])
        d[pf:pf+len(orig)]=orig;d[cf:cf+len(cave_orig)]=cave_orig
        ams.write_bytes(d);print("[R11] Revertido por state.");print("SHA:",sha(d));return

    d=bytearray(ams.read_bytes());cur=sha(d)
    if cur!=EXPECTED_SHA:
        if ns.apply and state_path.is_file():
            st=json.loads(state_path.read_text(encoding="utf-8"))
            if cur==st.get("patched_sha256"):
                print("[R11] Patch ja aplicado.");return
        raise SystemExit("AMS SHA inesperado: "+cur+" (reverta R10 antes de R11)")
    if bytes(d[PATCH_FILE:PATCH_FILE+5])!=PATCH_ORIGINAL:
        raise SystemExit("guard patch site falhou: "+bytes(d[PATCH_FILE:PATCH_FILE+5]).hex(" ").upper())

    ib,secs=parse_pe(d);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    all_vts,cands=gs_final_vtables(md,d,ib,secs)
    # Exclude primary; fallback already knows primary check and owner is expected secondary.
    cands=[x for x in cands if x["offset"]!=0]
    if not cands:raise SystemExit("nenhuma vtable secundaria GS_Garage com slot +0xDC encontrada")

    # Build once at arbitrary base to get exact size.
    probe=build_stub(PATCH_VA,cands);need=len(probe)
    refs=code_references(md,d,ib,secs);caves=find_caves(d,ib,secs,refs,need)
    if not caves:raise SystemExit(f"nenhum cave seguro >= {need} bytes")
    cave=caves[0];stub=build_stub(cave["va"],cands)
    if len(stub)>cave["length"]:raise SystemExit("stub > cave")
    pbytes=patch_bytes(cave["va"]);cave_orig=bytes(d[cave["file"]:cave["file"]+len(stub)])

    state={
      "phase":"R11","mode":"GS_SUBOBJECT_OWNER_FALLBACK",
      "base_sha256":cur,
      "patch_file":f"0x{PATCH_FILE:08X}","patch_va":f"0x{PATCH_VA:08X}",
      "patch_original":PATCH_ORIGINAL.hex(" ").upper(),"patch_new":pbytes.hex(" ").upper(),
      "cave_file":f"0x{cave['file']:08X}","cave_va":f"0x{cave['va']:08X}",
      "cave_length":cave["length"],"cave_tier":cave["tier"],"cave_padding":cave["padding"],
      "stub_length":len(stub),"cave_original":cave_orig.hex(" ").upper(),"stub_bytes":stub.hex(" ").upper(),
      "gs_primary_vtable":f"0x{GS_PRIMARY_VT:08X}",
      "all_final_gs_vtables":[{"offset":f"0x{x['offset']:X}","vtable":f"0x{x['vtable']:08X}","slot_count":x["slot_count"],"write_va":f"0x{x['write_va']:08X}"} for x in all_vts],
      "owner_candidate_vtables":[{"offset":f"0x{x['offset']:X}","vtable":f"0x{x['vtable']:08X}","slot_count":x["slot_count"]} for x in cands],
      "guards":[
        "buildSignal non-null => exact original signal path",
        "GBBW+0x04 must be non-null",
        "owner vtable must match a final GS_Garage secondary vtable with slot +0xDC",
        "owner pointer is adjusted back by that subobject offset",
        "adjusted object must have primary vtable 0x0186A9CC",
        "only then call virtual +0x110 BuildCar"
      ],
      "applied":False
    }

    if ns.plan:
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8");write_cmds(root)
        print("[R11 PLAN] READY")
        print("GS final vtables:",len(all_vts))
        print("Owner candidates:",len(cands))
        for x in cands:print("   offset=0x%X vt=0x%08X slots=%d"%(x["offset"],x["vtable"],x["slot_count"]))
        print("Cave file=0x%08X VA=0x%08X len=%d stub=%d tier=%d"%(cave["file"],cave["va"],cave["length"],len(stub),cave["tier"]))
        print("Generated:",state_path)
        print("NO gameplay bytes changed.");return

    if ns.apply:
        if not backup.exists():shutil.copy2(ams,backup)
        d[PATCH_FILE:PATCH_FILE+5]=pbytes;d[cave["file"]:cave["file"]+len(stub)]=stub
        ams.write_bytes(d);patched=sha(d);state["applied"]=True;state["patched_sha256"]=patched
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
        print("[R11 APPLY] APPLIED");print("Patched SHA:",patched)
        print("Teste MONTAR. Revert disponivel em R11-REVERT-SUBOBJECT-OWNER-FALLBACK.cmd")

if __name__=="__main__":main()
