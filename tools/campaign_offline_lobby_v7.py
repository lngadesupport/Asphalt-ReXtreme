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
 ("age/gender gate 1 -> local success",0x006A1CE1,
  bytes.fromhex("0F 85 FE 00 00 00"),bytes.fromhex("E9 FF 00 00 00 90")),
 ("age/gender gate 2 -> local success",0x006A1E03,
  bytes.fromhex("0F 85 D8 00 00 00"),bytes.fromhex("E9 D9 00 00 00 90")),

 # Phase15 dispatcher: two status codes route directly to NO_INTERNET modal.
 # Redirect them to the existing handled/common epilogue at 0x00917409.
 ("lobby dispatcher error 0x0BC2 -> common epilogue",0x00916B30,
  bytes.fromhex("0F 84 F6 05 00 00"),bytes.fromhex("0F 84 D3 08 00 00")),
 ("lobby dispatcher error 0x0FAA -> common epilogue",0x00916B3C,
  bytes.fromhex("0F 84 EA 05 00 00"),bytes.fromhex("0F 84 C7 08 00 00")),

 # Also bypass the known late construction block itself.
 ("post-tutorial/lobby NO_INTERNET -> native common continuation",0x009171DC,
  bytes.fromhex("51 8B CC C6 45"),bytes.fromhex("E9 28 02 00 00")),
)

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def fmt(b:bytes)->str:return " ".join(f"{x:02X}" for x in b)

def apply(root:Path)->int:
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file(): raise FileNotFoundError(ams)
    raw=ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]!=ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")

    d=bytearray(raw); changes=[]
    for label,off,before,after in PATCHES:
        cur=bytes(d[off:off+len(before)])
        if cur==after:
            changes.append({"label":label,"offset":f"0x{off:08X}","status":"already-patched"})
            continue
        if cur!=before:
            raise RuntimeError(f"{label}: unknown bytes at 0x{off:08X}: {fmt(cur)}")
        d[off:off+len(before)]=after
        changes.append({"label":label,"offset":f"0x{off:08X}","status":"patched",
                        "before":fmt(before),"after":fmt(after)})

    before=sha(raw)
    bdir=root/"_BACKUPS"/"CAMPAIGN-OFFLINE-V7"
    bdir.mkdir(parents=True,exist_ok=True)
    bak=bdir/f"AMS.exe.{before}.bak"
    if not bak.exists(): shutil.copy2(ams,bak)

    tmp=ams.with_suffix(".offline-v7.tmp"); tmp.write_bytes(d)
    verify=tmp.read_bytes()
    for label,off,_before,after in PATCHES:
        if verify[off:off+len(after)]!=after:
            raise RuntimeError(f"verification failed: {label}")
    tmp.replace(ams)

    out=root/"_TRACE_MONTAR"; out.mkdir(parents=True,exist_ok=True)
    report={
      "phase":"Campaign Offline Lobby Adapter v7",
      "strategy":"dispatcher-specific; no global popup hook",
      "logical_connectivity":"offline/false",
      "popup_dispatcher":"untouched",
      "lobby_dispatcher":"0x00916AE0",
      "no_internet_codes":["0x0BC2","0x0FAA"],
      "no_internet_codes_action":"existing native common epilogue 0x00917409",
      "late_no_internet_block":"0x009171DC bypassed",
      "sha256_before":before,"sha256_after":sha(ams.read_bytes()),
      "backup":str(bak),"changes":changes
    }
    (out/"CAMPAIGN-OFFLINE-LOBBY-V7.json").write_text(
      json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

    print("[OK] Campaign Offline Lobby Adapter v7 applied.")
    print("[PROFILE] local startup baseline retained.")
    print("[POPUP] GS_MessagePopup: untouched.")
    print("[LOBBY] NO_INTERNET codes 0x0BC2 + 0x0FAA: bypassed.")
    print("[LOBBY] late NO_INTERNET construction block: bypassed.")
    print("[NETWORK] Global IsOnline: FALSE")
    print(f"[AMS] {report['sha256_after']}")
    return 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",required=True)
    ns=ap.parse_args()
    try:return apply(Path(ns.project_root).resolve())
    except Exception as e:
        print("[ERRO]",e);return 1

if __name__=="__main__":raise SystemExit(main())
