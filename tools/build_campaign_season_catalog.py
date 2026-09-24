#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC=0x53435852
VERSION=1
MAX_SEASONS=64
MAX_EVENTS=32
HEADER=struct.Struct("<4I")
ENTRY=struct.Struct("<iiII32i")
EVENT_HEADER=struct.Struct("<4I")
EVENT_ENTRY=struct.Struct("<10i")
EVENT_MAGIC=0x45435852
EVENT_MAX=512

class SeasonError(RuntimeError): pass

def fnv1a(data: bytes)->int:
    h=2166136261
    for b in data:
        h^=b;h=(h*16777619)&0xFFFFFFFF
    return h

def integer(v,name:str,default=0)->int:
    if v is None:return default
    if isinstance(v,bool):raise SeasonError(f"{name}: bool is not integer")
    try:x=int(v)
    except (TypeError,ValueError) as exc:raise SeasonError(f"{name}: invalid integer") from exc
    if x< -0x80000000 or x>0x7FFFFFFF:raise SeasonError(f"{name}: out of i32 range")
    return x

def load_event_ids(path:Path|None)->set[int]|None:
    if path is None:return None
    raw=path.read_bytes()
    expected=EVENT_HEADER.size+EVENT_ENTRY.size*EVENT_MAX+4
    if len(raw)!=expected:raise SeasonError(f"CampaignEvents.dat: unexpected size {len(raw)}")
    magic,version,count,_=EVENT_HEADER.unpack_from(raw,0)
    if magic!=EVENT_MAGIC or version!=1 or count>EVENT_MAX:raise SeasonError("CampaignEvents.dat: invalid header")
    if struct.unpack_from("<I",raw,len(raw)-4)[0]!=fnv1a(raw[:-4]):raise SeasonError("CampaignEvents.dat: checksum mismatch")
    ids:set[int]=set();off=EVENT_HEADER.size
    for i in range(count):
        event_id=EVENT_ENTRY.unpack_from(raw,off+i*EVENT_ENTRY.size)[0]
        if event_id<=0 or event_id in ids:raise SeasonError("CampaignEvents.dat: invalid event ids")
        ids.add(event_id)
    return ids

def load_source(path:Path)->list[dict]:
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("format")!="rextreme-campaign-seasons":raise SeasonError("invalid format")
    if data.get("version")!=VERSION:raise SeasonError("unsupported version")
    rows=data.get("seasons")
    if not isinstance(rows,list) or len(rows)>MAX_SEASONS:raise SeasonError("seasons must be array <=64")
    return rows

def normalize(rows:list[dict],event_ids:set[int]|None)->list[tuple]:
    if rows and event_ids is None:raise SeasonError("non-empty Season catalog requires --event-catalog")
    out=[];seen:set[int]=set()
    for raw in rows:
        if not isinstance(raw,dict):raise SeasonError("season must be object")
        sid=integer(raw.get("id"),"id")
        if sid<=0 or sid in seen:raise SeasonError(f"invalid/duplicate season id {sid}")
        seen.add(sid)
        required=integer(raw.get("required_node_id",0),f"{sid}.required_node_id")
        flags=integer(raw.get("flags",0),f"{sid}.flags")
        if required<0 or flags<0:raise SeasonError(f"{sid}: required_node_id/flags invalid")
        events=raw.get("events")
        if not isinstance(events,list) or not events or len(events)>MAX_EVENTS:
            raise SeasonError(f"{sid}: events must contain 1..{MAX_EVENTS} ids")
        local:set[int]=set();ids=[]
        for i,v in enumerate(events):
            eid=integer(v,f"{sid}.events[{i}]")
            if eid<=0 or eid in local:raise SeasonError(f"{sid}: invalid/duplicate event {eid}")
            if event_ids is not None and eid not in event_ids:raise SeasonError(f"{sid}: event {eid} missing from CampaignEvents.dat")
            local.add(eid);ids.append(eid)
        ids += [0]*(MAX_EVENTS-len(ids))
        out.append((sid,required,len(events),flags,*ids))
    out.sort(key=lambda row:row[0])
    return out

def build(source:Path,output:Path,event_catalog:Path|None=None,report:Path|None=None)->dict:
    rows=normalize(load_source(source),load_event_ids(event_catalog))
    payload=bytearray(HEADER.pack(MAGIC,VERSION,len(rows),0))
    for row in rows:payload+=ENTRY.pack(*row)
    payload+=ENTRY.pack(*([0]*36))*(MAX_SEASONS-len(rows))
    payload+=struct.pack("<I",fnv1a(payload))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(payload)
    summary={
        "format":"rextreme-campaign-season-runtime-catalog","version":VERSION,
        "count":len(rows),"entry_size":ENTRY.size,"output":str(output),
        "validated_against_event_catalog":event_catalog is not None,
        "uses_existing_campaign_events_only":True,
        "online_backend_required":False,
        "ids":[r[0] for r in rows],
    }
    if report:
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary

def main()->int:
    ap=argparse.ArgumentParser(description="Build data-driven ReXtreme Career Season catalog")
    ap.add_argument("source",type=Path);ap.add_argument("output",type=Path)
    ap.add_argument("--event-catalog",type=Path);ap.add_argument("--report",type=Path)
    ns=ap.parse_args()
    try:r=build(ns.source,ns.output,ns.event_catalog,ns.report)
    except (OSError,json.JSONDecodeError,SeasonError,struct.error) as exc:
        print(f"ERROR: {exc}");return 1
    print(json.dumps(r,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
