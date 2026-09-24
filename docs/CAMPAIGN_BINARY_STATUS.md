# Campaign binary status — 1.7.3.8 x86

This file distinguishes **verified byte-level work** from the remaining
Microsoft Store/UWP decoupling work.

## Exact supported AMS.exe

```text
SHA-256
3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8
```

Unknown hashes are not patched.

## Verified core patches

The current manifest contains seven verified patches:

1. central connectivity getter forced offline;
2. premium-currency reward trampoline;
3. race payout hook 1;
4. race payout hook 2;
5. race payout hook 3;
6. race payout hook 4;
7. race payout hook 5.

Applying all seven to the exact supported AMS.exe is expected to produce:

```text
e036d16f56ccf7276973322b7494e791ef99c957211700542ab9980860e85043
```

The patcher verifies this final SHA-256 before accepting the write.

## What these patches do not prove

These core patches do **not** by themselves make the build a portable Win32
Campaign Edition. In particular they do not yet prove removal/replacement of:

- APPX package identity;
- AppUserModelID activation;
- Microsoft Store licensing APIs;
- Store IAP activation;
- Microsoft/Xbox authentication;
- package-family-dependent save paths;
- UWP activation/bootstrap requirements.

Therefore:

```text
campaign_ready = false
microsoft_decoupling_ready = false
```

until those call sites are statically identified and validated on the exact
source build.

## Known service components

Relevant files already identified in the supported build include:

- `InAppPurchaseComponentW8.dll`;
- `Microsoft.Live.dll`;
- `IGPLib_x86.dll`;
- `WCPToolkit.dll`;
- `Facebook.dll`.

`WCPToolkit.dll` is mixed-purpose and must not be blindly deleted because it
also exposes local storage, input, display and system functionality.

## Campaign decoupling acceptance gate

The Microsoft-decoupling stage is complete only after the exact build passes all
of these checks:

1. direct executable startup does not require APPX registration;
2. no Store license query is required;
3. no Microsoft/Xbox sign-in is required;
4. package-family save paths are replaced by Campaign-owned local paths;
5. Store/IAP components are not required for campaign progression;
6. internet can remain enabled without re-enabling legacy service behavior;
7. Microsoft Store can remain signed in without affecting startup;
8. local campaign save/load survives restart;
9. the static audit contains no unresolved package/store/auth blockers.

## Safety property

No patch offset is guessed. New byte patches are added only when:
- the original binary SHA-256 matches;
- the exact original bytes at the offset match;
- the transformed binary is re-hashed;
- a known expected result hash or equivalent structural verification is recorded.
