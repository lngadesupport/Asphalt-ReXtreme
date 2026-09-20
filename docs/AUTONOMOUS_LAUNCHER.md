# Autonomous launcher

Starting with **Offline Alpha 0.6**, the intended user entry point is only:

`AsphaltReXtreme.exe`

## Responsibilities

The launcher must:
- verify the supported Asphalt Xtreme 1.7.3.8 x86 source build;
- back up original files before patching;
- apply the current Offline/Premium payload;
- create the local ReXtreme configuration;
- verify `Microsoft.VCLibs.120.00` x86;
- acquire the official Microsoft VC120 redistributable automatically when it is absent;
- install the dependency silently for the current Windows user;
- register the extracted APPX package automatically;
- launch the correct AppUserModelID;
- keep a diagnostic log and repair/restore modes.

Normal users should not need PowerShell, WinGet, manual APPX registration, manual dependency installation, or direct execution of `AMS.exe`.

## VC120 bootstrap

The original game manifest requires:
- framework: `Microsoft.VCLibs.120.00`
- architecture: x86
- minimum version: `12.0.21005.1`

The launcher uses Microsoft's Visual Studio 2013 VCLibs redistributable package. Alpha 0.6 downloads and caches the official redistributable automatically on first run when the framework is not already installed. Subsequent starts reuse the installed framework and can remain offline.

The public repository does not contain Microsoft's binary framework package or proprietary Asphalt Xtreme binaries.

## Branding

Alpha 0.6 and later use the project owner's RX artwork as the embedded Windows executable icon.


## Automatic sideload preparation

Starting with Alpha 0.7, the launcher handles loose-APPX registration policy automatically.

Registration flow:
1. try `Add-AppxPackage -Register ... -DisableDevelopmentMode` first;
2. if Windows requires development/sideload mode, relaunch the ReXtreme launcher through UAC;
3. enable the Microsoft-documented local policy values for trusted/development apps;
4. register the extracted APPX;
5. launch the game.

The launcher configures:
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock\AllowAllTrustedApps=1`
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock\AllowDevelopmentWithoutDevLicense=1`

and matching Appx policy values when administrative access is available.

Normal users still only launch `AsphaltReXtreme.exe`; no PowerShell command is required.


## Alpha 0.8 resilience

Alpha 0.8 changes the bootstrapper architecture to reduce Windows-specific deployment failures:

- launcher is **x64** even though Asphalt Xtreme remains x86, avoiding WOW64 registry/System32 redirection;
- uses the native 64-bit `reg.exe`, `PowerShell`, `gpupdate.exe` and system tools;
- writes and validates both Microsoft AppModelUnlock and Group Policy AppX values in the 64-bit registry view;
- forces a computer-policy refresh before retrying loose-package registration;
- checks that the game is on a local NTFS volume;
- captures AppX deployment ActivityId diagnostics automatically;
- performs a safe registration-repair pass before surfacing an error;
- when Windows reports that newly applied developer/sideload policy requires a reboot, schedules a RunOnce resume and offers a one-time restart;
- continues to validate exact game hashes and preserve backups before patching.

The project does not claim that any Windows application can be guaranteed error-free on every future OS, driver or managed-policy configuration. The launcher contract is instead: detect known prerequisites up front, self-repair known failure modes, preserve user data/backups, and only surface an actionable diagnostic after automated recovery has been exhausted.


## Alpha 0.9 signed-package model

Alpha 0.9 removes loose-file registration from the normal launcher flow.

Previous alphas used `Add-AppxPackage -Register AppxManifest.xml`. Microsoft documents loose-file registration as a development/testing mechanism, not a production distribution model. Alpha 0.9 instead:

1. verifies and patches the supported 1.7.3.8 x86 source;
2. builds a clean staging layout excluding original signature/blockmap metadata and ReXtreme tooling/backups;
3. changes only the package version in staging to `1.7.3.9`;
4. obtains Microsoft's Windows SDK BuildTools when not cached;
5. uses `MakeAppx.exe` to create a normal APPX;
6. creates a local code-signing certificate whose Subject exactly matches the manifest Publisher;
7. trusts that certificate for the current user;
8. signs the APPX with SHA-256 using `SignTool.exe`;
9. verifies the signature;
10. installs the APPX with `Add-AppxPackage -Path` and the VC120 x86 dependency;
11. launches the normal AppUserModelID.

The package family remains compatible with the original manifest because the Publisher string is preserved. The ReXtreme package is distinguishable by version `1.7.3.9`.

The launcher no longer attempts to solve deployment failures by forcing Developer Mode or repeatedly registering a loose Store-origin package.
