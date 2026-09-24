from __future__ import annotations
import importlib.util,json
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/"tools"/"build_campaign_achievement_catalog.py"
spec=importlib.util.spec_from_file_location("build_campaign_achievement_catalog",MODULE)
mod=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(mod)

def test_empty_fixed_size(tmp_path):
 s=tmp_path/"a.json";o=tmp_path/"CampaignAchievements.dat"
 s.write_text(json.dumps({"format":"rextreme-campaign-achievements","version":1,"achievements":[]}),encoding="utf-8")
 r=mod.build(s,o)
 assert r["count"]==0
 assert mod.ENTRY.size==32
 assert len(o.read_bytes())==16+128*32+4

def test_existing_statistics_metrics_only(tmp_path):
 s=tmp_path/"a.json";o=tmp_path/"out.dat"
 s.write_text(json.dumps({"format":"rextreme-campaign-achievements","version":1,"achievements":[
 {"id":2,"metric":"best_finish_time_ms","compare":"le","threshold":60000},
 {"id":1,"metric":"wins","compare":"ge","threshold":1}
 ]}),encoding="utf-8")
 r=mod.build(s,o);assert r["ids"]==[1,2]

def test_unknown_metric_rejected(tmp_path):
 s=tmp_path/"a.json";o=tmp_path/"out.dat"
 s.write_text(json.dumps({"format":"rextreme-campaign-achievements","version":1,"achievements":[
 {"id":1,"metric":"invented_stat","compare":"ge","threshold":1}]}),encoding="utf-8")
 try:mod.build(s,o)
 except mod.AchievementError as e:assert "invalid metric" in str(e)
 else:raise AssertionError("invented metric accepted")


def test_zero_threshold_rejected(tmp_path):
 s=tmp_path/"a.json";o=tmp_path/"out.dat"
 s.write_text(json.dumps({"format":"rextreme-campaign-achievements","version":1,"achievements":[
 {"id":1,"metric":"wins","compare":"ge","threshold":0}]}),encoding="utf-8")
 try:mod.build(s,o)
 except mod.AchievementError as e:assert "threshold must be > 0" in str(e)
 else:raise AssertionError("zero-threshold achievement accepted")
