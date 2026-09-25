#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


EXPORTS = [
    (
        b"RexExp00XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?AddIGPComponent@IGPControl@IGPLib@@QAEXPBD@Z",
    ),
    (
        b"RexExp01XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?DestroyIGP@IGPControl@IGPLib@@SAXXZ",
    ),
    (
        b"RexExp02XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?GetInstance@IGPControl@IGPLib@@SAPAV12@XZ",
    ),
    (
        b"RexExp03XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?HttpPostLink@IGPControl@IGPLib@@QAEXPBD@Z",
    ),
    (
        b"RexExp04XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?Init@IGPControl@IGPLib@@SAXABUInitParams@2@@Z",
    ),
    (
        b"RexExp05XXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?InitBridgeCallbacks@IGPLib@@YAXXZ",
    ),
    (
        b"RexExp06XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?InitBridgeClass@IGPLib@@YAXP$AAVPanel@Controls@Xaml@UI@Windows@@@Z",
    ),
    (
        b"RexExp07XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?IsOnScreenFreemium@IGPControl@IGPLib@@SA_NXZ",
    ),
    (
        b"RexExp08XXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?PauseIGP@IGPControl@IGPLib@@QAEXXZ",
    ),
    (
        b"RexExp09XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?ResumeIGP@IGPControl@IGPLib@@QAEXXZ",
    ),
    (
        b"RexExp10XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?SetGender@IGPControl@IGPLib@@SAXPBD@Z",
    ),
    (
        b"RexExp11XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?SetIGPLanguage@IGPControl@IGPLib@@QAEXPBD@Z",
    ),
    (
        b"RexExp12XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?SetUserAge@IGPControl@IGPLib@@SAXPBD@Z",
    ),
    (
        b"RexExp13XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        b"?ShowIGP@IGPControl@IGPLib@@QAEX_N@Z",
    ),
]


def rewrite(path: Path) -> None:
    data = bytearray(path.read_bytes())

    for placeholder, target in EXPORTS:
        if len(placeholder) != len(target):
            raise RuntimeError(
                f"length mismatch: {placeholder!r} -> {target!r}"
            )

        needle = placeholder + b"\x00"
        replacement = target + b"\x00"
        count = data.count(needle)
        if count != 1:
            raise RuntimeError(
                f"expected one export placeholder {placeholder!r}, found {count}"
            )

        offset = data.find(needle)
        data[offset : offset + len(needle)] = replacement

    for placeholder, target in EXPORTS:
        if placeholder + b"\x00" in data:
            raise RuntimeError(f"placeholder survived: {placeholder!r}")
        if data.count(target + b"\x00") != 1:
            raise RuntimeError(f"target export count invalid: {target!r}")

    path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dll", type=Path)
    args = parser.parse_args()
    rewrite(args.dll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
