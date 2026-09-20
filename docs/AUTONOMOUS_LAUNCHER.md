# Autonomous launcher — historical APPX approach

> **Superseded for Campaign Edition.**
>
> The APPX/MSIX registration, signing, certificate, AppUserModelID and
> Add-AppxPackage approaches documented below are retained only as development
> history. They are **not** part of the Campaign Edition runtime or release
> path. See `CAMPAIGN_EDITION_ARCHITECTURE.md`.

Campaign Edition must launch as a portable desktop/Win32 game and must not
require Microsoft Store, APPX registration, Microsoft/Xbox authentication,
Developer Mode, sideload policy or package certificates.

---

# Historical notes

Starting with **Offline Alpha 0.6**, the intended user entry point was only:

`AsphaltReXtreme.exe`

Earlier alpha launchers wrapped the original Microsoft Store APPX deployment.
That approach is retired because it keeps Windows package identity and Store
deployment in the runtime path, which conflicts with the Campaign Edition
requirement to avoid Microsoft Store coupling completely.

For historical implementation details, inspect this file's Git history.
