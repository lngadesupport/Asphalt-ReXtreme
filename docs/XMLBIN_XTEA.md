# xml.bin / XTEA technical notes — build 1.7.3.8 x86

## Container structure

`data/xml.bin` is a ZIP archive with **60 stored entries** (method 0). Most payloads are `xml/*.xtea`.

`data/xml.bin.hdr` contains:
1. `uint32` entry count;
2. for each entry: `uint32 name_length`, UTF-8 filename, `uint64 data_offset`, `uint32 compressed_size`, `uint32 uncompressed_size`, `uint16 method`.

The offsets in the header point to the actual stored data inside the ZIP local-file records.

## Encrypted stream

Static analysis of the verified `AMS.exe` (SHA-256 `3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8`) identified:

- `0x505C20` — XTEA encrypt primitive;
- `0x505CA0` — XTEA decrypt primitive;
- `0x505D20` — 16-byte key derivation/folding helper;
- `0x505E20` — buffer decrypt path;
- loader path around `0x50E866` — stream-type dispatch.

The decrypt primitive uses 32 XTEA rounds and the standard delta relationship (`0x9E3779B9` / `0x61C88647`).

### Stream types

The loader reads a little-endian 16-bit type:

- **type 0**: payload is forwarded without XTEA decryption;
- **type 1**: encrypted path; XTEA decrypt followed by internal length/checksum validation.

All 59 encrypted data entries in the original build use type 1.

## ReXtreme editing strategy

For data files we modify, ReXtreme can use **type 0 plaintext** instead of re-encrypting:

```
00 00 + plaintext XML/JSON + ASCII whitespace padding
```

XML and JSON accept trailing whitespace. If the replacement is padded to exactly the original `.xtea` entry size, rebuilding `xml.bin` with the original order and ZIP metadata preserves every data offset and size in `xml.bin.hdr`.

A local validation test converted `first_rankup_tutorial.xtea` to type 0, rebuilt the container, and verified:
- 60/60 header entries retained the same data offsets;
- compressed/uncompressed sizes remained identical;
- total `xml.bin` size remained identical;
- original `xml.bin.hdr` remained compatible.

`tools/repack_xmlbin.py` implements this layout-preserving strategy and refuses output that no longer matches the original header.

## Economy data

Important decrypted entries:
- `career_data.xtea` → JSON despite the historical .xml naming in extraction;
- `asphaltshop.xtea` → XML shop/IAP configuration;
- `asphaltdb.xtea`;
- `asphaltserverdb.xtea`.

Main-career event fields include `money_for_playing`, `position_1/2/3`, star rewards, completion rewards, rank and car filters.

Current working interpretation:
- repeatable first-place payout candidate = `money_for_playing + position_1`;
- star rewards are progression/one-time rewards and are kept separate in audits.

This distinction is required by ReXtreme's rule that replaying the same race must never reduce its normal payout.
