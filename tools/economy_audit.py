#!/usr/bin/env python3
"""Audit paid-game economy against the 1.7.3.8 main career."""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path

FILTERS={
"CarFilter_Car_Buggy_Rage_Comet":2,"CarFilter_Car_Rally_Ford_Focus":22,
"CarFilter_Car_SUV_LandRover_Defender":31,"CarFilter_Car_MonsterTruck_Silverado_2500":78,
"CarFilter_Car_SUV_Jeep_Wrangler":35,"CarFilter_Car_Truck_Unimog_U400":62,
"CarFilter_Car_Buggy_Predator_Intimidator":1,"CarFilter_Car_Truck_Bulldog_Extreme":63,
"CarFilter_Car_MonsterTruck_Bel_Air":77,"CarFilter_Car_Buggy_BCN_Concept":3,
"CarFilter_Car_MonsterTruck_Type2_T1":80,"CarFilter_Car_Rally_Mitsubishi_R5":17,
"CarFilter_Car_MonsterTruck_Chevy_3100":79,"CarFilter_Car_Muscle_Camaro_1967":94,
"CarFilter_Car_Buggy_SMG_Dakar":4,"CarFilter_Car_Truck_Perlini_105F":61,
"CarFilter_Car_Rally_Polo_WRC":16,"CarFilter_Car_Pickup_Nissan_Titan_XD":48,
"CarFilter_Car_Rally_Peugeot_208":18,"CarFilter_Car_Truck_MAN_TGX":64,
"CarFilter_Car_SUV_Mercedes_G500":37,"CarFilter_Car_MonsterTruck_Ford_Coupe":76,
"CarFilter_Car_Buggy_Ariel_Nomad":5,"CarFilter_Car_MonsterTruck_Hummer_H1":82,
"CarFilter_Car_SUV_Evoque_Coupe":34,"CarFilter_Car_Rally_Beetle_GRC":19,
"CarFilter_Car_MonsterTruck_Delorean_DMC":81,"CarFilter_Car_Rally_LancerEvolution_X":24,
"CarFilter_Car_Truck_Mercedes_Zetros":65,"CarFilter_Car_Rally_Subaru_WRX":20,
"CarFilter_Car_SUV_Hummer_HX":36,"CarFilter_Car_Buggy_Hoggar_Concept":6,
"CarFilter_Car_Muscle_Bailey_Blade_GT1":95}

def load(p): return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def reward(e,prefix):
    return int(e.get(prefix+"_amount",0) or 0) if str(e.get(prefix+"_type","")).lower()=="credits" else 0
def season_rewards(s):
    c=h=0
    for r in s.get("rewards",[]) or []:
        typ=str(r.get("completionrewardtype","")).lower(); n=int(r.get("completionrewardamount",0) or 0)
        if typ=="credits": c+=n
        elif typ=="hardcurrency": h+=n
    return c,h
def write_csv(path,rows):
    if not rows: Path(path).write_text("",encoding="utf-8"); return
    keys=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen: seen.add(k); keys.append(k)
    with Path(path).open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("career_data",type=Path); ap.add_argument("car_catalog",type=Path)
    ap.add_argument("--out",type=Path,default=Path("economy-audit")); ap.add_argument("--vehicle-multiplier",type=float,default=.80)
    a=ap.parse_args(); career=load(a.career_data); cars=load(a.car_catalog); byid={int(c["car_id"]):c for c in cars}
    seasons=sorted([s for s in career["seasons"] if int(s.get("serieid",0) or 0)==1],key=lambda s:int(s.get("index",0) or 0))
    sids={int(s.get("seasonid",s.get("id",0)) or 0) for s in seasons}
    events=sorted([e for e in career["events"] if int(e.get("season",0) or 0) in sids and not e.get("masteries",False)],key=lambda e:int(e.get("eventid",0) or 0))
    byseason=defaultdict(list)
    for e in events: byseason[int(e["season"])].append(e)
    cum=hc=0; seen=set(); sr=[]; gates=[]
    for s in seasons:
        sid=int(s.get("seasonid",s.get("id",0)) or 0); rep=stars=comp=0
        for e in sorted(byseason[sid],key=lambda x:int(x["eventid"])):
            r=int(e.get("money_for_playing",0) or 0)+int(e.get("position_1",0) or 0)
            st=sum(reward(e,x) for x in ("first_star_reward","second_star_reward","third_star_reward"))
            co=reward(e,"completion_reward"); filt=str(e.get("carracerfilter","") or "")
            if filt.startswith("CarFilter_Car_") and filt not in seen:
                seen.add(filt); cid=FILTERS.get(filt); car=byid.get(cid,{})
                cr=int(car.get("credit_price",0) or 0) if car else None
                hard=int(car.get("hardcurrency_price",0) or 0) if car else None
                target=int(round(cr*a.vehicle_multiplier)) if cr and cr>0 else None
                action="credit_price_80pct" if target is not None else ("hardcurrency_only_needs_conversion_or_grant" if hard else "review")
                gates.append({"event_id":int(e["eventid"]),"season":sid,"filter":filt,"car_id":cid or "",
                    "car_def":car.get("car_def",""),"class":car.get("class",""),"original_credit_price":cr if cr is not None else "",
                    "original_hardcurrency_price":hard if hard is not None else "","premium_credit_target_80pct":target if target is not None else "",
                    "gross_credits_before_event_upper_bound":cum,"gross_hardcurrency_before_event":hc,
                    "target_exceeds_gross_upper_bound":bool(target is not None and target>cum),"acquisition_action":action})
            cum+=r+st+co; rep+=r; stars+=st; comp+=co
        scr,shr=season_rewards(s); cum+=scr; hc+=shr
        sr.append({"season":sid,"class":s.get("carclass",""),"events":len(byseason[sid]),
            "repeatable_first_place_credits_once_each":rep,"one_time_star_credits":stars,
            "event_completion_credits":comp,"season_completion_credits":scr,"season_completion_hardcurrency":shr,
            "ideal_first_clear_credit_total":rep+stars+comp+scr,"cumulative_gross_credits_upper_bound":cum,"cumulative_hardcurrency":hc})
    vr=[]
    for c in sorted(cars,key=lambda x:int(x["car_id"])):
        cr=int(c.get("credit_price",0) or 0); hard=int(c.get("hardcurrency_price",0) or 0)
        vr.append({"car_id":int(c["car_id"]),"car_def":c.get("car_def",""),"class":c.get("class",""),
            "original_credit_price":cr,"original_hardcurrency_price":hard,
            "premium_credit_target_80pct":int(round(cr*a.vehicle_multiplier)) if cr>0 else "",
            "premium_action":"discount_credit_and_disable_hardcurrency" if cr>0 else "convert_hardcurrency_only_to_progression_credit_or_unlock",
            "credit_upgrade_total_original":int(c.get("credit_upgrade_total",0) or 0),
            "hardcurrency_upgrade_total_original":int(c.get("hardcurrency_upgrade_total",0) or 0)})
    out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"season-summary.csv",sr); write_csv(out/"mandatory-car-gates.csv",gates); write_csv(out/"vehicle-price-baseline.csv",vr)
    summary={"main_seasons":len(seasons),"main_events":len(events),"credits":{
        "repeatable_first_place_once_each":sum(x["repeatable_first_place_credits_once_each"] for x in sr),
        "one_time_star_rewards":sum(x["one_time_star_credits"] for x in sr),
        "season_completion_rewards":sum(x["season_completion_credits"] for x in sr),
        "gross_ideal_first_clear_total":cum},"hardcurrency_from_main_season_completion":hc,
        "vehicles":{"catalog_count":len(vr),"hardcurrency_only_count":sum(1 for x in vr if x["original_credit_price"]==0 and x["original_hardcurrency_price"]>0),"vehicle_price_multiplier":a.vehicle_multiplier},
        "mandatory_exact_car_gates":{"count":len(gates),"hardcurrency_only_count":sum(1 for x in gates if x["acquisition_action"].startswith("hardcurrency_only"))},
        "notes":["repeat payout candidate = money_for_playing + position_1","star rewards are treated as one-time progression rewards","gross-before-gate is an upper bound; prior purchases/upgrades are not subtracted"]}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
