#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, struct
from pathlib import Path

MAGIC=0x47415852
VERSION=1
MAX=128
HEADER=struct.Struct("<4I")
ENTRY=struct.Struct("<i7I")
CHECK=struct.Struct("<I")
METRICS={
"races":1,"wins":2,"podiums":3,"best_placement":4,"best_finish_time_ms":5,
"drift_meters":6,"air_time_ms":7,"nitro_time_ms":8,"wrecked_cars":9,
"wrecked_environment":10,"wrecks_made":11,"flat_spins":12,"barrel_rolls":13,
"obstacles_broken":14,"nitro_all_in":15,"nitro_chain":16,"nitro_normal":17}
COMPARE={"le":1,"ge":2,"eq":3}

class AchievementError(RuntimeError): pass

def fnv(data:bytes)->int:
 h=2166136261
 for b in data:h=((h^b)*16777619)&0xffffffff
 return h

def u32(v,name):
 if isinstance(v,bool) or not isinstance(v,int) or v<0 or v>0xffffffff:
  raise AchievementError(f"{name} must be uint32")
 return v

def normalize(raw,seen):
 if not isinstance(raw,dict):raise AchievementError("achievement must be object")
 ident=raw.get("id")
 if isinstance(ident,bool) or not isinstance(ident,int) or ident<=0 or ident>0x7fffffff:
  raise AchievementError("achievement id must be positive int32")
 if ident in seen:raise AchievementError(f"duplicate achievement id: {ident}")
 seen.add(ident)
 metric=raw.get("metric")
 compare=raw.get("compare")
 if metric not in METRICS:raise AchievementError(f"{ident}: invalid metric {metric!r}")
 if compare not in COMPARE:raise AchievementError(f"{ident}: invalid compare {compare!r}")
 threshold=u32(raw.get("threshold"),f"{ident}.threshold")
 flags=u32(raw.get("flags",0),f"{ident}.flags")
 return (ident,METRICS[metric],COMPARE[compare],threshold,flags,0,0,0)

def build(source:Path,output:Path,report:Path|None=None):
 data=json.loads(source.read_text(encoding="utf-8"))
 if data.get("format")!="rextreme-campaign-achievements":raise AchievementError("invalid format")
 if data.get("version")!=VERSION:raise AchievementError("unsupported version")
 rows=data.get("achievements")
 if not isinstance(rows,list) or len(rows)>MAX:raise AchievementError("achievements must be array <=128")
 seen=set(); packed=[normalize(x,seen) for x in rows];packed.sort(key=lambda x:x[0])
 body=bytearray(HEADER.pack(MAGIC,VERSION,len(packed),0))
 for row in packed:body+=ENTRY.pack(*row)
 body+=b"\0"*((MAX-len(packed))*ENTRY.size)
 body+=CHECK.pack(fnv(body))
 output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(body)
 result={"format":"rextreme-campaign-achievement-catalog","version":VERSION,
 "count":len(packed),"entry_size":ENTRY.size,"file_size":len(body),
 "ids":[x[0] for x in packed],"output":str(output)}
 if report:
  report.parent.mkdir(parents=True,exist_ok=True)
  report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 return result

def main():
 ap=argparse.ArgumentParser(description="Build ReXtreme permanent achievement catalog")
 ap.add_argument("source",type=Path);ap.add_argument("output",type=Path);ap.add_argument("--report",type=Path)
 ns=ap.parse_args()
 try:r=build(ns.source,ns.output,ns.report)
 except (OSError,json.JSONDecodeError,AchievementError,struct.error) as e:
  print(f"ERROR: {e}");return 1
 print(json.dumps(r,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
