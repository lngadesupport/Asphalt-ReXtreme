#!/usr/bin/env python3
"""Decode Asphalt Xtreme 1.7.3.8 .xtea asset streams."""
from __future__ import annotations
import argparse, json, struct, sys, zipfile, zlib
from pathlib import Path

KEY_SOURCE = b"Unhandled field type (%d) in standard profile (%s)"

class DecodeError(RuntimeError): pass

def fold_key(source: bytes = KEY_SOURCE):
    key=bytearray(16)
    for i,b in enumerate(source): key[i & 0x0F] ^= b
    return struct.unpack("<4I",key)

def decrypt_block(block:bytes,key):
    v0,v1=struct.unpack("<2I",block); total=0xC6EF3720; delta=0x9E3779B9
    for _ in range(32):
        v1=(v1-((((v0<<4)&0xffffffff ^ (v0>>5))+v0)^((total+key[(total>>11)&3])&0xffffffff)))&0xffffffff
        total=(total-delta)&0xffffffff
        v0=(v0-((((v1<<4)&0xffffffff ^ (v1>>5))+v1)^((total+key[total&3])&0xffffffff)))&0xffffffff
    return struct.pack("<2I",v0,v1)

def decode_stream(raw:bytes):
    if len(raw)<2: raise DecodeError("stream shorter than type field")
    typ=struct.unpack_from("<H",raw,0)[0]
    if typ==0: return raw[2:],{"stream_type":0,"payload_size":len(raw)-2,"crc_ok":None}
    if typ!=1: raise DecodeError(f"unsupported stream type {typ}")
    enc=raw[2:]; dec=bytearray(enc); key=fold_key()
    for p in range(0,(len(enc)//8)*8,8): dec[p:p+8]=decrypt_block(enc[p:p+8],key)
    length,expected=struct.unpack_from("<II",dec,0)
    if length>len(dec)-8: raise DecodeError("declared length exceeds stream")
    payload=bytes(dec[8:8+length]); actual=zlib.crc32(payload)&0xffffffff
    if actual!=expected: raise DecodeError(f"CRC mismatch: {expected:08x} != {actual:08x}")
    return payload,{"stream_type":1,"payload_size":length,"crc32":f"{actual:08x}","crc_ok":True}

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    one=sub.add_parser("decode"); one.add_argument("input",type=Path); one.add_argument("output",type=Path)
    allp=sub.add_parser("extract-xmlbin"); allp.add_argument("xml_bin",type=Path); allp.add_argument("outdir",type=Path); allp.add_argument("--report",type=Path)
    a=ap.parse_args()
    try:
        if a.cmd=="decode":
            payload,meta=decode_stream(a.input.read_bytes()); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(payload); print(json.dumps(meta,indent=2))
        else:
            a.outdir.mkdir(parents=True,exist_ok=True); rows=[]; count=0
            with zipfile.ZipFile(a.xml_bin) as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    row={"entry":info.filename,"stored_size":info.file_size}
                    if info.filename.lower().endswith(".xtea"):
                        try:
                            payload,meta=decode_stream(z.read(info.filename))
                            dst=a.outdir/Path(info.filename).with_suffix(""); dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(payload)
                            row.update(meta); row["output"]=str(dst); count+=1
                        except DecodeError as exc: row["error"]=str(exc)
                    rows.append(row)
            report={"xml_bin":str(a.xml_bin),"entries":len(rows),"decoded_xtea":count,"files":rows}
            rp=a.report if a.report else a.outdir/"xtea-report.json"; rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
            print(f"Decoded XTEA entries: {count}")
    except (OSError,zipfile.BadZipFile,DecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
