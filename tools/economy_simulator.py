#!/usr/bin/env python3
"""Simulate mandatory-car purchase progression and quantify farming."""
from __future__ import annotations
import argparse,json,math,statistics
from pathlib import Path
from economy_audit import FILTERS

def load(p): return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def event_credits(e):
    n=int(e.get("money_for_playing",0) or 0)+int(e.get("position_1",0) or 0)
    for pre in ("first_star_reward","second_star_reward","third_star_reward","completion_reward"):
        if str(e.get(pre+"_type","")).lower()=="credits": n+=int(e.get(pre+"_amount",0) or 0)
    return n
def repeat_payout(e): return int(e.get("money_for_playing",0) or 0)+int(e.get("position_1",0) or 0)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("career_data",type=Path); ap.add_argument("car_catalog",type=Path)
    ap.add_argument("--reward-multiplier",type=float,default=1.0); ap.add_argument("--vehicle-multiplier",type=float,default=.80)
    ap.add_argument("--upgrade-reserve-fraction",type=float,default=0.0)
    ap.add_argument("--out",type=Path)
    a=ap.parse_args(); career=load(a.career_data); cars=load(a.car_catalog); byid={int(c["car_id"]):c for c in cars}
    ratios={cls:statistics.median([c["credit_price"]/c["hardcurrency_price"] for c in cars
            if c.get("class")==cls and c.get("credit_price",0)>0 and c.get("hardcurrency_price",0)>0]) for cls in "DCBAS"}
    seasons=sorted([s for s in career["seasons"] if int(s.get("serieid",0) or 0)==1],key=lambda s:int(s.get("index",0) or 0))
    wallet=0.0; owned=set(); prior=[]; gates=[]; total_farm=0; max_farm=0
    for s in seasons:
        sid=int(s.get("seasonid",s.get("id",0)) or 0)
        evs=sorted([e for e in career["events"] if int(e.get("season",0) or 0)==sid and not e.get("masteries",False)],
                   key=lambda e:int(e.get("eventid",0) or 0))
        for e in evs:
            f=str(e.get("carracerfilter","") or "")
            if f in FILTERS and FILTERS[f] not in owned:
                cid=FILTERS[f]; c=byid[cid]
                if int(c.get("credit_price",0) or 0)>0:
                    price=round(int(c["credit_price"])*a.vehicle_multiplier); source="credit_80pct"
                else:
                    price=round(int(c["hardcurrency_price"])*ratios[c["class"]]*a.vehicle_multiplier)
                    source="hc_class_equivalent_80pct"
                reserve=round(int(c.get("credit_upgrade_total",0) or 0)*a.upgrade_reserve_fraction)
                need=price+reserve; before=wallet; best=max(prior,default=0)*a.reward_multiplier; farm=0
                if wallet<need and best>0:
                    farm=math.ceil((need-wallet)/best); wallet+=farm*best
                short=max(0,need-wallet); wallet-=need
                total_farm+=farm; max_farm=max(max_farm,farm); owned.add(cid)
                gates.append({"event_id":int(e["eventid"]),"car_id":cid,"class":c["class"],"price":price,
                    "upgrade_reserve":reserve,"required_total":need,"price_source":source,
                    "wallet_before":round(before),"best_prior_repeat_payout":round(best),
                    "extra_repeats_needed":farm,"unfunded_shortfall":round(short),"wallet_after_purchase":round(wallet)})
            wallet+=event_credits(e)*a.reward_multiplier; prior.append(repeat_payout(e))
        for r in s.get("rewards",[]) or []:
            if str(r.get("completionrewardtype","")).lower()=="credits":
                wallet+=int(r.get("completionrewardamount",0) or 0)*a.reward_multiplier
    result={"reward_multiplier":a.reward_multiplier,"vehicle_multiplier":a.vehicle_multiplier,
            "upgrade_reserve_fraction":a.upgrade_reserve_fraction,"mandatory_cars":len(owned),
            "total_extra_repeats":total_farm,"max_extra_repeats_at_one_gate":max_farm,
            "final_wallet":round(wallet),"gates":gates,"class_credit_per_hardcurrency_median":ratios}
    print(json.dumps({k:v for k,v in result.items() if k not in ("gates","class_credit_per_hardcurrency_median")},indent=2))
    if a.out: a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
