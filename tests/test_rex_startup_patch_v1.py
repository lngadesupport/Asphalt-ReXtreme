import unittest

from builder.rex_startup_patch_v1 import StartupPatchError, patch_bytes


PATCHES = (
    (0x0069B8C6, bytes.fromhex("74 24"), bytes.fromhex("74 22")),
    (0x0069B8E6, bytes.fromhex("32 C0"), bytes.fromhex("B0 01")),
    (
        0x00685F9C,
        bytes.fromhex("0F 84 DF 00 00 00"),
        bytes.fromhex("E9 E0 00 00 00 90"),
    ),
    (
        0x006CF957,
        bytes.fromhex("8D 45 E0 0F 57 C0 50 66 0F"),
        bytes.fromhex("C6 47 4C 00 E9 43 01 00 00"),
    ),
    (
        0x0092B82A,
        bytes.fromhex("0F 84 8D 01 00 00"),
        bytes.fromhex("E9 8E 01 00 00 90"),
    ),
    (
        0x006A1CE1,
        bytes.fromhex("0F 85 FE 00 00 00"),
        bytes.fromhex("E9 FF 00 00 00 90"),
    ),
    (
        0x006A1E03,
        bytes.fromhex("0F 85 D8 00 00 00"),
        bytes.fromhex("E9 D9 00 00 00 90"),
    ),
)

GUARDS = (
    (0x00BACDD0, bytes.fromhex("31 C0 C3 90 90 90 90")),
    (0x009168B0, bytes.fromhex("31 C0 C2 18 00")),
)


def fixture():
    size = max(
        max(offset + len(before) for offset, before, _ in PATCHES),
        max(offset + len(expected) for offset, expected in GUARDS),
    ) + 32
    data = bytearray(size)
    for offset, before, _ in PATCHES:
        data[offset : offset + len(before)] = before
    for offset, expected in GUARDS:
        data[offset : offset + len(expected)] = expected
    return data


class RexStartupPatchV1Tests(unittest.TestCase):
    def test_rewrites_only_local_startup_profile_transitions(self):
        source = fixture()
        patched = patch_bytes(bytes(source))

        self.assertEqual(len(patched), len(source))
        for offset, before, after in PATCHES:
            self.assertEqual(patched[offset : offset + len(after)], after)
            self.assertNotEqual(before, after)

        for offset, expected in GUARDS:
            self.assertEqual(
                patched[offset : offset + len(expected)],
                expected,
            )

    def test_rejects_unknown_startup_site(self):
        source = fixture()
        offset, before, _ = PATCHES[2]
        source[offset : offset + len(before)] = b"\xCC" * len(before)

        with self.assertRaises(StartupPatchError):
            patch_bytes(bytes(source))


if __name__ == "__main__":
    unittest.main()
