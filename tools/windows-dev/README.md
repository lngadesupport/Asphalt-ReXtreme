# Campaign development bootstrap

This folder is for **local Windows testing**, not final distribution.

## Fast path

Run `CampaignDevBootstrap.cmd`.

It:
1. checks the extracted Campaign folder;
2. installs the bundled `Microsoft.VCLibs.120.00` x86 dependency only if needed;
3. registers the loose `AppxManifest.xml` using the local Windows Package Manager;
4. launches `A278AB0D.AsphaltXtreme!App`;
5. captures immediate AppModel/TWinUI diagnostics.

This does **not** use the Microsoft Store or require a Microsoft account.

If Windows refuses loose development registration, enable **Developer Mode** in Windows Settings, then rerun.

## Cleanup

Run `Unregister-CampaignDev.ps1`.

The script removes only a registration whose `InstallLocation` matches this Campaign folder. It deliberately does not remove VCLibs because another application may use that framework.

## Important

The final Campaign Edition target remains package-independent. Loose registration is an intermediate compatibility harness because this 1.7.3.10 build uses `Windows.UI.Xaml.Application` and `ms-appx:///DirectXPage.xaml`.
