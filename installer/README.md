# Asphalt ReXtreme Setup

Custom WPF bootstrapper for the 1.0 RC.

## Runtime layout

The assembled private installer directory is:

```
Asphalt-ReXtreme-Setup.exe
assets/
  logo.png
  trailer-vertical.mp4
payload/
  install-manifest.json
  Asphalt-ReXtreme-1.0.0.0-x86.appx
  ReXtreme-Publisher.cer
  Microsoft.VCLibs.120.00_*.appx
```

The public repository intentionally does not include proprietary game media or
game payloads.

## UI contract

- the official logo occupies the former title position;
- the logo fades in with eased motion;
- the trailer uses a vertical panel with `UniformToFill` and a 1.06x visual zoom;
- the trailer fades in, starts muted and loops continuously;
- status/action panels use eased transitions;
- progress is driven by Windows package deployment progress, not a fake timer;
- an existing install exposes **JOGAR AGORA** and **REPARAR**.

## Installation / repair contract

The installer runs elevated and:

1. verifies SHA-256 for the APPX, publisher certificate and VC120 payload;
2. trusts the ReXtreme signing certificate in `LocalMachine/TrustedPeople`;
3. deploys with `Windows.Management.Deployment.PackageManager`;
4. applies local dependency package URIs;
5. allows same/older-version repair through `ForceUpdateFromAnyVersion`;
6. verifies that `ReXtreme.AsphaltXtreme` exists after deployment;
7. enables launch only after successful verification.

No visible PowerShell window is used by the WPF installer.

## RC1 private build flow

Build the transformed package from a legitimate extracted 1.7.3.8 x86 source:

```powershell
tools\build_rc1.ps1 -Source "D:\Source\Asphalt Xtreme" -VCLibsPath "D:\Deps\Microsoft.VCLibs.120.00_x86.appx"
```

Publish the installer shell:

```powershell
dotnet publish installer\AsphaltReXtreme.Setup\AsphaltReXtreme.Setup.csproj -c Release -r win-x64 --self-contained true -o .artifacts\installer
```

Then assemble the private test folder using locally supplied media:

```powershell
python tools\prepare_installer_payload.py ^
  --installer-exe .artifacts\installer\AsphaltReXtreme.Setup.exe ^
  --appx .artifacts\1.0-rc1\installer-payload\Asphalt-ReXtreme-1.0.0.0-x86.appx ^
  --certificate .artifacts\1.0-rc1\installer-payload\ReXtreme-Publisher.cer ^
  --dependency "D:\Deps\Microsoft.VCLibs.120.00_x86.appx" ^
  --logo "D:\PrivateAssets\logo.png" ^
  --trailer "D:\PrivateAssets\trailer-vertical.mp4" ^
  --out .artifacts\Asphalt-ReXtreme-1.0-RC1
```

The assembler writes the final `install-manifest.json` with immutable SHA-256
values for the deployable payload.

## Release rule

RC1 remains a candidate until it passes a clean-machine install, first boot
without network, fresh-save progression, repair, restart/save persistence and
career/economy gates. Only after those gates pass is the package eligible for
the `v1.0.0` tag.
