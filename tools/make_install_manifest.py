#!/usr/bin/env python3
"""Create the installer payload manifest with mandatory SHA-256 hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", type=Path, required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--certificate", required=True)
    ap.add_argument("--dependency", default="")
    ap.add_argument("--version", default="1.0.0-rc1")
    args = ap.parse_args()

    payload = args.payload.resolve()
    package = payload / args.package
    certificate = payload / args.certificate
    dependency = payload / args.dependency if args.dependency else None

    required = [package, certificate]
    if dependency is not None:
        required.append(dependency)

    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit("Missing payload file(s):\n" + "\n".join(missing))

    data = {
        "product": "Asphalt ReXtreme",
        "version": args.version,
        "package": package.name,
        "certificate": certificate.name,
        "dependency": dependency.name if dependency else None,
        "packageSha256": sha256_file(package),
        "certificateSha256": sha256_file(certificate),
        "dependencySha256": sha256_file(dependency) if dependency else None,
    }

    out = payload / "install-manifest.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
