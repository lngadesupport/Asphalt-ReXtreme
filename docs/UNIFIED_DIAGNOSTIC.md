# Unified Diagnostic

This replaces the separate Deep Scanner and Crash Probe workflow.

Put `UNIFIED_DIAGNOSTIC.cmd` and the `tools` folder in the Campaign Edition
game root, then run:

```text
UNIFIED_DIAGNOSTIC.cmd
```

One pass collects:
- hashes of the critical runtime/data files;
- PE imports/exports for AMS/WCP/IAP/IGP and relevant service DLLs;
- AppContainer state;
- Store/package/XAML/WinRT/ad/IAP references;
- Windows/GPU/runtime state;
- stale Asphalt package registration state;
- modules loaded by AMS.exe;
- AMS.exe exit code;
- a WER minidump when Windows produces one;
- Application/AppModel/TWinUI events around the failure.

It writes one final ZIP under `_campaign_unified_diagnostic`.

The diagnostic does not modify game files or register/install APPX.
