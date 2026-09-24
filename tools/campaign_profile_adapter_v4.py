#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

ONLINE_OFF=0x00BACDD0
ONLINE_FALSE=bytes.fromhex("31 C0 C3 90 90 90 90")

PROFILE_PATCHES=(
 ("local profile validation path 1",0x0069B8C6,bytes.fromhex("74 24"),bytes.fromhex("74 22")),
 ("local profile validation path 2",0x0069B8E6,bytes.fromhex("32 C0"),bytes.fromhex("B0 01")),
 ("startup remote-profile sync gate",0x0092B82A,
  bytes.fromhex("0F 84 8D 01 00 00"),bytes.fromhex("E9 8E 01 00 00 90")),
)

OFFLINE_UI_PATCHES=(
 ("age/gender gate 1 -> local success",0x006A1CE1,
  bytes.fromhex("0F 85 FE 00 00 00"),bytes.fromhex("E9 FF 00 00 00 90")),
 ("age/gender gate 2 -> local success",0x006A1E03,
  bytes.fromhex("0F 85 D8 00 00 00"),bytes.fromhex("E9 D9 00 00 00 90")),

 ("NO_INTERNET callback 1 -> true epilogue",0x004FBCF0,
  bytes.fromhex("8B 8E AC 01 00"),bytes.fromhex("E9 09 FF FF FF")),
 ("NO_INTERNET callback 2 -> true epilogue",0x004FD6A5,
  bytes.fromhex("8B 8E B0 01 00"),bytes.fromhex("E9 E0 FF FF FF")),
 ("NO_INTERNET callback 3 -> true epilogue",0x0064A789,
  bytes.fromhex("8B 8E B8 01 00"),bytes.fromhex("E9 09 FF FF FF")),

 ("NO_INTERNET callback 1 sibling -> epilogue",0x004FBEC1,
  bytes.fromhex("8B 8E AC 01 00"),bytes.fromhex("E9 9A 00 00 00")),
 ("NO_INTERNET callback 2 sibling -> epilogue",0x004FD876,
  bytes.fromhex("8B 8E B0 01 00"),bytes.fromhex("E9 A7 00 00 00")),
 ("NO_INTERNET callback 3 sibling -> epilogue",0x0064A95A,
  bytes.fromhex("8B 8E B8 01 00"),bytes.fromhex("E9 9A 00 00 00")),

 ("NO_INTERNET title-only 04 -> continuation",0x00530935,
  bytes.fromhex("8B 0D 64 85 94"),bytes.fromhex("E9 AD 02 00 00")),
 ("NO_INTERNET title-only 05 -> continuation",0x006D62C5,
  bytes.fromhex("51 8B CC 68 88"),bytes.fromhex("E9 3A 06 00 00")),
 ("NO_INTERNET title-only 06 -> cleanup",0x00746EDB,
  bytes.fromhex("68 F0 60 53 01"),bytes.fromhex("E9 86 00 00 00")),
 ("NO_INTERNET title-only 07 -> cleanup",0x008DA2B4,
  bytes.fromhex("68 F0 60 53 01"),bytes.fromhex("E9 83 00 00 00")),
 ("NO_INTERNET title-only 08 lobby -> continuation",0x009171DC,
  bytes.fromhex("51 8B CC C6 45"),bytes.fromhex("E9 28 02 00 00")),
 ("NO_INTERNET title-only 09 -> continuation",0x0099D3F7,
  bytes.fromhex("51 8B CC 89 8D"),bytes.fromhex("E9 7A 04 00 00")),
 ("NO_INTERNET title-only 10 -> continuation",0x00A68023,
  bytes.fromhex("51 8B CC C6 45"),bytes.fromhex("E9 3B 02 00 00")),

 ("NO_INTERNET site 04 -> cleanup",0x00689741,
  bytes.fromhex("84 DB 0F 85 F5"),bytes.fromhex("E9 F8 01 00 00")),
 ("NO_INTERNET site 07 -> cleanup",0x006A46DC,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 D9 00 00 00")),
 ("NO_INTERNET site 08 -> cleanup",0x006A5EFC,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 D9 00 00 00")),
 ("NO_INTERNET site 09 -> cleanup",0x006A6BCC,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 D9 00 00 00")),
 ("NO_INTERNET site 10 -> cleanup",0x00809EB2,
  bytes.fromhex("51 8B C4 68 A8"),bytes.fromhex("E9 EC 00 00 00")),
 ("NO_INTERNET site 11 -> cleanup",0x008B5441,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 98 01 00 00")),
 ("NO_INTERNET site 12 -> cleanup",0x00B0CB4C,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 D9 00 00 00")),
 ("NO_INTERNET site 13 -> cleanup",0x00B24D61,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 98 01 00 00")),
 ("NO_INTERNET site 14 -> cleanup",0x00B44EA1,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 98 01 00 00")),
 ("NO_INTERNET site 15 -> cleanup",0x00B6A0A0,
  bytes.fromhex("C7 45 F0 00 00"),bytes.fromhex("E9 98 01 00 00")),
)

def sha(b): return hashlib.sha256(b).hexdigest()
def fmt(b): return " ".join(f"{x:02X}" for x in b)

def patch_set(d:bytearray, rows, changes):
    for label,off,before,after in rows:
        cur=bytes(d[off:off+len(before)])
        if cur==after:
            changes.append({"label":label,"offset":f"0x{off:08X}","status":"already-patched"})
            continue
        if cur!=before:
            raise RuntimeError(f"{label}: unknown bytes at 0x{off:08X}: {fmt(cur)}")
        d[off:off+len(before)]=after
        changes.append({"label":label,"offset":f"0x{off:08X}","status":"patched",
                        "before":fmt(before),"after":fmt(after)})

def apply_bytes(d:bytearray):
    if bytes(d[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)])!=ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")
    changes=[]
    patch_set(d,PROFILE_PATCHES,changes)
    patch_set(d,OFFLINE_UI_PATCHES,changes)
    return changes

def apply(root:Path):
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise FileNotFoundError(ams)
    raw=ams.read_bytes(); before=sha(raw); d=bytearray(raw)
    changes=apply_bytes(d)

    bdir=root/"_BACKUPS"/"CAMPAIGN-PROFILE-V4"
    bdir.mkdir(parents=True,exist_ok=True)
    bak=bdir/f"AMS.exe.{before}.bak"
    if not bak.exists(): shutil.copy2(ams,bak)

    tmp=ams.with_suffix(".profile-v4.tmp"); tmp.write_bytes(d)
    verify=tmp.read_bytes()
    if verify[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("verification failed: IsOnline")
    for label,off,_before,after in PROFILE_PATCHES+OFFLINE_UI_PATCHES:
        if verify[off:off+len(after)]!=after:
            raise RuntimeError(f"verification failed: {label}")
    tmp.replace(ams)

    out=root/"_TRACE_MONTAR"; out.mkdir(parents=True,exist_ok=True)
    report={
      "phase":"Campaign Profile/Offline UI Adapter v4",
      "basis":"working Profile v3 + verified Phase14 no-connection continuations",
      "logical_connectivity":"offline/false",
      "startup_remote_profile_gate":"bypassed",
      "runtime_global_sync":"untouched",
      "known_no_connection_routes_bypassed":len(OFFLINE_UI_PATCHES),
      "garage_hooks":"not part of this adapter",
      "sha256_before":before,"sha256_after":sha(ams.read_bytes()),
      "changes":changes
    }
    (out/"CAMPAIGN-PROFILE-V4.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("[OK] Campaign Profile/Offline UI Adapter v4 applied.")
    print("[PROFILE] Startup remote profile gate: RETIRED")
    print(f"[OFFLINE UI] Known connection-error routes bypassed: {len(OFFLINE_UI_PATCHES)}")
    print("[NETWORK] Global IsOnline: FALSE")
    print("[NETWORK] Runtime GlobalSync: untouched")
    print(f"[AMS] {report['sha256_after']}")
    return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print("[ERRO]",e); return 1
if __name__=="__main__": raise SystemExit(main())
