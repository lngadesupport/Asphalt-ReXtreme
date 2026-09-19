#!/usr/bin/env python3
"""Create conservative Phase-1 Premium asphaltshop data."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
CAR=re.compile(r'<Car\s+carId="(?P<id>\d+)"[^>]*>.*?</Car>',re.S)
PRICE=re.compile(r'(<Price\s+Id="CAR_PRICE"\s+Price=")(?P<price>\d+)("\s+Currency=")(?P<currency>credits|hardcurrency)("\s*/>)')
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("asphaltshop",type=Path); ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--report",type=Path); ap.add_argument("--vehicle-multiplier",type=float,default=.80)
    a=ap.parse_args(); text=a.asphaltshop.read_text(encoding="utf-8-sig"); changed=[]; pending=[]
    def car_repl(m):
        block=m.group(0); cid=int(m.group("id")); vals={}
        for pm in PRICE.finditer(block): vals[pm.group("currency")]=int(pm.group("price"))
        credit=vals.get("credits",0); hard=vals.get("hardcurrency",0)
        if credit>0:
            target=max(0,int(round(credit*a.vehicle_multiplier)))
            def price_repl(p):
                cur=p.group("currency"); new=target if cur=="credits" else 0
                return p.group(1)+str(new)+p.group(3)+cur+p.group(5)
            changed.append({"car_id":cid,"original_credit":credit,"premium_credit":target,
                            "original_hardcurrency":hard,"premium_hardcurrency":0})
            return PRICE.sub(price_repl,block)
        if hard>0:
            pending.append({"car_id":cid,"hardcurrency_price":hard,
                            "reason":"needs progression-aware credit conversion or unlock"})
        return block
    out=CAR.sub(car_repl,text); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(out,encoding="utf-8",newline="")
    report={"vehicle_multiplier":a.vehicle_multiplier,"changed_credit_cars":len(changed),
            "pending_hardcurrency_only_cars":len(pending),"changes":changed,"pending":pending,
            "output_bytes":a.output.stat().st_size}
    rp=a.report or a.output.with_suffix(a.output.suffix+".report.json")
    rp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("vehicle_multiplier","changed_credit_cars",
          "pending_hardcurrency_only_cars","output_bytes")},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
