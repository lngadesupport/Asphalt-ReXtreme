# Asphalt ReXtreme 1.0 RC1 test plan

RC1 is not promoted to `v1.0.0` until every mandatory section passes on a
fresh Windows profile.

## A. Build gate

Run the full repack from a clean supported 1.7.3.8 x86 source.

Expected:
- source binary hashes match the supported manifest;
- binary patches reproduce their expected post-patch hashes;
- Premium/offline plaintext overrides are inserted into `xml.bin`;
- `xml.bin` remains byte-size/HDR compatible;
- package identity is `ReXtreme.AsphaltXtreme`;
- publisher is `CN=ReXtreme`;
- Internet/private-network/location capabilities are absent;
- VC120 x86 is present in the installer payload;
- `tools/check_release_gate.py` returns PASS.

A build that lacks private XML overrides may be useful diagnostically but is
not a release candidate.

## B. Installer gate

On a clean Windows 10/11 user profile:

1. Start Setup.
2. Confirm the approved logo fades into the former title position.
3. Confirm the trailer fills the vertical panel with the approved slight zoom.
4. Confirm trailer starts muted and loops.
5. Toggle audio twice.
6. Start installation.
7. Confirm UI remains responsive and progress is smooth.
8. Confirm no console/PowerShell window appears.
9. Confirm package installation completes.
10. Press **JOGAR AGORA**.

Expected:
- one UAC elevation at Setup start;
- ReXtreme signing certificate trusted in TrustedPeople;
- VC120 x86 installed as package dependency;
- ReXtreme package installed with independent identity;
- game starts without reopening Setup.

## C. Offline boot gate

Disable network before launching.

Expected:
- game reaches main menu;
- garage opens;
- career opens;
- first event starts and completes;
- returning from a race does not wait for Gameloft services;
- no login, ad, purchase, IGP or browser requirement.

## D. Save gate

From a fresh profile:
1. complete at least three events;
2. buy/upgrade at least one vehicle;
3. close the game normally;
4. restart Windows;
5. relaunch offline.

Expected:
- progress, balances, owned vehicles and settings survive;
- no remote sync is required.

## E. Premium economy gate

Use a fresh save and record both wallets after each mandatory-car gate.

Rules to verify:
- positive vehicle prices are exactly 80% of their original values;
- credit cars spend credits;
- original hardcurrency-only cars spend locally earnable Premium currency;
- every completed race grants
  `floor((money_for_playing + finishing-position reward) × 0.50)`
  Premium currency;
- repeating the same event does not diminish either repeatable payout;
- no daily cap or cooldown stops normal farming;
- every mandatory car is obtainable before its first gate.

The simulator is advisory. Runtime values win if the game exposes a different
reward path than static data suggested.

## F. Career completion gate

A fresh Premium save must be able to complete the 300-event main career without:
- real-money purchases;
- ads;
- login;
- live server responses;
- energy/fuel waiting;
- impossible mandatory-car requirements.

Record any point that requires excessive replaying even if technically
possible. The 1.0 goal is paid-game pacing, not merely mathematical
completability.

## G. Repair/reinstall gate

Before 1.0 final:
- installer detects an already-installed ReXtreme package;
- repair verifies hashes and restores damaged package content;
- update does not reuse the original Store identity;
- uninstall behavior for local saves is explicit and tested.

## Promotion rule

Only after A-F pass is the build eligible to become `v1.0.0`.
Section G must also pass before the public one-click Setup is declared final.
