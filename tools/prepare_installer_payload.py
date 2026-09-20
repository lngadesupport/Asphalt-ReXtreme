#!/usr/bin/env python3
"""Assemble a private Asphalt ReXtreme installer directory.

The public repository contains only this assembler. The caller supplies the
locally built APPX and private media/assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


PACKAGE_NAME = "Asphalt-ReXtreme-1.0.0.0-x86.appx"
CERT_NAME = "ReXtreme-Publisher.cer"
LOGO_NAME = "logo.png"
TRAILER_NAME = "trailer-vertical.mp4"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_required(source: Path, target: Path) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def assemble(
    installer_exe: Path,
    appx: Path,
    certificate: Path,
    out_dir: Path,
    dependency: Path | None = None,
    logo: Path | None = None,
    trailer: Path | None = None,
) -> Path:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    setup_target = copy_required(installer_exe, out_dir / "Asphalt-ReXtreme-Setup.exe")
    payload = out_dir / "payload"
    assets = out_dir / "assets"

    package_target = copy_required(appx, payload / PACKAGE_NAME)
    cert_target = copy_required(certificate, payload / CERT_NAME)

    dependency_target: Path | None = None
    if dependency is not None:
        dependency_target = copy_required(dependency, payload / dependency.name)

    if logo is not None:
        copy_required(logo, assets / LOGO_NAME)
    if trailer is not None:
        copy_required(trailer, assets / TRAILER_NAME)

    manifest = {
        "product": "Asphalt ReXtreme",
        "version": "1.0.0-rc1",
        "package": package_target.name,
        "certificate": cert_target.name,
        "dependency": dependency_target.name if dependency_target else None,
        "packageSha256": sha256_file(package_target),
        "certificateSha256": sha256_file(cert_target),
        "dependencySha256": sha256_file(dependency_target) if dependency_target else None,
        "setupSha256": sha256_file(setup_target),
    }

    manifest_path = payload / "install-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(out_dir)
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--installer-exe", type=Path, required=True)
    ap.add_argument("--appx", type=Path, required=True)
    ap.add_argument("--certificate", type=Path, required=True)
    ap.add_argument("--dependency", type=Path)
    ap.add_argument("--logo", type=Path)
    ap.add_argument("--trailer", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    assemble(
        installer_exe=args.installer_exe,
        appx=args.appx,
        certificate=args.certificate,
        dependency=args.dependency,
        logo=args.logo,
        trailer=args.trailer,
        out_dir=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
