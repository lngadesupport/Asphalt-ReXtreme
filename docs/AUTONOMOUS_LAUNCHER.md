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
