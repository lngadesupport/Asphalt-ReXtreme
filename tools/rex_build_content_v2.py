#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, struct
from pathlib import Path

MAGIC=0x32434552  # REC2
VERSION=2
MAX_CARS=256
HEADER=struct.Struct("<6I")
ENTRY=struct.Struct("<4i")
SIZE=HEADER.size + ENTRY.size*MAX_CARS + 4

MODE={
    "free":1,
    "credits":2,
    "tokens":3,
}

def fnv1a(data:bytes)->int:
    h=2166136261
    for b in data:
        h^=b
        h=(h*16777619)&0xffffffff
    return h

def load_manifest(path:Path):
    obj=json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema")!=2:
        raise ValueError("expected Rex content manifest schema 2")
    eco=obj.get("economy") or {}
    garage=obj.get("garage") or {}
    starter=int(garage.get("starter_car_id",0))
    rows=[]
    seen=set()
    for item in garage.get("cars") or []:
        car=int(item["car_id"])
        if car<=0 or car in seen:
            raise ValueError(f"invalid/duplicate car_id {car}")
        seen.add(car)
        mode_name=str(item["acquire_mode"]).lower()
        if mode_name not in MODE:
            raise ValueError(f"unknown acquire_mode {mode_name}")
        price=int(item.get("price",0))
        cls=int(item.get("class_id",0))
        if price<0:
            raise ValueError("negative price")
        rows.append((car,MODE[mode_name],price,cls))
    rows.sort(key=lambda x:x[0])
    if not rows or len(rows)>MAX_CARS:
        raise ValueError("content must define 1..256 cars")
    if starter not in seen:
        raise ValueError("starter_car_id must exist in cars")
    return {
        "starter":starter,
        "credits":int(eco.get("starting_credits",50000)),
        "tokens":int(eco.get("starting_tokens",0)),
        "rows":rows,
    }

def build(cfg)->bytes:
    out=bytearray()
    out+=HEADER.pack(
        MAGIC,VERSION,len(cfg["rows"]),cfg["starter"],
        cfg["credits"],cfg["tokens"]
    )
    for row in cfg["rows"]:
        out+=ENTRY.pack(*row)
    for _ in range(MAX_CARS-len(cfg["rows"])):
        out+=ENTRY.pack(0,0,0,0)
    out+=struct.pack("<I",fnv1a(out))
    if len(out)!=SIZE:
        raise AssertionError((len(out),SIZE))
    return bytes(out)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ns=ap.parse_args()
    cfg=load_manifest(ns.manifest)
    data=build(cfg)
    ns.output.parent.mkdir(parents=True,exist_ok=True)
    ns.output.write_bytes(data)
    print(
        f"[OK] CampaignContentV2.dat: {len(cfg['rows'])} cars, "
        f"starter={cfg['starter']}, {len(data)} bytes"
    )
    return 0

if __name__=="__main__":
    raise SystemExit(main())
