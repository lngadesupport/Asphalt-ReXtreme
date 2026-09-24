from __future__ import annotations
import importlib.util
import json
import struct
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_campaign_championship_catalog.py"
spec = importlib.util.spec_from_file_location("build_campaign_championship_catalog", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def write_source(path: Path, rows):
    path.write_text(json.dumps({
        "format": "rextreme-campaign-championships",
        "version": 1,
        "championships": rows,
    }), encoding="utf-8")

def write_events(path: Path, ids: list[int]):
    payload = bytearray(mod.EVENT_HEADER.pack(mod.EVENT_MAGIC, 1, len(ids), 0))
    for event_id in ids:
        payload += mod.EVENT_ENTRY.pack(event_id, 0, 0, 3, 0, 0, 0, 0, 0, 0)
    payload += mod.EVENT_ENTRY.pack(*([0]*10)) * (mod.EVENT_MAX-len(ids))
    payload += struct.pack("<I", mod.fnv1a(payload))
    path.write_bytes(payload)

def test_empty_catalog_is_safe(tmp_path: Path):
    src=tmp_path/"c.json"; out=tmp_path/"CampaignChampionships.dat"
    write_source(src, [])
    result=mod.build(src,out)
    assert result["count"]==0
    assert len(out.read_bytes()) == mod.HEADER.size + mod.ENTRY.size*mod.MAX_CHAMPIONSHIPS + 4

def test_nonempty_requires_event_catalog(tmp_path: Path):
    src=tmp_path/"c.json"; out=tmp_path/"out.dat"
    write_source(src,[{"id":1,"rounds":[1001],"points":[10,8,6,5,4,3,2]}])
    try:
        mod.build(src,out)
    except mod.ChampionshipError as exc:
        assert "event-catalog" in str(exc)
    else:
        raise AssertionError("missing event catalog accepted")

def test_cross_validates_rounds_and_points(tmp_path: Path):
    src=tmp_path/"c.json"; out=tmp_path/"out.dat"; events=tmp_path/"CampaignEvents.dat"
    write_events(events,[1001,1002,1003])
    write_source(src,[{
        "id":7001,
        "required_node_id":0,
        "rounds":[1001,1002,1003],
        "points":[10,8,6,5,4,3,2]
    }])
    result=mod.build(src,out,events)
    assert result["count"]==1
    assert result["validated_against_event_catalog"] is True
    assert result["uses_existing_campaign_events_only"] is True
