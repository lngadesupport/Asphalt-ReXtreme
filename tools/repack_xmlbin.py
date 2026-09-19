#!/usr/bin/env python3
"""Rebuild data/xml.bin with exact-size type-0 plaintext replacements."""
from __future__ import annotations
import argparse, json, shutil, struct, sys, tempfile, zipfile
from dataclasses import dataclass
from pathlib import Path

class RepackError(RuntimeError): pass

@dataclass(frozen=True)
class HeaderEntry:
    name: str
    data_offset: int
    compressed_size: int
    uncompressed_size: int
    method: int

def parse_hdr(path: Path) -> list[HeaderEntry]:
    data=path.read_bytes(); pos=0
    if len(data)<4: raise RepackError("xml.bin.hdr is too small")
    count=struct.unpack_from("<I",data,pos)[0]; pos+=4
    out=[]
    for idx in range(count):
        if pos+4>len(data): raise RepackError(f"truncated hdr before entry {idx}")
        n=struct.unpack_from("<I",data,pos)[0]; pos+=4
        if pos+n+18>len(data): raise RepackError(f"truncated hdr at entry {idx}")
        name=data[pos:pos+n].decode("utf-8"); pos+=n
        off=struct.unpack_from("<Q",data,pos)[0]; pos+=8
        cs,us=struct.unpack_from("<II",data,pos); pos+=8
        method=struct.unpack_from("<H",data,pos)[0]; pos+=2
        out.append(HeaderEntry(name,off,cs,us,method))
    if pos!=len(data): raise RepackError(f"hdr has {len(data)-pos} trailing bytes")
    return out

def data_offset(info: zipfile.ZipInfo)->int:
    return info.header_offset+30+len(info.filename.encode("utf-8"))+len(info.extra)

def clone_info(src: zipfile.ZipInfo)->zipfile.ZipInfo:
    dst=zipfile.ZipInfo(src.filename,date_time=src.date_time)
    dst.compress_type=zipfile.ZIP_STORED
    for attr in ("comment","extra","create_system","create_version","extract_version",
                 "flag_bits","volume","internal_attr","external_attr"):
        setattr(dst,attr,getattr(src,attr))
    return dst

def normalize_plain(path: Path)->bytes:
    b=path.read_bytes()
    if b.startswith(b"\xef\xbb\xbf"): b=b[3:]
    return b.rstrip(b"\x00")

def type0(plain: bytes,target:int)->bytes:
    if len(plain)+2>target:
        raise RepackError(f"plaintext needs {len(plain)+2} bytes; entry has {target}")
    return b"\x00\x00"+plain+b" "*(target-2-len(plain))

def replacements(items:list[str])->dict[str,Path]:
    out={}
    for raw in items:
        if "=" not in raw: raise RepackError(f"use ENTRY=FILE: {raw}")
        entry,file=raw.split("=",1)
        entry=entry.replace("\\","/").strip()
        if not entry.startswith("xml/"): entry="xml/"+entry
        if not entry.endswith(".xtea"): entry+=".xtea"
        p=Path(file).expanduser().resolve()
        if not p.is_file(): raise RepackError(f"file not found: {p}")
        out[entry]=p
    return out

def verify(path:Path,hdr:list[HeaderEntry])->list[str]:
    probs=[]; hm={e.name:e for e in hdr}
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())!=len(hdr): probs.append(f"count ZIP={len(z.infolist())} HDR={len(hdr)}")
        for i in z.infolist():
            h=hm.get(i.filename)
            if not h: probs.append(f"not in hdr: {i.filename}"); continue
            if data_offset(i)!=h.data_offset: probs.append(f"{i.filename}: offset {data_offset(i)} != {h.data_offset}")
            if i.compress_size!=h.compressed_size: probs.append(f"{i.filename}: compressed size mismatch")
            if i.file_size!=h.uncompressed_size: probs.append(f"{i.filename}: uncompressed size mismatch")
            if i.compress_type!=h.method: probs.append(f"{i.filename}: method mismatch")
    return probs

def rebuild(src:Path,dst:Path,repl:dict[str,Path])->dict:
    report={"original":str(src),"replacements":[]}
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst,"w",compression=zipfile.ZIP_STORED,allowZip64=True) as zout:
        unknown=set(repl)-set(zin.namelist())
        if unknown: raise RepackError("entries missing: "+", ".join(sorted(unknown)))
        for info in zin.infolist():
            old=zin.read(info.filename); new=old
            if info.filename in repl:
                plain=normalize_plain(repl[info.filename])
                new=type0(plain,len(old))
                report["replacements"].append({
                    "entry":info.filename,"source":str(repl[info.filename]),
                    "entry_size":len(old),"plaintext_size":len(plain),
                    "padding":len(old)-2-len(plain),"stream_type":0})
            zout.writestr(clone_info(info),new)
    return report

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("xml_bin",type=Path)
    ap.add_argument("--hdr",type=Path,required=True)
    ap.add_argument("--replace",action="append",default=[],metavar="ENTRY=FILE")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--report",type=Path)
    ap.add_argument("--in-place",action="store_true")
    a=ap.parse_args()
    src=a.xml_bin.resolve(); hdrp=a.hdr.resolve()
    try:
        hdr=parse_hdr(hdrp)
        probs=verify(src,hdr)
        if probs: raise RepackError("original does not match hdr:\n"+"\n".join(probs))
        repl=replacements(a.replace)
        out=(a.output.resolve() if a.output else src.with_name(src.name+".rex"))
        if out==src and not a.in_place: raise RepackError("refusing overwrite without --in-place")
        out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="rextreme-",suffix=".tmp",dir=out.parent,delete=False) as f:
            tmp=Path(f.name)
        try:
            report=rebuild(src,tmp,repl)
            probs=verify(tmp,hdr)
            report["original_size"]=src.stat().st_size
            report["rebuilt_size"]=tmp.stat().st_size
            report["layout_problems"]=probs
            report["hdr_unchanged_compatible"]=not probs and src.stat().st_size==tmp.stat().st_size
            if not report["hdr_unchanged_compatible"]:
                raise RepackError("rebuilt archive changed HDR layout")
            final=src if a.in_place else out
            backup=None
            if a.in_place:
                backup=src.with_suffix(src.suffix+".rex.bak")
                if not backup.exists(): shutil.copy2(src,backup)
            shutil.move(str(tmp),str(final))
            report["final_output"]=str(final); report["backup"]=str(backup) if backup else None
            rp=a.report.resolve() if a.report else final.with_suffix(final.suffix+".report.json")
            rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
            print(f"OK: {final}")
            print(f"HDR-compatible layout: yes ({len(hdr)} entries)")
            print(f"Report: {rp}")
        finally:
            if tmp.exists(): tmp.unlink()
    except (RepackError,OSError,zipfile.BadZipFile,struct.error) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 1
    return 0

if __name__=="__main__": raise SystemExit(main())
