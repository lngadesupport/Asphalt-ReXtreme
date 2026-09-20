# RC1 Setup assembly

The 1.0 RC installer is assembled from three independently verifiable parts:

1. the compiled self-contained WPF installer shell;
2. the approved installer visual assets;
3. the signed ReXtreme APPX payload plus VC120 x86.

## Visual assets

`tools/prepare_installer_assets.ps1` consumes the project-owner supplied
Asphalt Xtreme trailer and ReXtreme logo.

The generated trailer is:
- 540x960 (9:16);
- center-cropped;
- approximately 1.06x overscaled before crop;
- 30 fps;
- H.264/yuv420p;
- AAC audio retained so the installer can start muted and allow unmute.

The WPF shell handles fade-in, mute state and looping.

## Full repack payload

`tools/build_rc1.ps1` consumes a legitimate extracted Asphalt Xtreme
`1.7.3.8 x86` source. It creates the independent ReXtreme staging tree,
applies hash-verified patches/data transformations, creates the APPX, signs
it with the ReXtreme RC publisher certificate, verifies the signature, and
writes SHA-256 values to `install-manifest.json`.

The payload is only marked `releaseEligible=true` when:
- the stage metadata itself is release-eligible;
- VC120 x86 is present in the payload.

Diagnostic builds remain install-blocked by the public RC installer.

## Installer shell

The installer project is:

`installer/AsphaltReXtreme.Setup/AsphaltReXtreme.Setup.csproj`

It targets Windows 10 build 19041 or later, is published self-contained for
x64, and uses Windows package deployment APIs for install/update/repair.

## Assembly layout

`tools/assemble_setup.ps1` produces:

    .artifacts/setup-rc1/
      AsphaltReXtreme.Setup.exe
      assets/
        logo.png
        trailer-vertical.mp4
      payload/
        install-manifest.json
        Asphalt-ReXtreme-1.0.0.0-x86.appx
        ReXtreme-Publisher.cer
        Microsoft.VCLibs.120.00_*.appx
      setup-layout.json

RC1 intentionally keeps these pieces visible for diagnostics. The final
single-download wrapper is frozen only after install, offline boot, save,
economy and repair gates pass on real Windows systems.
