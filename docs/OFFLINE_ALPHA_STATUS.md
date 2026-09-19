# Offline Alpha status

## Verified executable patch

For the exact 1.7.3.8 x86 `AMS.exe` (SHA-256 `3d48800d...`), the central connectivity getter at file offset `0xBACDD0` is:

```
8A 81 B0 04 00 00 C3
```

The Offline Alpha replacement is:

```
31 C0 C3 90 90 90 90
```

This returns false unconditionally and is now recorded in the hash-guarded patch manifest.

## Premium v3 data baseline

Validated locally against the original `xml.bin`:

- 61 active cars affected;
- all 92 positive `CAR_PRICE` entries are 80% of original, preserving credits vs hardcurrency;
- energy refill direct price = 0;
- energy refill base price = 0;
- maintenance timer multiplier = 0;
- maintenance price multiplier = 0;
- fuse refill price = 0;
- rebuilt `xml.bin` keeps the exact original size and all 60 `xml.bin.hdr` offsets.

## Real-money storefront data

The Windows CurrentApp simulation/listing XML contains 432 product entries. The offline data transformer removes those Product nodes while retaining a valid CurrentApp/App structure.

Windows8 Facebook/MSN entries in `snsconfig.json` are also disabled in the generated offline copy.

## Premium-currency rule

The approved design remains:

`hardcurrency earned per completed race = floor(repeatable credit payout × 0.50)`

A progression simulation using this rule plus 20%-discounted car prices shows **0 extra replay races required for all 33 first mandatory exact-car gates** under an ideal first-place/three-star career path.

The runtime hook that grants this hardcurrency every race is still under binary analysis and is not yet marked verified.
