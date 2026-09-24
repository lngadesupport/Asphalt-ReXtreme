# Phase 10 — Global Local Profile Sync

Phase 9 proved that the native default profile object can pass the first startup gate.

Phase 10 neutralizes **all three known code sites** that construct `STR_MENU_SYNC_LOADING`:

- file offset `0x00685FD0`
- file offset `0x006CF9E6`
- file offset `0x0092B8BB`

The actual patches are placed at the controlling branches/state transitions around those sites.

## Goal

Treat remote/cloud profile synchronization as a local no-op while preserving gameplay-side profile mutations.

This is intended to cover:

- startup / consent flow;
- race completion;
- vehicle upgrades;
- box opening/purchases;
- shop/inventory changes;
- other actions that currently trigger the same online-profile loading UI.

## Runtime sync manager

The function near file offset `0x006CF7F0` is a generic profile-sync state machine. It consumes pending profile flags and, when state `+0x50 == 1` and pending byte `+0x4C != 0`, opens `STR_MENU_SYNC_LOADING` and calls the legacy remote backend.

Phase 10 consumes `+0x4C` locally and jumps directly to cleanup, skipping the remote loading UI/backend call.

## Rollback

`RESTORE-PROFILE-PHASE10.cmd` restores the verified Phase 5 AMS backup.
