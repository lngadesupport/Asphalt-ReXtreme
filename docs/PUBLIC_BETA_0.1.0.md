# Asphalt ReXtreme: Campaign Edition — Public Beta 0.1.0-beta.1

This branch is the frozen public-beta track derived from Campaign commit
`ecd82c36505a2ba5010caaf98d04493e9f63230b`.

## Scope

The beta is intended to validate the complete user loop:

`garage -> career -> race -> result -> reward -> save -> relaunch`.

Campaign economy, local progression, garage ownership/build flow, Career Adapter
v3, local upgrades/Pro Kits and the local Campaign store are in scope.

Replay, Photo Mode and any UI path that still lacks a verified original binding
are not release blockers and should remain fail-closed.

## Distribution

The repository does not redistribute original Asphalt Xtreme executables,
assets, APPX packages or other proprietary files. A tester provides a compatible
Windows 1.7.3.8 x86 source locally.

Normal beta users do not need Git or a system-wide Python installation.
`INSTALL-BETA.cmd` imports the clean source, builds the verified Phase 2/Phase 5
layout, downloads the official CPython 3.12.10 32-bit embeddable runtime from
python.org, and runs the current Campaign finalizer.

## Temporary startup model

Beta 0.1 uses a **UWP loose-layout compatibility startup**. This is temporary.

It still requires Windows Developer Mode and package registration because direct
portable Win32 startup has not yet passed runtime validation. The beta manifest
therefore deliberately keeps:

- `portable_startup_ready = false`
- `startup_mode = uwp-loose-compatibility`

Do not relabel this beta as 1.0 until the portable-startup release gate passes.

## Safety around the original installation

The compatibility beta temporarily reuses the original package identity. The
installer refuses to automatically remove a conflicting Asphalt Xtreme package
registered from another location. This protects an existing installation and
its LocalState from accidental deletion.

Use a clean Windows test profile/machine, or explicitly remove/back up the old
package yourself before installing the beta.

## Entry points

- `INSTALL-BETA.cmd [source-folder]`
- `PLAY-BETA.cmd`
- `UPDATE-BETA.cmd`
- `REPAIR-BETA.cmd`

If no source folder is passed to INSTALL, the script asks for it.

## Public beta release gate

Before publishing the first downloadable beta, perform this on a clean Windows
10/11 profile:

1. Install from a clean compatible source.
2. Create a fresh profile/save.
3. Open Garage and select/build a vehicle.
4. Enter Career and start a race.
5. Finish the race and receive the Campaign reward.
6. Return to Career/Garage.
7. Close the game.
8. Relaunch with PLAY-BETA.cmd.
9. Confirm progression and currency persisted.
10. Run REPAIR-BETA.cmd and confirm the same save still loads.
11. Run UPDATE-BETA.cmd and confirm it does not modify LocalState.

After that smoke test passes, `0.1.0-beta.1` can be published as the first
public beta without waiting for Replay, Photo Mode, or portable Win32 startup.
