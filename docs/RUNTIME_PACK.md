# Campaign Runtime Pack

The final Campaign Edition runtime is portable and desktop-oriented.

## Target layout

```text
Asphalt ReXtreme Campaign Edition/
├── AsphaltReXtreme.exe
├── GameData/
├── config/
├── save/
├── logs/
└── runtime/
```

## Runtime contract

The normal launch path must not:
- register or install APPX/MSIX;
- depend on AppUserModelID activation;
- require Microsoft Store;
- require Microsoft/Xbox sign-in;
- query Store licensing;
- install package certificates;
- change Developer Mode or sideload policy;
- copy the game into WindowsApps.

Internet may remain enabled. The user may remain signed into Microsoft Store.
Those conditions must not change Campaign behavior.

## Source-build compatibility

The original 1.7.3.8 x86 source is a Microsoft Store/UWP-style package and uses
package/WinRT facilities. Campaign conversion therefore separates:
- generic Windows runtime helpers that remain useful;
- package-identity APIs that must be replaced;
- Store/IAP/authentication code that must be bypassed or removed;
- obsolete Gameloft service code that must be replaced with local behavior.

`tools/campaign_static_audit.ps1` and `tools/store_dependency_audit.py` are the
static discovery tools for this work.

## Portable host direction

If `AMS.exe` cannot be made directly desktop-launchable without package
identity, the supported final route is a ReXtreme-owned Win32 host/shim layer.
That host may provide local path/save/window/bootstrap behavior required by the
engine, but it must not recreate Store licensing or silently register an APPX.

## Saves

Campaign Edition owns its own local save directory and must use recoverable,
atomic writes. Save paths may be relative to the portable directory or to a
Campaign-owned desktop application data path, but never require the original
Store package family.

## No compatibility fallback in release

Historical APPX signing/registration experiments remain available in Git
history only. They are not a supported Campaign Edition release fallback.
