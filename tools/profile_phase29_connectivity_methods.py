import sys, struct, hashlib, pathlib

root = pathlib.Path(sys.argv[1]).resolve()
game = root / "_PACKAGE_PHASE5"
ams = game / "AMS.exe"
outdir = game / "_PHASE29_CONNECTIVITY_METHODS"
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / "LATEST-PHASE29-CONNECTIVITY-METHODS.txt"

data = ams.read_bytes()
sha = hashlib.sha256(data).hexdigest()

def u16(o): return struct.unpack_from("<H", data, o)[0]
def u32(o): return struct.unpack_from("<I", data, o)[0]
def i32(o): return struct.unpack_from("<i", data, o)[0]

pe = u32(0x3C)
if u32(pe) != 0x4550:
    raise SystemExit("Invalid PE")
machine = u16(pe+4)
nsec = u16(pe+6)
opt_size = u16(pe+20)
magic = u16(pe+24)
if machine != 0x14C or magic != 0x10B:
    raise SystemExit("Expected x86 PE32")
image_base = u32(pe+24+28)
sec_off = pe+24+opt_size
sections=[]
for i in range(nsec):
    o=sec_off+40*i
    name=data[o:o+8].split(b"\0",1)[0].decode("ascii","replace")
    vsize=u32(o+8); va=u32(o+12); rawsize=u32(o+16); raw=u32(o+20); chars=u32(o+36)
    sections.append((name,vsize,va,rawsize,raw,chars))

def file_to_rva(off):
    for name,vsize,va,rawsize,raw,chars in sections:
        if raw <= off < raw+rawsize:
            return va+(off-raw)
    return None
def file_to_va(off):
    r=file_to_rva(off)
    return None if r is None else image_base+r
def va_to_file(va):
    if va < image_base: return None
    rva=va-image_base
    for name,vsize,sva,rawsize,raw,chars in sections:
        span=max(vsize,rawsize)
        if sva <= rva < sva+span:
            return raw+(rva-sva)
    return None
def sec_name(off):
    for name,vsize,va,rawsize,raw,chars in sections:
        if raw <= off < raw+rawsize:
            return name
    return "?"
def is_exec(off):
    for name,vsize,va,rawsize,raw,chars in sections:
        if raw <= off < raw+rawsize:
            return bool(chars & 0x20000000)
    return False
def nearest_prologue(off, back=0x1000):
    lo=max(0,off-back)
    for p in range(off,lo+1,-1):
        if data[p:p+3] == b"\x55\x8B\xEC":
            return p
    return None
def hexdump(center,before=64,after=192):
    a=max(0,center-before); b=min(len(data),center+after)
    lines=[]
    for o in range(a,b,16):
        chunk=data[o:min(o+16,b)]
        lines.append(f"0x{o:08X}: "+" ".join(f"{x:02X}" for x in chunk))
    return "\n".join(lines)
def direct_calls_to(target_off):
    tva=file_to_va(target_off)
    if tva is None: return []
    res=[]
    for name,vsize,va,rawsize,raw,chars in sections:
        if not (chars & 0x20000000): continue
        end=min(len(data),raw+rawsize)
        o=raw
        while o+5<=end:
            if data[o]==0xE8:
                sva=file_to_va(o)
                if sva is not None:
                    dest=sva+5+i32(o+1)
                    if dest==tva:
                        res.append((o,nearest_prologue(o)))
            o+=1
    return res
def scan_func_calls(start,maxlen=0x500):
    res=[]
    end=min(len(data)-5,start+maxlen)
    for o in range(start,end):
        if data[o]!=0xE8: continue
        sva=file_to_va(o)
        if sva is None: continue
        dest=sva+5+i32(o+1)
        fo=va_to_file(dest)
        if fo is not None:
            res.append((o,fo))
    return res
def find_disp32_uses(start,maxlen,disp):
    pat=struct.pack("<I",disp)
    end=min(len(data),start+maxlen)
    out=[]
    for o in range(start,end-4):
        if data[o:o+4]==pat:
            out.append(o)
    return out

targets = [
    ("ctor-vftable-init-region",0x008743E0),
    ("vmethod-primary-0",0x008962B0),
    ("vmethod-secondary-0",0x009C9240),
    ("vmethod-secondary-1",0x0098CF80),
]
known = {
    0x00B989D0:"WinRT wrapper A",
    0x00B9A100:"WinRT wrapper B",
    0x00D2DEA0:"WinRT wrapper C",
    0x00D2E320:"WinRT InternetAccess predicate",
    0x00E07C40:"WinRT wrapper D",
    0x00E0E490:"WinRT parent",
    0x00BACDD0:"global IsOnline",
}

lines=[]
A=lines.append
A("="*60)
A(" ReXtreme Phase 29 - Connectivity Tracker Methods")
A("="*60)
A(f"AMS_SHA256={sha}")
A(f"ImageBase=0x{image_base:08X}")
A("")

# Discover exact constructor prologue around vftable write at 0x00874418.
ctor_ref=0x00874418
ctor=nearest_prologue(ctor_ref,0x800)
if ctor is not None:
    targets[0]=("AVAsphaltConnectivityTracker-constructor",ctor)

for name,off in targets:
    A(f"===== {name} file=0x{off:08X} VA=0x{file_to_va(off):08X} =====")
    A(hexdump(off,48,320))
    A("")
    calls=direct_calls_to(off)
    A(f"DirectCallers={len(calls)}")
    for call,pro in calls:
        ptxt="N/A" if pro is None else f"0x{pro:08X}"
        A(f"CALL file=0x{call:08X} callerPrologue={ptxt}")
    A("")
    subcalls=scan_func_calls(off,0x500)
    A(f"Rel32CallsWithin500={len(subcalls)}")
    for call,dest in subcalls:
        tag=known.get(dest,"")
        if tag:
            tag=" *** "+tag
        A(f" call@0x{call:08X} -> file=0x{dest:08X}{tag}")
    A("")
    for disp in (0xB8,0xC0,0xC4,0xC8,0xD0,0xD4,0xD8,0xDC):
        uses=find_disp32_uses(off,0x500,disp)
        if uses:
            A(f"disp32 +0x{disp:02X} byte-pattern uses: "+", ".join(f"0x{x:08X}" for x in uses))
    A("")

# Search executable code for direct references to the two known vftables.
A("===== VFTABLE IMMEDIATE REFERENCES =====")
for vfva,label in ((0x0185FF40,"primary"),(0x0185FF48,"secondary")):
    pat=struct.pack("<I",vfva)
    refs=[]
    for i in range(0,len(data)-4):
        if data[i:i+4]==pat and is_exec(i):
            refs.append(i)
    A(f"{label} vftable VA=0x{vfva:08X} executable immediate refs={len(refs)}")
    for r in refs:
        pro=nearest_prologue(r)
        A(f" ref=0x{r:08X} prologue={'N/A' if pro is None else f'0x{pro:08X}'}")
    A("")

# Identify all functions that access the same object-state offsets near known ctor/method areas.
A("===== CONNECTIVITY STATE OFFSET CANDIDATES =====")
for disp in (0xB8,0xC0,0xC4,0xC8,0xD0,0xD4,0xD8,0xDC):
    pat=struct.pack("<I",disp)
    refs=[]
    for i in range(0,len(data)-4):
        if data[i:i+4]==pat and is_exec(i):
            pro=nearest_prologue(i,0x500)
            if pro is not None:
                refs.append((i,pro))
    uniq={}
    for r,p in refs:
        uniq.setdefault(p,[]).append(r)
    A(f"+0x{disp:02X}: functions={len(uniq)} refs={len(refs)}")
    # Prioritize functions near known connectivity areas or that call known connectivity funcs.
    scored=[]
    for p,rs in uniq.items():
        sub=scan_func_calls(p,0x400)
        tags=[known[d] for _,d in sub if d in known]
        near=min(abs(p-t[1]) for t in targets)
        score=(10 if tags else 0)+(5 if near<0x20000 else 0)
        if score:
            scored.append((score,p,rs,tags))
    for score,p,rs,tags in sorted(scored,reverse=True)[:24]:
        A(f"  func=0x{p:08X} refs={','.join(f'0x{x:08X}' for x in rs[:8])} tags={';'.join(tags) if tags else '-'}")
    A("")

out.write_text("\n".join(lines),encoding="utf-8-sig")
print("="*60)
print(" PHASE 29 CONNECTIVITY METHODS READY")
print("="*60)
print(out)
