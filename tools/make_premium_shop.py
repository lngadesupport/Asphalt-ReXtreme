#!/usr/bin/env python3
"""Create Premium-v2 asphaltshop data: every positive car price is 80% of original."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
CAR=re.compile(r'<Car\s+carId="(?P<id>\d+)"[^>]*>.*?</Car>',re.S)
PRICE=re.compile(r'(<Price\s+Id="CAR_PRICE"\s+Price=")(?P<price>\d+)("\s+Currency=")(?P<currency>credits|hardcurrency)("\s*/>)')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("asphaltshop",type=Path); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--report",type=Path); ap.add_argument("--vehicle-multiplier",type=float,default=.80)
    a=ap.parse_args(); text=a.asphaltshop.read_text(encoding="utf-8-sig"); changes=[]
    def car_repl(m):
        block=m.group(0); cid=int(m.group("id"))
        def p_repl(p):
            old=int(p.group("price")); cur=p.group("currency")
            if old<=0: return p.group(0)
            new=max(1,int(round(old*a.vehicle_multiplier)))
            changes.append({"car_id":cid,"currency":cur,"original":old,"premium":new})
            return p.group(1)+str(new)+p.group(3)+cur+p.group(5)
        return PRICE.sub(p_repl,block)
    out=CAR.sub(car_repl,text); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(out,encoding="utf-8",newline="")
    report={"rule":"all positive CAR_PRICE values use 0.80 multiplier; currency type preserved","vehicle_multiplier":a.vehicle_multiplier,"changed_entries":len(changes),"cars_changed":len(set(c["car_id"] for c in changes)),"credits_changes":sum(c["currency"]=="credits" for c in changes),"hardcurrency_changes":sum(c["currency"]=="hardcurrency" for c in changes),"changes":changes,"input_bytes":len(text.encode("utf-8")),"output_bytes":a.output.stat().st_size}
    rp=a.report or a.output.with_suffix(a.output.suffix+".report.json"); rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("changed_entries","cars_changed","credits_changes","hardcurrency_changes","output_bytes")},indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
