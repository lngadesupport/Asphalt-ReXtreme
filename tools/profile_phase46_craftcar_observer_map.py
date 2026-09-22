#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_HASH = "22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
FINAL_VTABLE = 0x0184F6C0
TEMP_VTABLE  = 0x0184F41C

def u16(b,o): return struct.unpack_from("<H", b, o)[0]
def u32(b,o): return struct.unpack_from("<I", b, o)[0]
def i32(b,o): return struct.unpack_from("<i", b, o)[0]

def parse_pe(data: bytes):
    pe = u32(data, 0x3C)
    if data[pe:pe+4] != b"PE\0\0":
        raise RuntimeError("Invalid PE")
    machine = u16(data, pe+4)
    nsec = u16(data, pe+6)
    opt_size = u16(data, pe+20)
    opt = pe+24
    magic = u16(data, opt)
    if machine != 0x14C or magic != 0x10B:
        raise RuntimeError("Expected x86 PE32")
    image_base = u32(data, opt+28)
    sec_off = opt + opt_size
    secs=[]
    for i in range(nsec):
        o=sec_off+i*40
        name=data[o:o+8].split(b"\0",1)[0].decode("ascii","replace")
        vsize=u32(data,o+8); va=u32(data,o+12)
        raw_size=u32(data,o+16); raw=u32(data,o+20)
        chars=u32(data,o+36)
        secs.append(dict(name=name,vsize=vsize,va=va,raw_size=raw_size,raw=raw,chars=chars))
    return image_base, secs

def make_mappers(image_base, secs):
    def file_to_va(off:int):
        for s in secs:
            if s["raw"] <= off < s["raw"]+s["raw_size"]:
                return image_base+s["va"]+(off-s["raw"])
        return None
    def va_to_file(va:int):
        rva=va-image_base
        if rva < 0: return None
        for s in secs:
            span=max(s["vsize"],s["raw_size"])
            if s["va"] <= rva < s["va"]+span:
                return s["raw"]+(rva-s["va"])
        return None
    def is_exec_va(va:int):
        rva=va-image_base
        for s in secs:
            span=max(s["vsize"],s["raw_size"])
            if s["va"] <= rva < s["va"]+span:
                return bool(s["chars"] & 0x20000000)
        return False
    return file_to_va, va_to_file, is_exec_va

def hexdump(data:bytes, start:int, before=0, after=112):
    a=max(0,start-before); z=min(len(data),start+after)
    out=[]
    p=a
    while p<z:
        chunk=data[p:min(p+16,z)]
        out.append(f"0x{p:08X}: "+" ".join(f"{x:02X}" for x in chunk))
        p+=16
    return "\n".join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    args=ap.parse_args()
    root=Path(args.project_root).resolve()
    game=root/"_PACKAGE_PHASE5"
    ams=game/"AMS.exe"
    out_dir=game/"_PHASE46_BUILD_OBSERVER_MAP"
    out_dir.mkdir(parents=True,exist_ok=True)
    out=out_dir/"LATEST-PHASE46-BUILD-OBSERVER-MAP.txt"

    data=ams.read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    if sha != EXPECTED_HASH:
        raise SystemExit(f"Expected Phase36-only AMS hash {EXPECTED_HASH}, got {sha}")

    image_base, secs=parse_pe(data)
    file_to_va, va_to_file, is_exec_va=make_mappers(image_base,secs)

    exec_ranges=[]
    for s in secs:
        if s["chars"] & 0x20000000:
            a=s["raw"]; z=min(len(data),s["raw"]+s["raw_size"])
            exec_ranges.append((a,z))

    # Build direct CALL index once.
    call_index={}
    for a,z in exec_ranges:
        i=a
        end=max(a,z-5)
        while i<=end:
            if data[i]==0xE8:
                src=file_to_va(i)
                if src is not None:
                    dst=(src+5+i32(data,i+1)) & 0xFFFFFFFF
                    call_index.setdefault(dst,[]).append(i)
                i+=5
            else:
                i+=1

    def dword_refs(value:int):
        pat=struct.pack("<I",value)
        refs=[]
        pos=0
        while True:
            pos=data.find(pat,pos)
            if pos<0: break
            refs.append(pos); pos+=1
        return refs

    def in_exec(off:int):
        return any(a<=off<z for a,z in exec_ranges)

    lines=[]
    w=lines.append
    w("="*60)
    w(" ReXtreme Phase 46 - CraftCar Observer VTable Map (Python)")
    w("="*60)
    w(f"AMS_SHA256={sha}")
    w(f"ImageBase=0x{image_base:08X}")
    w(f"IndexedDirectCalls={sum(len(v) for v in call_index.values())}")
    w("")

    for label,vt in [("FINAL_OBSERVER_VTABLE",FINAL_VTABLE),("CTOR_TEMP_VTABLE",TEMP_VTABLE)]:
        off=va_to_file(vt)
        if off is None:
            w(f"===== {label} =====")
            w(f"VA 0x{vt:08X} not mapped")
            w("")
            continue
        w(f"===== {label} VA=0x{vt:08X} File=0x{off:08X} =====")
        for slot in range(24):
            eo=off+slot*4
            if eo+4>len(data): break
            fn=u32(data,eo)
            fo=va_to_file(fn)
            execflag=is_exec_va(fn)
            ftxt=f"0x{fo:08X}" if fo is not None else "N/A"
            w(f"slot={slot:2d} entryFile=0x{eo:08X} fnVA=0x{fn:08X} fnFile={ftxt} Exec={execflag}")
            if execflag and fo is not None:
                w(hexdump(data,fo,0,112))
                calls=call_index.get(fn,[])
                w(f"DirectCallers={len(calls)}")
                for c in calls[:20]:
                    cv=file_to_va(c)
                    w(f" callerFile=0x{c:08X} callerVA=0x{cv:08X}")
                    w(hexdump(data,c,24,48))
                # Scan first 128 bytes for +/-0x298 immediates.
                hi=min(len(data)-4,fo+128)
                for p in range(fo,hi):
                    val=i32(data,p)
                    if val in (0x298,-0x298):
                        w(f"  ** +/-0x298 immediate @ file=0x{p:08X}")
            w("")

    w("===== EXECUTABLE REFS TO FINAL OBSERVER VTABLE =====")
    for r in dword_refs(FINAL_VTABLE):
        if in_exec(r):
            rv=file_to_va(r)
            w(f"refFile=0x{r:08X} refVA=0x{rv:08X}")
            w(hexdump(data,r,48,96))
            w("")

    w("===== BUILD HANDLER REGISTRATION WINDOW =====")
    w(hexdump(data,0x006870D0,32,176))
    w("")

    out.write_text("\n".join(lines),encoding="utf-8")
    print("="*60)
    print(" PHASE 46 CRAFTCAR OBSERVER MAP READY (Python)")
    print("="*60)
    print(f"Indexed direct calls: {sum(len(v) for v in call_index.values())}")
    print(f"Report: {out}")

if __name__=="__main__":
    main()
