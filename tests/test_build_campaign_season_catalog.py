from __future__ import annotations
import importlib.util,json,struct
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/"tools"/"build_campaign_season_catalog.py"
spec=importlib.util.spec_from_file_location("build_campaign_season_catalog",MODULE)
mod=importlib.util.module_from_spec(spec);assert spec.loader is not None;spec.loader.exec_module(mod)

def source(path:Path,rows):
    path.write_text(json.dumps({"format":"rextreme-campaign-seasons","version":1,"seasons":rows}),encoding="utf-8")

def events(path:Path,ids:list[int]):
    payload=bytearray(mod.EVENT_HEADER.pack(mod.EVENT_MAGIC,1,len(ids),0))
    for eid in ids:payload+=mod.EVENT_ENTRY.pack(eid,0,0,0,0,0,0,0,3,0)
    payload+=mod.EVENT_ENTRY.pack(*([0]*10))*(mod.EVENT_MAX-len(ids))
    payload+=struct.pack("<I",mod.fnv1a(payload));path.write_bytes(payload)

def test_layout_and_empty(tmp_path:Path):
    assert mod.ENTRY.size==144
    s=tmp_path/"s.json";o=tmp_path/"CampaignSeasons.dat";source(s,[])
    r=mod.build(s,o)
    assert r["count"]==0
    assert len(o.read_bytes())==9236

def test_nonempty_requires_events(tmp_path:Path):
    s=tmp_path/"s.json";o=tmp_path/"out.dat"
    source(s,[{"id":1,"events":[1001]}])
    try:mod.build(s,o)
    except mod.SeasonError as exc:assert "event-catalog" in str(exc)
    else:raise AssertionError("missing event catalog accepted")

def test_cross_validation(tmp_path:Path):
    s=tmp_path/"s.json";o=tmp_path/"out.dat";e=tmp_path/"CampaignEvents.dat"
    events(e,[1001,1002])
    source(s,[{"id":10,"events":[1001,1002]}])
    r=mod.build(s,o,e)
    assert r["count"]==1
    assert r["uses_existing_campaign_events_only"] is True
