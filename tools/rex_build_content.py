#!/usr/bin/env python3
from __future__ import annotations
import argparse, struct
from pathlib import Path

OLD_MAGIC=0x54435852
OLD_VERSION=1
OLD_MAX=256
OLD_HEADER=struct.Struct("<4I")
OLD_ENTRY=struct.Struct("<8i")
OLD_SIZE=OLD_HEADER.size + OLD_ENTRY.size*OLD_MAX + 4

NEW_MAGIC=0x31434552
NEW_VERSION=1
NEW_MAX=256
NEW_HEADER=struct.Struct("<4I")
NEW_ENTRY=struct.Struct("<4i")
NEW_SIZE=NEW_HEADER.size + NEW_ENTRY.size*NEW_MAX + 4

# New Campaign Edition acquisition model.
REX_FREE=1
REX_CREDITS=2
REX_TOKENS=3

def fnv1a(data:bytes)->int:
    h=2166136261
    for b in data:
        h^=b
        h=(h*16777619)&0xffffffff
    return h

def read_source(path:Path):
    data=path.read_bytes()
    if len(data)!=OLD_SIZE:
        raise ValueError(f"unexpected source catalog size {len(data)}")
    magic,version,count,_=OLD_HEADER.unpack_from(data,0)
    if magic!=OLD_MAGIC or version!=OLD_VERSION or count>OLD_MAX:
        raise ValueError("source catalog header invalid")
    stored=struct.unpack_from("<I",data,len(data)-4)[0]
    if fnv1a(data[:-4])!=stored:
        raise ValueError("source catalog checksum invalid")

    rows=[]
    off=OLD_HEADER.size
    for _ in range(count):
        car,kind,item,cost,unlock,class_id,flags,reserved=OLD_ENTRY.unpack_from(data,off)
        off+=OLD_ENTRY.size
        if car<=0:
            raise ValueError("invalid source car id")

        # Data migration only. No legacy runtime behavior survives.
        # The first owned vehicle is free in RexState regardless of this mode.
        if kind==4:
            mode=REX_FREE
            price=0
        elif kind==2:
            mode=REX_CREDITS
            price=max(0,cost)
        elif kind==3:
            mode=REX_TOKENS
            price=max(0,cost)
        else:
            # Blueprint economy will be authored natively in the new content
            # schema later. Until then, preserve availability without invoking
            # any previous gameplay/service flow.
            mode=REX_FREE
            price=0

        rows.append((car,mode,price,class_id))

    rows.sort(key=lambda r:r[0])
    return rows

def build(rows):
    if not rows or len(rows)>NEW_MAX:
        raise ValueError("new content needs 1..256 cars")

    out=bytearray()
    out+=NEW_HEADER.pack(NEW_MAGIC,NEW_VERSION,len(rows),0)
    for row in rows:
        out+=NEW_ENTRY.pack(*row)
    for _ in range(NEW_MAX-len(rows)):
        out+=NEW_ENTRY.pack(0,0,0,0)
    out+=struct.pack("<I",fnv1a(out))
    if len(out)!=NEW_SIZE:
        raise AssertionError((len(out),NEW_SIZE))
    return bytes(out)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ns=ap.parse_args()

    rows=read_source(ns.source)
    data=build(rows)
    ns.output.parent.mkdir(parents=True,exist_ok=True)
    ns.output.write_bytes(data)
    print(f"[OK] CampaignContentV1.dat: {len(rows)} cars, {len(data)} bytes")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
