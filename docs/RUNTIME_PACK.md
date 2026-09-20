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
