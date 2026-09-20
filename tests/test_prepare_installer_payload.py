import hashlib
import json
from pathlib import Path

from tools.prepare_installer_payload import assemble


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_assemble_private_installer_payload(tmp_path: Path):
    setup = tmp_path / "setup.exe"
    appx = tmp_path / "game.appx"
    cert = tmp_path / "publisher.cer"
    dep = tmp_path / "vc120.appx"
    logo = tmp_path / "logo-source.png"
    trailer = tmp_path / "trailer-source.mp4"

    setup.write_bytes(b"setup")
    appx.write_bytes(b"appx")
    cert.write_bytes(b"cert")
    dep.write_bytes(b"vc120")
    logo.write_bytes(b"logo")
    trailer.write_bytes(b"trailer")

    out = assemble(
        installer_exe=setup,
        appx=appx,
        certificate=cert,
        dependency=dep,
        logo=logo,
        trailer=trailer,
        out_dir=tmp_path / "out",
    )

    assert (out / "Asphalt-ReXtreme-Setup.exe").read_bytes() == b"setup"
    assert (out / "assets" / "logo.png").read_bytes() == b"logo"
    assert (out / "assets" / "trailer-vertical.mp4").read_bytes() == b"trailer"

    manifest = json.loads((out / "payload" / "install-manifest.json").read_text())
    assert manifest["package"] == "Asphalt-ReXtreme-1.0.0.0-x86.appx"
    assert manifest["packageSha256"] == _sha(b"appx")
    assert manifest["certificateSha256"] == _sha(b"cert")
    assert manifest["dependencySha256"] == _sha(b"vc120")
    assert manifest["setupSha256"] == _sha(b"setup")
