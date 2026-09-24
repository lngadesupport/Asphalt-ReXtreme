# Direct-launch laboratory findings

## Loader failure reproduced from Windows test

Direct execution of the Campaign build initially failed with:

- missing `vccorlib120_app.dll`;
- missing `msvcp120_app.dll`;
- `WCPToolkit.dll` reported as a bad image / NTSTATUS `0xC0000020`;
- after adding the VC++ App runtime, `InAppPurchaseComponentW8.dll` also reported `0xC0000020`.

## Root cause identified statically

The runtime tree contains exactly three primary PE images with
`IMAGE_DLLCHARACTERISTICS_APPCONTAINER` set:

| File | Original flags |
|---|---|
| `AMS.exe` | `0x9140` |
| `WCPToolkit.dll` | `0x1140` |
| `InAppPurchaseComponentW8.dll` | `0x1140` |

The direct-launch v2 experiment cleared the flag only on `AMS.exe`. Windows
then reached the dependent DLLs and rejected them in the non-AppContainer
process.

## Direct-launch lab v3

The v3 experiment clears AppContainer on all three:

- `AMS.exe`: `0x9140 -> 0x8140`;
- `WCPToolkit.dll`: `0x1140 -> 0x0140`;
- `InAppPurchaseComponentW8.dll`: `0x1140 -> 0x0140`.

The v3 WCPToolkit laboratory binary also replaces:

- `GetAppInstalledFolderPath()` with a local-current-directory path;
- `GetAppLocalFolderPath()` with a local-current-directory path.

The Microsoft VC++ 2013 App x86 runtime is supplied locally beside the
executable for the direct-launch experiment:

- `vccorlib120_app.dll`;
- `msvcp120_app.dll`;
- `msvcr120_app.dll`;
- `vcamp120_app.dll`;
- `vcomp120_app.dll`.

## Interpretation

If v3 passes the PE loader, the next likely blocker is no longer basic
AppContainer image loading. The remaining architectural risk is the WinRT/XAML
activation path, including `Windows.UI.Xaml.Application`,
`AMS.DirectXPage` and `ms-appx:///DirectXPage.xaml`.

This remains a laboratory path. Campaign Edition is not declared fully
unpackaged until startup, race entry, saving and restart persistence are tested
on Windows.
