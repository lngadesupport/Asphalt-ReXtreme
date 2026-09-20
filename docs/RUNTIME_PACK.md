# Runtime Pack architecture

Starting with Alpha 0.11, ReXtreme development no longer assumes that every bootstrap component must be embedded into one giant executable.

## Layout

```
Asphalt Xtreme/
├── AsphaltReXtreme.exe
├── ReXtreme.ini
├── ReXtreme/
│   ├── Runtime/
│   │   └── payload.zip
│   ├── Identity/
│   │   ├── ReXtremeLocal.cer
│   │   └── ReXtremeLocal.pfx   # private alpha/test material only
│   ├── Tools/
│   ├── Cache/
│   ├── Logs/
│   └── Repair/
├── AMS.exe
├── AppxManifest.xml
└── data/
```

## Why this model

- normal launch can reuse prepared/cache state instead of rebuilding bootstrap infrastructure;
- payload, certificate/identity, repair and diagnostics can be updated independently;
- the launcher can remain focused on orchestration and fast-path launch;
- future portable-host / external-identity experiments can live under `ReXtreme/` without changing the original game directory layout;
- diagnostics and recovery do not require rebuilding the launcher.

## Alpha 0.11 certificate fix

Alpha 0.10 trusted the self-signed alpha certificate only in `CurrentUser\TrustedPeople`. SignTool could still reject the chain because the self-signed root was not trusted.

Alpha 0.11 imports the **public certificate only** into:
- `CurrentUser\Root`;
- `CurrentUser\TrustedPeople`.

The private PFX remains alpha-only material and is not intended for public repository distribution.

## Portable direction

The preferred final user experience remains:

`folder + AsphaltReXtreme.exe -> play`

The original `AMS.exe` is a UWP/windowsApp executable and therefore uses package-identity-gated WinRT behavior. Microsoft external-location/sparse packaging is primarily designed around Win32 `win32App` binaries, so ReXtreme treats sparse identity for AMS as experimental until validated on real Windows.

The Runtime Pack reserves two paths:
1. **Identity mode** — minimal package identity while all large game data stays in the user folder, if the Windows runtime accepts the client model.
2. **Portable Host mode** — ReXtreme-owned Win32 host/shims that replace the package-identity assumptions required by AMS.

A full-package install remains a compatibility fallback during development, not the desired final UX.


## Alpha 0.12 packaging fixes

Alpha 0.12 fixes both failures observed in the Alpha 0.11 compatibility path.

### Sharing violation / MakeAppx 0x80070020

The launcher now:
- terminates `AMS.exe` before staging and packaging;
- waits briefly for file handles to close;
- retries MakeAppx automatically up to four times when the failure is a sharing violation;
- preserves SDK/cache state between retries.

This addresses package creation failures caused by game data files such as `data/textures_win32.bin` being held open by the running game.

### Proper signing chain

The previous alpha used a self-signed leaf code-signing certificate. Importing a `CA:FALSE` leaf into Root does not create a proper certificate authority chain.

Alpha 0.12 uses:
- **ReXtreme Local Root CA** — `CA:TRUE`, keyCertSign/cRLSign;
- **ReXtreme Publisher Signing** — `CA:FALSE`, Digital Signature, Code Signing EKU;
- leaf Subject remains exactly `CN=276B8086-F8CA-495E-A880-D275ED83EA67` to match the package Publisher.

Trust layout:
- Root CA -> `CurrentUser\\Root`;
- signing leaf -> `CurrentUser\\TrustedPublisher` and `CurrentUser\\TrustedPeople`.

The private alpha signing key remains private build material and is not committed to the public repository.

### Final direction

Full APPX packaging remains only a compatibility fallback. The preferred end state remains a portable ReXtreme host that runs from the user folder without copying the large game payload into WindowsApps.
