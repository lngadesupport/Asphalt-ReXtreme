# Asphalt ReXtreme Setup

Custom WPF bootstrapper for the 1.0 RC.

## Runtime layout

The published installer executable expects two sibling directories:

```
AsphaltReXtreme.Setup.exe
assets/
  logo.png
  trailer-vertical.mp4
payload/
  install-manifest.json
  Asphalt-ReXtreme-1.0.0.0-x86.appx
  ReXtreme-Publisher.cer
  Microsoft.VCLibs.120.00_*.appx
```

The public repository intentionally does not include proprietary game media or game payloads.

## UI contract

- logo occupies the previous title position;
- logo fades in;
- trailer uses a vertical panel with UniformToFill + 1.06x zoom;
- trailer fades in, starts muted and loops continuously;
- status/action panels fade in with eased animation;
- progress is driven by installer stages, not a fake timer.

## Installation contract

The installer runs elevated, trusts the ReXtreme signing certificate in
LocalMachine/TrustedPeople, installs the signed package with Add-AppxPackage,
passes VC120 through DependencyPath when supplied, then verifies the
independent package identity before enabling JOGAR AGORA.

The final 1.0 outer packer may combine these files into a single downloadable
Setup executable. RC1 keeps them separated so failures can be diagnosed.


## CI

Every push to `release/1.0-rc1` recompiles the self-contained WPF installer on a Windows runner. This is a compile gate only; proprietary payload/media are supplied locally for private RC packaging.
