#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


class StartupPatchError(RuntimeError):
    pass


def patch_bytes(data: bytes) -> bytes:
    return bytes(data)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    args.output.write_bytes(patch_bytes(args.input.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
