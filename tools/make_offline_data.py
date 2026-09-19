#!/usr/bin/env python3
"""Generate service-disabled local data files without touching proprietary DLLs."""
from __future__ import annotations
import argparse,json,xml.etree.ElementTree as ET
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--iap-xml",type=Path,required=True)
    ap.add_argument("--snsconfig",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    text=a.iap_xml.read_text(encoding="utf-16")
    root=ET.fromstring(text); removed=[]
    for parent in root.iter():
        for child in list(parent):
            if child.tag.endswith("Product"):
                removed.append(child.attrib.get("ProductId",""))
                parent.remove(child)
    iap_out=a.out/"in-app-purchase_w8.1.xml"
    ET.ElementTree(root).write(iap_out,encoding="utf-16",xml_declaration=True)

    sns=json.loads(a.snsconfig.read_text(encoding="utf-8-sig"))
    win=sns.setdefault("snsConfig",{}).setdefault("Windows8",{})
    win.clear(); win.update({"Facebook":0,"Msn":0})
    sns_out=a.out/"snsconfig.json"
    sns_out.write_text(json.dumps(sns,indent=2,ensure_ascii=False),encoding="utf-8")

    report={"iap_products_removed":len(removed),"iap_output_bytes":iap_out.stat().st_size,
            "windows8_social":{"Facebook":0,"Msn":0}}
    (a.out/"offline-data-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
