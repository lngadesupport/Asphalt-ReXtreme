# XTEA asset format — Asphalt Xtreme 1.7.3.8 x86

The data inside `data/xml.bin` is a ZIP archive containing `.xtea` entries.
The format and cipher were verified against the target `AMS.exe`.

## Container

Each `.xtea` file is:

1. unencrypted `uint16 LE` type (observed value: `1`);
2. XTEA-encrypted data in 8-byte blocks.

After decryption:

1. `uint32 LE` plaintext body length;
2. `uint32 LE` CRC32 of the body;
3. body bytes (XML/JSON/etc.);
4. zero padding.

The original writer always emits between 1 and 8 padding bytes. If the
header+body is already 8-byte aligned, it emits a full 8-byte zero block.

## Cipher

The client uses standard XTEA, 32 rounds, little-endian DWORDs.

The 16-byte key is derived by zero-initializing 16 bytes and XORing byte `i`
of the source string into `key[i & 15]`.

Verified derived key for this build:

`3c5a79762a6c39732266666b203f3864`

## Verification

Round-trip tests against the original files are byte-for-byte identical for:

- `asphaltdb.xtea`;
- `asphaltserverdb.xtea`;
- `asphaltshop.xtea`;
- `career_data.xtea`;
- tutorial assets including an input whose plaintext+header is block-aligned.

This means ReXtreme can modify data assets while preserving the exact original
container format and CRC behavior.

Use `tools/rextreme_xtea.py` to decrypt, verify and rebuild these assets.
