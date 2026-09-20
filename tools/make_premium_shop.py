#!/usr/bin/env python3
"""Create Premium asphaltshop data while preserving purchase currency."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CAR = re.compile(r'<Car\s+carId="(?P<id>\d+)"[^>]*>.*?</Car>', re.S)
PRICE = re.compile(
    r'(<Price\s+Id="CAR_PRICE"\s+Price=")(?P<price>\d+)("'
    r'\s+Currency=")(?P<currency>credits|hardcurrency)("\s*/>)'
)


def transform_shop(text: str, vehicle_multiplier: float = 0.80) -> tuple[str, dict]:
    if not 0 < vehicle_multiplier <= 1:
        raise ValueError("vehicle_multiplier must be > 0 and <= 1")

    changes: list[dict] = []

    def car_repl(match: re.Match[str]) -> str:
        block = match.group(0)
        car_id = int(match.group("id"))

        def price_repl(price_match: re.Match[str]) -> str:
            old = int(price_match.group("price"))
            currency = price_match.group("currency")
            if old <= 0:
                return price_match.group(0)

            new = max(1, int(round(old * vehicle_multiplier)))
            changes.append(
                {
                    "car_id": car_id,
                    "currency": currency,
                    "original": old,
                    "premium": new,
                }
            )
            return (
                price_match.group(1)
                + str(new)
                + price_match.group(3)
                + currency
                + price_match.group(5)
            )

        return PRICE.sub(price_repl, block)

    output = CAR.sub(car_repl, text)
    report = {
        "rule": "all positive CAR_PRICE values use multiplier; currency type preserved",
        "vehicle_multiplier": vehicle_multiplier,
        "changed_entries": len(changes),
        "cars_changed": len({c["car_id"] for c in changes}),
        "credits_changes": sum(c["currency"] == "credits" for c in changes),
        "hardcurrency_changes": sum(c["currency"] == "hardcurrency" for c in changes),
        "changes": changes,
        "input_bytes": len(text.encode("utf-8")),
        "output_bytes": len(output.encode("utf-8")),
    }
    return output, report


def transform_file(
    source: Path,
    output: Path,
    report_path: Path | None = None,
    vehicle_multiplier: float = 0.80,
) -> dict:
    text = source.read_text(encoding="utf-8-sig")
    transformed, report = transform_shop(text, vehicle_multiplier)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(transformed, encoding="utf-8", newline="")

    report["output_bytes"] = output.stat().st_size
    final_report_path = report_path or output.with_suffix(output.suffix + ".report.json")
    final_report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asphaltshop", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--vehicle-multiplier", type=float, default=0.80)
    args = ap.parse_args()

    report = transform_file(
        args.asphaltshop,
        args.output,
        args.report,
        args.vehicle_multiplier,
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "changed_entries",
                    "cars_changed",
                    "credits_changes",
                    "hardcurrency_changes",
                    "output_bytes",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
