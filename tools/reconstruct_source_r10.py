#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,struct,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM

EXPECTED_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

PATCH_FILE=0x005730B4
PATCH_VA=0x00973CB4
PATCH_ORIGINAL=bytes.fromhex("8B 49 44 C7 45")
CONTINUE_VA=0x00973CCA
SIGNAL_HELPER=0x00936BE0
GS_VTABLE=0x0186A9CC
GS_BUILD_SLOT=0x110
MIN_CAVE=64

def u16(b,o):return struct.unpack_from("<H",b,o)[0]
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def p32(x):return struct.pack("<I",x&0xffffffff)
def rel32(src_after,target):return p32((target-src_after)&0xffffffff)
def sha(b):return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0":raise RuntimeError("invalid PE")
    n=u16(d,pe+6);optsz=u16(d,pe+20);opt=pe+24
    if u16(d,pe+4)!=0x14c or u16(d,opt)!=0x10b:raise RuntimeError("expected x86 PE32")
    ib=u32(d,opt+28);so=opt+optsz;secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({
            "name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
            "raw":u32(d,o+20),"ch":u32(d,o+36)
        })
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
            f=s["raw"]+(rva-s["va"])
            if s["raw"]<=f<s["raw"]+s["rs"]:return f
    return None

def direct_targets(md,d,ib,secs):
    out=set()
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);va=ib+s["va"]
        for x in md.disasm(d[a:b],va):
            if x.mnemonic not in ("call","jmp","je","jne","jz","jnz","ja","jae","jb","jbe","jg","jge","jl","jle"):
                continue
            if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                out.add(x.operands[0].imm&0xffffffff)
    return out

def read_function_ranges(path):
    rows=[]
    if not path.is_file():return rows
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            try:a=int(r.get("file_start",""),16);b=int(r.get("file_end",""),16)
            except:continue
            if b>a:rows.append((a,b))
    return rows

def overlaps_ranges(a,b,ranges):
    # Do not reject cave merely because an atlas "function" spans padding;
    # reject only if a function START lies inside the cave.
    for x,y in ranges:
        if a<=x<b:return True
    return False

def find_cave(d,ib,secs,targets,function_ranges):
    candidates=[]
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"])
        p=a
        while p<b:
            if d[p]!=0xCC:
                p+=1;continue
            q=p
            while q<b and d[q]==0xCC:q+=1
            n=q-p
            if n>=MIN_CAVE:
                va=f2v(p,ib,secs)
                if va is not None:
                    target_inside=any(va<=t<va+n for t in targets)
                    fn_start_inside=overlaps_ranges(p,q,function_ranges)
                    if not target_inside and not fn_start_inside:
                        candidates.append({"file":p,"va":va,"length":n,"section":s["name"]})
            p=max(q,p+1)
    # Prefer smallest sufficient cave to avoid consuming a huge region, then nearest to callback.
    candidates.sort(key=lambda c:(c["length"],abs(c["va"]-PATCH_VA)))
    return candidates

class Stub:
    def __init__(self,base):
        self.base=base;self.b=bytearray();self.labels={};self.short_fix=[]
    @property
    def va(self):return self.base+len(self.b)
    def emit(self,h):self.b+=bytes.fromhex(h)
    def label(self,n):self.labels[n]=self.va
    def jcc8(self,opcode,label):
        pos=self.va;self.b+=bytes([opcode,0]);self.short_fix.append((len(self.b)-1,pos+2,label))
    def call(self,target):
        after=self.va+5;self.b+=b"\xE8"+rel32(after,target)
    def jmp(self,target):
        after=self.va+5;self.b+=b"\xE9"+rel32(after,target)
    def finish(self):
        for idx,after,label in self.short_fix:
            target=self.labels[label];delta=target-after
            if not(-128<=delta<=127):raise RuntimeError("short branch overflow")
            self.b[idx]=delta&0xff
        return bytes(self.b)

def build_stub(base):
    s=Stub(base)
    # Original ECX is GarageBottomBarWidget*. EDI is saved by original prologue
    # and is not semantically initialized until later cleanup code.
    s.emit("8B F9")                         # mov edi,ecx  ; preserve GBBW this
    s.emit("8B 41 44")                      # mov eax,[ecx+44] buildSignal.object
    s.emit("C7 45 FC 00 00 00 00")          # original SEH state = 0
    s.emit("85 C0")                         # test eax,eax
    s.jcc8(0x74,"fallback")                 # jz fallback
    s.emit("8B 48 08")                      # mov ecx,[eax+8]
    s.call(SIGNAL_HELPER)                    # original behavior
    s.jmp(CONTINUE_VA)

    s.label("fallback")
    s.emit("8B 4F 04")                      # mov ecx,[edi+4] candidate owner
    s.emit("85 C9")                         # test ecx,ecx
    s.jcc8(0x74,"cleanup")
    s.emit("8B 01")                         # mov eax,[ecx] vtable
    s.emit("3D "+p32(GS_VTABLE).hex(" "))    # cmp eax,GS_Garage vtable
    s.jcc8(0x75,"cleanup")
    s.emit("FF 90 10 01 00 00")             # call dword ptr [eax+110h]

    s.label("cleanup")
    s.jmp(CONTINUE_VA)
    return s.finish()

def patch_bytes(cave_va):
    return b"\xE9"+rel32(PATCH_VA+5,cave_va)

def write_cmds(root,script_rel):
    apply_cmd=root/"R10-APPLY-OWNER-FALLBACK.cmd"
    revert_cmd=root/"R10-REVERT-OWNER-FALLBACK.cmd"
    apply_cmd.write_text(f'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "{script_rel}" --project-root "%CD%" --apply
if errorlevel 1 (
  echo.
  echo [ERRO] R10 nao foi aplicado.
  pause
  exit /b 1
)
echo.
echo R10 aplicado. Execute o jogo pelo launcher normal e teste MONTAR.
pause
''',encoding="utf-8")
    revert_cmd.write_text(f'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "{script_rel}" --project-root "%CD%" --revert
if errorlevel 1 (
  echo.
  echo [ERRO] R10 nao foi revertido.
  pause
  exit /b 1
)
echo.
echo R10 revertido.
pause
''',encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    g=ap.add_mutually_exclusive_group()
    g.add_argument("--plan",action="store_true")
    g.add_argument("--apply",action="store_true")
    g.add_argument("--revert",action="store_true")
    ns=ap.parse_args()
    if not(ns.plan or ns.apply or ns.revert):ns.plan=True

    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    atlas=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX"
    out=root/"src-reconstructed"/"reverse"/"r10"
    out.mkdir(parents=True,exist_ok=True)
    backup=root/"_PACKAGE_PHASE5"/"AMS.exe.r10-owner-fallback.bak"
    state_path=out/"OWNER_FALLBACK_PATCH.json"

    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")
    d=bytearray(ams.read_bytes())
    ib,secs=parse_pe(d)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True

    if ns.revert:
        if backup.is_file():
            shutil.copy2(backup,ams)
            print("[R10] Revertido usando backup:",backup)
            print("SHA:",sha(ams.read_bytes()))
            return
        if not state_path.is_file():raise SystemExit("backup/state R10 nao encontrado")
        st=json.loads(state_path.read_text(encoding="utf-8"))
        pf=int(st["patch_file"],16);cf=int(st["cave_file"],16)
        orig=bytes.fromhex(st["patch_original"])
        cave_orig=bytes.fromhex(st["cave_original"])
        d[pf:pf+len(orig)]=orig
        d[cf:cf+len(cave_orig)]=cave_orig
        ams.write_bytes(d)
        print("[R10] Revertido por state.")
        print("SHA:",sha(d))
        return

    cur_sha=sha(d)
    if cur_sha!=EXPECTED_SHA:
        # apply can also be idempotent if state matches a previous R10 result
        if ns.apply and state_path.is_file():
            st=json.loads(state_path.read_text(encoding="utf-8"))
            if cur_sha==st.get("patched_sha256"):
                print("[R10] Patch ja aplicado.")
                return
        raise SystemExit("AMS SHA inesperado: "+cur_sha)

    if bytes(d[PATCH_FILE:PATCH_FILE+5])!=PATCH_ORIGINAL:
        raise SystemExit("guard falhou em 0x005730B4: "+bytes(d[PATCH_FILE:PATCH_FILE+5]).hex(" ").upper())

    targets=direct_targets(md,d,ib,secs)
    ranges=read_function_ranges(atlas/"FUNCTIONS.csv")
    caves=find_cave(d,ib,secs,targets,ranges)
    if not caves:raise SystemExit("nenhum code cave 0xCC seguro >=64 bytes encontrado")
    cave=caves[0]
    stub=build_stub(cave["va"])
    if len(stub)>cave["length"]:raise SystemExit("stub maior que cave")
    pbytes=patch_bytes(cave["va"])

    cave_orig=bytes(d[cave["file"]:cave["file"]+len(stub)])
    state={
        "phase":"R10",
        "mode":"OWNER_FALLBACK_GUARDED",
        "base_sha256":cur_sha,
        "patch_file":f"0x{PATCH_FILE:08X}",
        "patch_va":f"0x{PATCH_VA:08X}",
        "patch_original":PATCH_ORIGINAL.hex(" ").upper(),
        "patch_new":pbytes.hex(" ").upper(),
        "cave_file":f"0x{cave['file']:08X}",
        "cave_va":f"0x{cave['va']:08X}",
        "cave_length":cave["length"],
        "stub_length":len(stub),
        "cave_original":cave_orig.hex(" ").upper(),
        "stub_bytes":stub.hex(" ").upper(),
        "guards":{
            "buildSignal":"preserve original signal path when GBBW+0x44 != null",
            "owner_nonnull":"GBBW+0x04 must be non-null",
            "owner_vtable":f"must equal 0x{GS_VTABLE:08X}",
            "build_dispatch":"call [owner.vtable+0x110] only after exact vtable match"
        },
        "fallback_behavior":"if owner check fails, continue at original cleanup 0x00973CCA",
        "applied":False
    }

    if ns.plan:
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
        write_cmds(root,"tools\\reconstruct_source_r10.py")
        print("[R10 PLAN] READY")
        print("Cave file=0x%08X VA=0x%08X len=%d stub=%d"%(cave["file"],cave["va"],cave["length"],len(stub)))
        print("Patch site original:",PATCH_ORIGINAL.hex(" ").upper())
        print("Patch site new     :",pbytes.hex(" ").upper())
        print("Generated:",state_path)
        print("Generated: R10-APPLY-OWNER-FALLBACK.cmd")
        print("Generated: R10-REVERT-OWNER-FALLBACK.cmd")
        print("NO gameplay bytes changed.")
        return

    if ns.apply:
        if not backup.exists():shutil.copy2(ams,backup)
        d[PATCH_FILE:PATCH_FILE+5]=pbytes
        d[cave["file"]:cave["file"]+len(stub)]=stub
        ams.write_bytes(d)
        patched=sha(d)
        state["applied"]=True
        state["patched_sha256"]=patched
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
        print("[R10 APPLY] OWNER FALLBACK APPLIED")
        print("Backup:",backup)
        print("Patched SHA:",patched)
        print("Test MONTAR. If behavior regresses, run R10-REVERT-OWNER-FALLBACK.cmd.")
        return

if __name__=="__main__":main()
