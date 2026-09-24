#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GARAGE_PATH = ROOT / "tools" / "campaign_garage_v2.py"
spec = importlib.util.spec_from_file_location("campaign_garage_v2_probe_base", GARAGE_PATH)
g = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(g)


def apply_mode(project_root: Path, mode: str) -> None:
    ams = project_root / "_PACKAGE_PHASE5" / "AMS.exe"
    data = bytearray(ams.read_bytes())
    g.validate_pe(data)

    if bytes(data[g.ONLINE_OFF:g.ONLINE_OFF + len(g.ONLINE_FALSE)]) != g.ONLINE_FALSE:
        raise RuntimeError("Phase2 Global IsOnline FALSE guard missing")

    gateway, owned_stub_va = g.build_gateway()

    if mode in {"gateway-only", "build-only", "ownership-only", "build-ownership", "full"}:
        if bytes(data[g.CAVE_OFF:g.CAVE_OFF + g.CAVE_LEN]) != g.P48_CAVE_ORIG:
            raise RuntimeError("Campaign gateway cave is not pristine")
        data[g.CAVE_OFF:g.CAVE_OFF + g.CAVE_LEN] = gateway

    if mode in {"popup-only", "full"}:
        cur = bytes(data[g.POPUP_OFF:g.POPUP_OFF + len(g.POPUP_PATCH)])
        if cur not in g.POPUP_EXPECTED_STATES:
            raise RuntimeError("popup site unexpected")
        data[g.POPUP_OFF:g.POPUP_OFF + len(g.POPUP_PATCH)] = g.POPUP_PATCH

    if mode in {"build-only", "build-ownership", "full"}:
        cur = bytes(data[g.BUILD_OFF:g.BUILD_OFF + 5])
        if cur != g.BUILD_ORIG:
            raise RuntimeError("BuildCar entry is not pristine")
        patch = b"\xE9" + g.rel32(g.BUILD_VA, 5, g.CAVE_VA)
        data[g.BUILD_OFF:g.BUILD_OFF + 5] = patch

    if mode in {"ownership-only", "build-ownership", "full"}:
        cur = bytes(data[g.OWN_OFF:g.OWN_OFF + 5])
        if cur != g.OWN_ORIG:
            raise RuntimeError("ownership entry is not pristine")
        patch = b"\xE9" + g.rel32(g.OWN_VA, 5, owned_stub_va)
        data[g.OWN_OFF:g.OWN_OFF + 5] = patch

    ams.write_bytes(data)
    print(f"[OK] Campaign Garage startup probe mode applied: {mode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument(
        "--mode",
        required=True,
        choices=[
            "popup-only",
            "gateway-only",
            "build-only",
            "ownership-only",
            "build-ownership",
            "full",
        ],
    )
    ns = ap.parse_args()
    try:
        apply_mode(Path(ns.project_root).resolve(), ns.mode)
        return 0
    except Exception as exc:
        print(f"[ERRO] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
