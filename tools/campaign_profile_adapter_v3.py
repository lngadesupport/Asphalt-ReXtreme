#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

PATCHES=(
 ("local profile validation path 1",0x0069B8C6,bytes.fromhex("74 24"),bytes.fromhex("74 22")),
 ("local profile validation path 2",0x0069B8E6,bytes.fromhex("32 C0"),bytes.fromhex("B0 01")),
 ("startup remote-profile sync gate",0x0092B82A,
  bytes.fromhex("0F 84 8D 01 00 00"),bytes.fromhex("E9 8E 01 00 00 90")),
)

def h(b): return hashlib.sha256(b).hexdigest()
def fmt(b): return " ".join(f"{x:02X}" for x in b)

def apply_bytes(d:bytearray):
    if bytes(d[ONLINE_OFF:ONLINE_OFF+7]) != ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")
    changes=[]
    for label,off,before,after in PATCHES:
        cur=bytes(d[off:off+len(before)])
        if cur==after:
            changes.append({"label":label,"offset":f"0x{off:08X}","status":"already-patched"})
            continue
        if cur!=before:
            raise RuntimeError(f"{label}: unknown bytes at 0x{off:08X}: {fmt(cur)}")
        d[off:off+len(before)]=after
        changes.append({"label":label,"offset":f"0x{off:08X}","status":"patched"})
    return changes

def apply(root:Path):
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    raw=ams.read_bytes(); before=h(raw); d=bytearray(raw)
    changes=apply_bytes(d)
    bdir=root/"_BACKUPS"/"CAMPAIGN-PROFILE-V3"
    bdir.mkdir(parents=True,exist_ok=True)
    bak=bdir/f"AMS.exe.{before}.bak"
    if not bak.exists(): shutil.copy2(ams,bak)
    tmp=ams.with_suffix(".profile-v3.tmp"); tmp.write_bytes(d); tmp.replace(ams)
    out=root/"_TRACE_MONTAR"; out.mkdir(parents=True,exist_ok=True)
    (out/"CAMPAIGN-PROFILE-V3.json").write_text(json.dumps({
      "phase":"Campaign Profile Adapter v3",
      "basis":"verified historical Phase9 native-profile path",
      "logical_connectivity":"offline/false",
      "startup_remote_profile_gate":"bypassed",
      "runtime_global_sync":"untouched",
      "garage_hooks":"not part of this adapter",
      "sha256_before":before,"sha256_after":h(ams.read_bytes()),
      "changes":changes
    },indent=2),encoding="utf-8")
    print("[OK] Campaign Profile Adapter v3 applied.")
    print("[PROFILE] Native local profile accepted.")
    print("[PROFILE] Startup remote-profile sync gate bypassed.")
    print("[PROFILE] Global IsOnline: FALSE")
    print("[PROFILE] Runtime GlobalSync: untouched")
    return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print("[ERRO]",e); return 1
if __name__=="__main__": raise SystemExit(main())
