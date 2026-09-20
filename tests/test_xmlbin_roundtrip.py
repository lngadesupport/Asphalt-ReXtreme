import struct
import zipfile
from pathlib import Path

from tools import repack_xmlbin
from tools import xtea_assets


def _data_offset(info: zipfile.ZipInfo) -> int:
    return info.header_offset + 30 + len(info.filename.encode("utf-8")) + len(info.extra)


def _make_hdr(xml_bin: Path, hdr: Path) -> None:
    rows = []
    with zipfile.ZipFile(xml_bin) as z:
        for info in z.infolist():
            rows.append(
                (
                    info.filename,
                    _data_offset(info),
                    info.compress_size,
                    info.file_size,
                    info.compress_type,
                )
            )

    out = bytearray(struct.pack("<I", len(rows)))
    for name, offset, csize, usize, method in rows:
        raw = name.encode("utf-8")
        out += struct.pack("<I", len(raw))
        out += raw
        out += struct.pack("<QIIH", offset, csize, usize, method)
    hdr.write_bytes(out)


def test_type0_decode_returns_plaintext():
    payload = b"<Root><Value>42</Value></Root>   "
    decoded, meta = xtea_assets.decode_stream(b"\x00\x00" + payload)
    assert decoded == payload
    assert meta["stream_type"] == 0


def test_xmlbin_repack_preserves_hdr_layout(tmp_path: Path):
    xml_bin = tmp_path / "xml.bin"
    hdr = tmp_path / "xml.bin.hdr"
    replacement = tmp_path / "asphaltshop.xml"
    rebuilt = tmp_path / "xml.bin.rebuilt"

    original_payload = b"\x00\x00" + b"<Root/>" + b" " * 120

    info = zipfile.ZipInfo("xml/asphaltshop.xtea")
    info.compress_type = zipfile.ZIP_STORED
    with zipfile.ZipFile(xml_bin, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr(info, original_payload)

    _make_hdr(xml_bin, hdr)

    replacement.write_text(
        '<Root><Car carId="22"><Price Id="CAR_PRICE" Price="26400" Currency="credits" /></Car></Root>',
        encoding="utf-8",
    )

    header = repack_xmlbin.parse_hdr(hdr)
    assert repack_xmlbin.verify(xml_bin, header) == []

    report = repack_xmlbin.rebuild(
        xml_bin,
        rebuilt,
        {"xml/asphaltshop.xtea": replacement},
    )

    assert report["replacements"][0]["stream_type"] == 0
    assert rebuilt.stat().st_size == xml_bin.stat().st_size
    assert repack_xmlbin.verify(rebuilt, header) == []

    with zipfile.ZipFile(rebuilt) as z:
        raw = z.read("xml/asphaltshop.xtea")
    assert raw[:2] == b"\x00\x00"
    assert b"Price=\"26400\"" in raw
