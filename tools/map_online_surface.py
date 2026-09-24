#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, struct
from pathlib import Path

ASCII_MARKERS = {
    "multiplayer": [b"multiplayer", b"matchmaking", b"matchmaker", b"pvp"],
    "leaderboards": [b"leaderboard", b"ranking", b"gamerscore"],
    "social": [b"facebook", b"social", b"friends"],
    "iap": [b"iap", b"in_app", b"inapp", b"purchase", b"billing"],
    "ads": [b"rewarded", b"advert", b"ads_", b"video_ad"],
    "cloud": [b"cloud", b"sync", b"profile_sync"],
    "push": [b"push", b"notification"],
    "remote_config": [b"remote_config", b"config.php", b"configuration"],
    "telemetry": [b"telemetry", b"analytics", b"tracking"],
    "network": [b"http://", b"https://", b"socket", b"connect", b"request"],
}

NETWORK_DLLS = [
    b"winhttp.dll",
    b"wininet.dll",
    b"ws2_32.dll",
    b"urlmon.dll",
    b"webservices.dll",
]

URL_RE = re.compile(rb"https?://[^\x00\s\"'<>]{4,220}", re.I)

def ascii_context(data: bytes, off: int, radius: int = 64) -> str:
    a=max(0,off-radius); z=min(len(data),off+radius)
    raw=data[a:z]
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw)

def find_all(haystack: bytes, needle: bytes):
    start=0
    n=needle.lower()
    h=haystack.lower()
    while True:
        i=h.find(n,start)
        if i<0: break
        yield i
        start=i+1

def scan_utf16(data: bytes, text: str):
    enc=text.encode("utf-16le")
    return list(find_all(data,enc))

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():
        print("[ERRO] missing",ams)
        return 2

    data=ams.read_bytes()
    categories={}
    for cat,markers in ASCII_MARKERS.items():
        hits=[]
        for marker in markers:
            for off in find_all(data,marker):
                hits.append({
                    "encoding":"ascii",
                    "marker":marker.decode("ascii","replace"),
                    "offset":f"0x{off:08X}",
                    "context":ascii_context(data,off)
                })
            try:
                text=marker.decode("ascii")
            except Exception:
                continue
            for off in scan_utf16(data,text):
                hits.append({
                    "encoding":"utf16le",
                    "marker":text,
                    "offset":f"0x{off:08X}"
                })
        categories[cat]=hits

    dlls={}
    low=data.lower()
    for dll in NETWORK_DLLS:
        offs=[f"0x{x:08X}" for x in find_all(low,dll)]
        if offs:
            dlls[dll.decode("ascii")]=offs

    urls=[]
    seen=set()
    for m in URL_RE.finditer(data):
        u=m.group(0).decode("ascii","replace")
        if u in seen: continue
        seen.add(u)
        urls.append({"offset":f"0x{m.start():08X}","url":u})

    report={
        "schema":1,
        "ams":str(ams),
        "size":len(data),
        "network_dll_string_markers":dlls,
        "urls":urls,
        "categories":categories,
        "counts":{
            "urls":len(urls),
            **{k:len(v) for k,v in categories.items()}
        },
        "note":"Presence is inventory only. It does not prove runtime reachability. Each hit must be classified during migration."
    }
    outdir=root/"_TRACE_MONTAR"
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/"ONLINE-SURFACE-MAP.json"
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

    print("[ONLINE-SURFACE] AMS:",ams)
    print("[ONLINE-SURFACE] URLs:",len(urls))
    for k,v in categories.items():
        print(f"[ONLINE-SURFACE] {k}: {len(v)}")
    if dlls:
        print("[ONLINE-SURFACE] network DLL markers:",", ".join(sorted(dlls)))
    print("[REPORT]",out)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
