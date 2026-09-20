import json
import struct
import zipfile
from pathlib import Path

from tools.audit_offline_data import audit
from tools.xtea_assets import fold_key


def _encrypt_block(block: bytes, key) -> bytes:
    v0, v1 = struct.unpack("<2I", block)
    total = 0
    delta = 0x9E3779B9
    for _ in range(32):
        v0 = (v0 + ((((v1 << 4) & 0xffffffff ^ (v1 >> 5)) + v1) ^
                    ((total + key[total & 3]) & 0xffffffff))) & 0xffffffff
        total = (total + delta) & 0xffffffff
        v1 = (v1 + ((((v0 << 4) & 0xffffffff ^ (v0 >> 5)) + v0) ^
                    ((total + key[(total >> 11) & 3]) & 0xffffffff))) & 0xffffffff
    return struct.pack("<2I", v0, v1)


def _type1(payload: bytes) -> bytes:
    import zlib
    body = struct.pack("<II", len(payload), zlib.crc32(payload) & 0xffffffff) + payload
    body += b"\x00" * ((8 - (len(body) % 8)) % 8)
    key = fold_key()
    encrypted = b"".join(
        _encrypt_block(body[i:i+8], key)
        for i in range(0, len(body), 8)
    )
    return b"\x01\x00" + encrypted


def test_audit_finds_offline_categories(tmp_path: Path):
    xml_bin = tmp_path / "xml.bin"
    payload = (
        b'<Root Energy="10" Maintenance="20" Fuse="3" '
        b'Url="https://example.gameloft.invalid" '
        b'Name="credits_full_sync" />'
    )

    with zipfile.ZipFile(xml_bin, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("xml/test.xtea", _type1(payload))

    report = audit(xml_bin)

    assert report["decoded_xtea_entries"] == 1
    assert report["candidate_entries"] == 1
    categories = report["entries"][0]["categories"]
    assert categories["energy"] >= 1
    assert categories["maintenance"] >= 1
    assert categories["fuses"] >= 1
    assert categories["sync"] >= 1
    assert categories["online"] >= 1
