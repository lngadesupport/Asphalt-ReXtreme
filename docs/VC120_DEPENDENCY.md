# VC120 dependency policy

Asphalt Xtreme 1.7.3.8 x86 declares the legacy Store framework:

```text
Name: Microsoft.VCLibs.120.00
Minimum version: 12.0.21005.1
Architecture: x86
Publisher ID: 8wekyb3d8bbwe
```

Microsoft support documentation lists the exact x86 APPX as:

```text
Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe.appx
Size: 900,419 bytes
```

Do not silently substitute `Microsoft.VCLibs.120.00.UWPDesktop`; that is a
different framework identity even though it is also a v12 runtime.

## Validator

`tools/resolve_vclibs120.ps1` validates a candidate APPX by opening its
`AppxManifest.xml` and checking package name, minimum version and x86
architecture. It also reports whether the exact framework is already
registered for the current user.

Examples:

```powershell
.\tools\resolve_vclibs120.ps1 -InstalledOnly

.\tools\resolve_vclibs120.ps1 `
  -Candidate "C:\path\Microsoft.VCLibs.120.00_12.0.21005.1_x86__8wekyb3d8bbwe.appx"
```

RC/public Setup only bundles a candidate after this validation passes.
Third-party redistributed copies are not a project dependency.
