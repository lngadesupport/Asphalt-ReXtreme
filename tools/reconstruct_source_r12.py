#!/usr/bin/env python3
from __future__ import annotations
import argparse,ctypes,csv,hashlib,json,struct,shutil,time
from ctypes import wintypes
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM

EXPECTED_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

PATCH_FILE=0x005730B4
PATCH_VA=0x00973CB4
PATCH_ORIGINAL=bytes.fromhex("8B 49 44 C7 45")
CONTINUE_VA=0x00973CCA
SIGNAL_HELPER=0x00936BE0
MAGIC=0x52313250  # "P21R" little endian marker
PROBE_NAMES=("magic","click_count","gbbw","build_signal","owner","owner_control","owner_vtable")
PROBE_SIZE=len(PROBE_NAMES)*4

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
    image_base=u32(d,opt+28)
    dll_chars=u16(d,opt+70)
    so=opt+optsz;secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({"name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
                     "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
                     "raw":u32(d,o+20),"ch":u32(d,o+36)})
    return image_base,dll_chars,secs

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

def code_references(md,d,ib,secs):
    refs=set()
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"]);va=ib+s["va"]
        for x in md.disasm(d[a:b],va):
            if x.mnemonic in ("call","jmp","je","jne","jz","jnz","ja","jae","jb","jbe","jg","jge","jl","jle"):
                if len(x.operands)==1 and x.operands[0].type==X86_OP_IMM:
                    refs.add(x.operands[0].imm&0xffffffff)
            for op in x.operands:
                ref=None
                if op.type==X86_OP_IMM:ref=op.imm&0xffffffff
                elif op.type==X86_OP_MEM and not op.mem.base and not op.mem.index:ref=op.mem.disp&0xffffffff
                if ref is not None and v2f(ref,ib,secs) is not None:refs.add(ref)
    return refs

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
    for s in secs:
        if not(s["ch"]&0x20000000):continue
        a=s["raw"];b=min(len(d),a+s["rs"])
        for allowed,tier in [({0xCC},1),({0x90},2),({0xCC,0x90},3),({0x00,0x90,0xCC},4)]:
            out += scan_runs(d,a,b,allowed,minlen,ib,secs,refs,tier,s["name"])
    best={}
    for x in out:
        k=(x["file"],x["va"])
        if k not in best or x["tier"]<best[k]["tier"]:best[k]=x
    out=list(best.values())
    out.sort(key=lambda x:(x["tier"],x["length"],abs(x["va"]-PATCH_VA)))
    return out

class ProbeBuilder:
    def __init__(self,base):
        self.base=base
        self.b=bytearray()
        self.labels={}
        self.rel8=[]
        self.datafix=[]
        self.anchor_off=None

    @property
    def off(self):return len(self.b)
    @property
    def va(self):return self.base+len(self.b)

    def emit(self,h):self.b+=bytes.fromhex(h)

    def label(self,name):self.labels[name]=self.off

    def call_get_eip_edx(self):
        # call next; pop edx. EDX = address of pop instruction.
        self.emit("E8 00 00 00 00")
        self.anchor_off=self.off
        self.emit("5A")

    def mem_edx_disp(self,prefix,data_name):
        # prefix includes opcode+modrm for [edx+disp32]
        self.emit(prefix)
        pos=self.off
        self.b+=b"\0\0\0\0"
        self.datafix.append((pos,data_name))

    def jcc8(self,op,label):
        after=self.off+2
        self.b+=bytes([op,0])
        self.rel8.append((self.off-1,after,label))

    def finish(self):
        # original execution tail first
        for idx,after,label in self.rel8:
            delta=self.labels[label]-after
            if not -128<=delta<=127:raise RuntimeError("rel8 overflow")
            self.b[idx]=delta&0xff

        # align local probe storage
        while len(self.b)%4:self.b+=b"\x90"
        data_off=len(self.b)
        offsets={}
        for i,name in enumerate(PROBE_NAMES):offsets[name]=data_off+i*4

        # initialize data
        data=bytearray(PROBE_SIZE)
        struct.pack_into("<I",data,0,MAGIC)
        self.b+=data

        if self.anchor_off is None:raise RuntimeError("missing EIP anchor")
        for pos,name in self.datafix:
            disp=offsets[name]-self.anchor_off
            self.b[pos:pos+4]=struct.pack("<i",disp)

        return bytes(self.b),data_off,offsets

def build_probe(base):
    s=ProbeBuilder(base)

    # Preserve caller-visible scratch registers. ECX remains the original GBBW.
    s.emit("50")                    # push eax
    s.emit("52")                    # push edx
    s.call_get_eip_edx()

    # click_count++
    s.mem_edx_disp("FF 82","click_count")  # inc dword ptr [edx+disp32]

    # store GBBW this
    s.mem_edx_disp("89 8A","gbbw")         # mov [edx+disp32],ecx

    # signal
    s.emit("8B 41 44")
    s.mem_edx_disp("89 82","build_signal")

    # owner
    s.emit("8B 41 04")
    s.mem_edx_disp("89 82","owner")

    # owner control
    s.emit("8B 41 08")
    s.mem_edx_disp("89 82","owner_control")

    # owner vtable
    s.emit("8B 41 04")
    s.emit("85 C0")
    s.jcc8(0x74,"no_owner")
    s.emit("8B 00")
    s.mem_edx_disp("89 82","owner_vtable")
    s.jcc8(0xEB,"probe_done")

    s.label("no_owner")
    s.emit("33 C0")
    s.mem_edx_disp("89 82","owner_vtable")

    s.label("probe_done")
    s.emit("5A")                    # pop edx
    s.emit("58")                    # pop eax

    # Replay exact original logic from overwritten region onward.
    s.emit("8B 49 44")             # mov ecx,[ecx+44]
    s.emit("C7 45 FC 00 00 00 00")
    s.emit("85 C9")
    s.jcc8(0x74,"cleanup")
    s.emit("8B 49 08")
    # call helper relative; base known now
    after=s.va+5
    s.b+=b"\xE8"+rel32(after,SIGNAL_HELPER)

    s.label("cleanup")
    after=s.va+5
    s.b+=b"\xE9"+rel32(after,CONTINUE_VA)

    return s.finish()

def patch_bytes(cave_va):return b"\xE9"+rel32(PATCH_VA+5,cave_va)

# ---------------- Windows runtime reader ----------------
TH32CS_SNAPPROCESS=0x00000002
TH32CS_SNAPMODULE=0x00000008
TH32CS_SNAPMODULE32=0x00000010
PROCESS_VM_READ=0x0010
PROCESS_QUERY_INFORMATION=0x0400
INVALID_HANDLE_VALUE=ctypes.c_void_p(-1).value

class PROCESSENTRY32W(ctypes.Structure):
    _fields_=[("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),("th32ProcessID",wintypes.DWORD),
              ("th32DefaultHeapID",ctypes.POINTER(ctypes.c_ulong)),("th32ModuleID",wintypes.DWORD),
              ("cntThreads",wintypes.DWORD),("th32ParentProcessID",wintypes.DWORD),
              ("pcPriClassBase",ctypes.c_long),("dwFlags",wintypes.DWORD),
              ("szExeFile",wintypes.WCHAR*260)]

class MODULEENTRY32W(ctypes.Structure):
    _fields_=[("dwSize",wintypes.DWORD),("th32ModuleID",wintypes.DWORD),("th32ProcessID",wintypes.DWORD),
              ("GlblcntUsage",wintypes.DWORD),("ProccntUsage",wintypes.DWORD),
              ("modBaseAddr",ctypes.POINTER(ctypes.c_byte)),("modBaseSize",wintypes.DWORD),
              ("hModule",wintypes.HMODULE),("szModule",wintypes.WCHAR*256),("szExePath",wintypes.WCHAR*260)]

def find_pid(exe="AMS.exe"):
    k=ctypes.windll.kernel32
    snap=k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0)
    if snap==INVALID_HANDLE_VALUE:return None
    try:
        pe=PROCESSENTRY32W();pe.dwSize=ctypes.sizeof(pe)
        ok=k.Process32FirstW(snap,ctypes.byref(pe))
        while ok:
            if pe.szExeFile.lower()==exe.lower():return int(pe.th32ProcessID)
            ok=k.Process32NextW(snap,ctypes.byref(pe))
    finally:k.CloseHandle(snap)
    return None

def module_base(pid,exe="AMS.exe"):
    k=ctypes.windll.kernel32
    snap=k.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid)
    if snap==INVALID_HANDLE_VALUE:return None
    try:
        me=MODULEENTRY32W();me.dwSize=ctypes.sizeof(me)
        ok=k.Module32FirstW(snap,ctypes.byref(me))
        while ok:
            if me.szModule.lower()==exe.lower():
                return ctypes.cast(me.modBaseAddr,ctypes.c_void_p).value
            ok=k.Module32NextW(snap,ctypes.byref(me))
    finally:k.CloseHandle(snap)
    return None

def read_mem(handle,address,size):
    k=ctypes.windll.kernel32
    buf=(ctypes.c_ubyte*size)()
    got=ctypes.c_size_t()
    if not k.ReadProcessMemory(handle,ctypes.c_void_p(address),buf,size,ctypes.byref(got)):
        return None
    return bytes(buf[:got.value])

def normalize_ptr(ptr,delta):
    if not ptr:return None
    return (ptr-delta)&0xffffffff

def watch(root,state_path):
    if not state_path.is_file():raise SystemExit("R12 state nao encontrado; rode PLAN/APPLY primeiro")
    st=json.loads(state_path.read_text(encoding="utf-8"))
    if not st.get("applied"):raise SystemExit("R12 probe ainda nao esta aplicado")
    preferred=int(st["image_base"],16)
    probe_rva=int(st["probe_rva"],16)
    out=state_path.parent/"RUNTIME_OWNER_CAPTURE.json"

    print("[R12 WATCH] Procurando AMS.exe...")
    while True:
        pid=find_pid()
        if pid:break
        time.sleep(1)
    base=module_base(pid)
    if not base:raise SystemExit("nao consegui obter base do AMS.exe")
    delta=base-preferred
    addr=base+probe_rva

    k=ctypes.windll.kernel32
    h=k.OpenProcess(PROCESS_VM_READ|PROCESS_QUERY_INFORMATION,False,pid)
    if not h:raise SystemExit("OpenProcess falhou; tente executar CMD como administrador")
    try:
        print(f"[R12 WATCH] PID={pid} moduleBase=0x{base:08X} ASLRdelta=0x{delta & 0xffffffff:08X}")
        print("[R12 WATCH] Va para garagem e clique MONTAR.")
        last=-1
        while True:
            raw=read_mem(h,addr,PROBE_SIZE)
            if not raw or len(raw)<PROBE_SIZE:
                print("[R12 WATCH] processo encerrou ou probe ficou inacessivel.")
                break
            vals=struct.unpack("<"+"I"*len(PROBE_NAMES),raw)
            rec=dict(zip(PROBE_NAMES,vals))
            if rec["magic"]!=MAGIC:
                print(f"[R12 WATCH] magic inesperado 0x{rec['magic']:08X}")
                time.sleep(1);continue
            if rec["click_count"]!=last:
                last=rec["click_count"]
                owner_vt_pref=normalize_ptr(rec["owner_vtable"],delta)
                snap={
                    "pid":pid,"module_base_runtime":f"0x{base:08X}",
                    "preferred_image_base":f"0x{preferred:08X}",
                    "aslr_delta":f"0x{delta & 0xffffffff:08X}",
                    **{k:f"0x{v:08X}" if k!="click_count" else v for k,v in rec.items()},
                    "owner_vtable_normalized":f"0x{owner_vt_pref:08X}" if owner_vt_pref else None,
                    "vtable_slots":[]
                }
                if rec["owner_vtable"]:
                    block=read_mem(h,rec["owner_vtable"],0x120)
                    if block:
                        for off in range(0,min(len(block),0x120),4):
                            p=struct.unpack_from("<I",block,off)[0]
                            snap["vtable_slots"].append({
                                "slot":f"0x{off:X}",
                                "runtime":f"0x{p:08X}",
                                "normalized":f"0x{normalize_ptr(p,delta):08X}" if p else None
                            })
                out.write_text(json.dumps(snap,indent=2),encoding="utf-8")
                print("")
                print("=== R12 CAPTURE ===")
                print("click_count   :",rec["click_count"])
                print("GBBW          : 0x%08X"%rec["gbbw"])
                print("buildSignal   : 0x%08X"%rec["build_signal"])
                print("owner         : 0x%08X"%rec["owner"])
                print("ownerControl  : 0x%08X"%rec["owner_control"])
                print("ownerVtable RT: 0x%08X"%rec["owner_vtable"])
                print("ownerVtable VA:",("0x%08X"%owner_vt_pref) if owner_vt_pref else "NULL")
                print("Capture file  :",out)
                if rec["click_count"]>0:
                    print("Capture obturado. Pode fechar este watcher com Ctrl+C e enviar o JSON.")
            time.sleep(0.25)
    finally:k.CloseHandle(h)

def write_cmds(root):
    (root/"R12-APPLY-OWNER-PROBE.cmd").write_text(r'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "tools\reconstruct_source_r12.py" --project-root "%CD%" --apply
if errorlevel 1 (pause&exit /b 1)
echo.
echo R12 probe aplicado. Abra o jogo normalmente.
echo Em OUTRO CMD execute R12-WATCH-OWNER-PROBE.cmd
pause
''',encoding="utf-8")
    (root/"R12-WATCH-OWNER-PROBE.cmd").write_text(r'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "tools\reconstruct_source_r12.py" --project-root "%CD%" --watch
pause
''',encoding="utf-8")
    (root/"R12-REVERT-OWNER-PROBE.cmd").write_text(r'''@echo off
setlocal
cd /d "%~dp0"
py.exe -3 -u "tools\reconstruct_source_r12.py" --project-root "%CD%" --revert
pause
''',encoding="utf-8")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    g=ap.add_mutually_exclusive_group()
    g.add_argument("--plan",action="store_true");g.add_argument("--apply",action="store_true")
    g.add_argument("--watch",action="store_true");g.add_argument("--revert",action="store_true")
    ns=ap.parse_args()
    if not(ns.plan or ns.apply or ns.watch or ns.revert):ns.plan=True

    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    out=root/"src-reconstructed"/"reverse"/"r12";out.mkdir(parents=True,exist_ok=True)
    state_path=out/"OWNER_RUNTIME_PROBE.json"
    backup=root/"_PACKAGE_PHASE5"/"AMS.exe.r12-owner-probe.bak"

    if ns.watch:
        return watch(root,state_path)
    if not ams.is_file():raise SystemExit("AMS.exe nao encontrado")

    if ns.revert:
        if backup.is_file():
            shutil.copy2(backup,ams)
            print("[R12] Probe revertido usando backup.")
            print("SHA:",sha(ams.read_bytes()));return
        if not state_path.is_file():raise SystemExit("R12 state/backup nao encontrado")
        st=json.loads(state_path.read_text(encoding="utf-8"))
        d=bytearray(ams.read_bytes())
        pf=int(st["patch_file"],16);cf=int(st["cave_file"],16)
        orig=bytes.fromhex(st["patch_original"]);cave_orig=bytes.fromhex(st["cave_original"])
        d[pf:pf+len(orig)]=orig;d[cf:cf+len(cave_orig)]=cave_orig
        ams.write_bytes(d);print("[R12] Revertido por state.");print("SHA:",sha(d));return

    d=bytearray(ams.read_bytes());cur=sha(d)
    if cur!=EXPECTED_SHA:
        if ns.apply and state_path.is_file():
            st=json.loads(state_path.read_text(encoding="utf-8"))
            if cur==st.get("patched_sha256"):
                print("[R12] Probe ja aplicado.");return
        raise SystemExit("AMS SHA inesperado: "+cur+" (reverta R10/R11 antes)")
    if bytes(d[PATCH_FILE:PATCH_FILE+5])!=PATCH_ORIGINAL:
        raise SystemExit("guard patch site falhou: "+bytes(d[PATCH_FILE:PATCH_FILE+5]).hex(" ").upper())

    ib,dll_chars,secs=parse_pe(d)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    probe0,data0,_=build_probe(PATCH_VA)
    need=len(probe0)
    refs=code_references(md,d,ib,secs)
    caves=find_caves(d,ib,secs,refs,need)
    if not caves:raise SystemExit(f"nenhum cave seguro >= {need} bytes")
    cave=caves[0]
    probe,data_off,offsets=build_probe(cave["va"])
    pbytes=patch_bytes(cave["va"])
    cave_orig=bytes(d[cave["file"]:cave["file"]+len(probe)])
    probe_va=cave["va"]+data_off
    probe_rva=probe_va-ib

    state={
      "phase":"R12","mode":"RUNTIME_OWNER_PROBE",
      "base_sha256":cur,"image_base":f"0x{ib:08X}",
      "dll_characteristics":f"0x{dll_chars:04X}",
      "dynamic_base_enabled":bool(dll_chars&0x40),
      "patch_file":f"0x{PATCH_FILE:08X}","patch_va":f"0x{PATCH_VA:08X}",
      "patch_original":PATCH_ORIGINAL.hex(" ").upper(),"patch_new":pbytes.hex(" ").upper(),
      "cave_file":f"0x{cave['file']:08X}","cave_va":f"0x{cave['va']:08X}",
      "cave_length":cave["length"],"cave_tier":cave["tier"],"stub_and_data_length":len(probe),
      "probe_data_offset":data_off,"probe_va":f"0x{probe_va:08X}","probe_rva":f"0x{probe_rva:08X}",
      "probe_fields":{name:f"0x{probe_va+(offsets[name]-data_off):08X}" for name in PROBE_NAMES},
      "cave_original":cave_orig.hex(" ").upper(),"probe_bytes":probe.hex(" ").upper(),
      "captures":["callback click_count","GBBW this","GBBW+0x44 buildSignal","GBBW+0x04 owner","GBBW+0x08 owner control","owner runtime vtable"],
      "behavior":"replays original build callback exactly after capture; no BuildCar fallback",
      "applied":False
    }

    if ns.plan:
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8");write_cmds(root)
        print("[R12 PLAN] READY")
        print("DynamicBase/ASLR:",state["dynamic_base_enabled"])
        print("Cave file=0x%08X VA=0x%08X len=%d probe=%d tier=%d"%(cave["file"],cave["va"],cave["length"],len(probe),cave["tier"]))
        print("Probe data VA:",state["probe_va"],"RVA:",state["probe_rva"])
        print("Generated APPLY / WATCH / REVERT commands.")
        print("NO gameplay behavior changed.");return

    if ns.apply:
        if not backup.exists():shutil.copy2(ams,backup)
        d[PATCH_FILE:PATCH_FILE+5]=pbytes
        d[cave["file"]:cave["file"]+len(probe)]=probe
        ams.write_bytes(d);patched=sha(d)
        state["applied"]=True;state["patched_sha256"]=patched
        state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
        print("[R12 APPLY] OWNER PROBE APPLIED")
        print("Patched SHA:",patched)
        print("Agora abra o jogo e rode R12-WATCH-OWNER-PROBE.cmd em outro CMD.")

if __name__=="__main__":main()
