#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import struct
from pathlib import Path
from typing import Any


MAGIC = b"REXCTV2\x00"
SCHEMA = 2
MAX_VEHICLES = 128
MAX_INITIAL_BALANCES = 256
MAX_STARTER_OWNED = 128
U32_MAX = 0xFFFFFFFF


def _u32(value: Any, field: str, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < 0 or value > U32_MAX:
        raise ValueError(f"{field} must fit uint32")
    if not allow_zero and value == 0:
        raise ValueError(f"{field} must be positive")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _pack_u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _normalize(document: dict[str, Any]) -> tuple[
    list[tuple[int, int, int, int, int]],
    list[tuple[int, int]],
    list[int],
]:
    schema = _u32(document.get("schema"), "schema", allow_zero=False)
    if schema != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")

    vehicle_docs = _list(document.get("vehicles"), "vehicles")
    if len(vehicle_docs) > MAX_VEHICLES:
        raise ValueError(f"vehicles exceeds {MAX_VEHICLES}")

    vehicle_ids: set[int] = set()
    vehicles: list[tuple[int, int, int, int, int]] = []

    for index, raw_vehicle in enumerate(vehicle_docs):
        vehicle = _dict(raw_vehicle, f"vehicles[{index}]")
        vehicle_id = _u32(
            vehicle.get("vehicle_id"),
            f"vehicles[{index}].vehicle_id",
            allow_zero=False,
        )
        if vehicle_id in vehicle_ids:
            raise ValueError(f"duplicate vehicle_id: {vehicle_id}")
        vehicle_ids.add(vehicle_id)

        unlocked = _bool(
            vehicle.get("unlocked_by_default"),
            f"vehicles[{index}].unlocked_by_default",
        )

        recipe = vehicle.get("recipe")
        if recipe is None:
            has_recipe = 0
            blueprint_id = 0
            cost = 0
        else:
            recipe_obj = _dict(recipe, f"vehicles[{index}].recipe")
            has_recipe = 1
            blueprint_id = _u32(
                recipe_obj.get("blueprint_id"),
                f"vehicles[{index}].recipe.blueprint_id",
                allow_zero=False,
            )
            cost = _u32(
                recipe_obj.get("cost"),
                f"vehicles[{index}].recipe.cost",
                allow_zero=False,
            )

        vehicles.append(
            (
                vehicle_id,
                int(unlocked),
                has_recipe,
                blueprint_id,
                cost,
            )
        )

    initial_state = _dict(
        document.get("initial_state"),
        "initial_state",
    )
    balance_docs = _list(
        initial_state.get("blueprints"),
        "initial_state.blueprints",
    )
    if len(balance_docs) > MAX_INITIAL_BALANCES:
        raise ValueError(
            f"initial_state.blueprints exceeds {MAX_INITIAL_BALANCES}"
        )

    balance_ids: set[int] = set()
    balances: list[tuple[int, int]] = []
    for index, raw_balance in enumerate(balance_docs):
        balance = _dict(
            raw_balance,
            f"initial_state.blueprints[{index}]",
        )
        blueprint_id = _u32(
            balance.get("blueprint_id"),
            f"initial_state.blueprints[{index}].blueprint_id",
            allow_zero=False,
        )
        if blueprint_id in balance_ids:
            raise ValueError(f"duplicate blueprint_id: {blueprint_id}")
        balance_ids.add(blueprint_id)
        amount = _u32(
            balance.get("amount"),
            f"initial_state.blueprints[{index}].amount",
        )
        balances.append((blueprint_id, amount))

    owned_docs = _list(
        initial_state.get("owned_vehicles"),
        "initial_state.owned_vehicles",
    )
    if len(owned_docs) > MAX_STARTER_OWNED:
        raise ValueError(
            f"initial_state.owned_vehicles exceeds {MAX_STARTER_OWNED}"
        )

    owned_ids: set[int] = set()
    owned: list[int] = []
    for index, raw_vehicle_id in enumerate(owned_docs):
        vehicle_id = _u32(
            raw_vehicle_id,
            f"initial_state.owned_vehicles[{index}]",
            allow_zero=False,
        )
        if vehicle_id in owned_ids:
            raise ValueError(f"duplicate starter vehicle_id: {vehicle_id}")
        if vehicle_id not in vehicle_ids:
            raise ValueError(
                f"starter vehicle_id not present in vehicles: {vehicle_id}"
            )
        owned_ids.add(vehicle_id)
        owned.append(vehicle_id)

    vehicles.sort(key=lambda row: row[0])
    balances.sort(key=lambda row: row[0])
    owned.sort()

    return vehicles, balances, owned


def build_bytes(document: dict[str, Any]) -> bytes:
    if not isinstance(document, dict):
        raise ValueError("manifest root must be an object")

    vehicles, balances, owned = _normalize(document)

    output = bytearray(MAGIC)
    output += _pack_u32(SCHEMA)
    output += _pack_u32(len(vehicles))

    for row in vehicles:
        for value in row:
            output += _pack_u32(value)

    output += _pack_u32(len(balances))
    for blueprint_id, amount in balances:
        output += _pack_u32(blueprint_id)
        output += _pack_u32(amount)

    output += _pack_u32(len(owned))
    for vehicle_id in owned:
        output += _pack_u32(vehicle_id)

    return bytes(output)


def build_file(source: Path | str, destination: Path | str) -> None:
    source_path = Path(source)
    destination_path = Path(destination)

    document = json.loads(source_path.read_text(encoding="utf-8"))
    payload = build_bytes(document)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination_path.with_name(
        destination_path.name + ".tmp"
    )
    temporary.write_bytes(payload)
    os.replace(temporary, destination_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build ReX CampaignContentV2.dat",
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    build_file(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
