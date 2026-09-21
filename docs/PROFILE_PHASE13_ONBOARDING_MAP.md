# Phase 13 - Onboarding state mapper

Current Phase 12 runtime state:

- the game's native Campaign profile object is accepted locally;
- obsolete profile-sync loading sites are bypassed;
- logical connectivity remains offline;
- known NO_INTERNET popups are bypassed;
- startup reaches the age/gender screen;
- pressing ACEITAR does not advance.

## Goal

Find the internal state that represents an already configured Campaign user:

- age stored;
- gender stored;
- privacy/terms/EULA accepted;
- first run complete;
- profile initialized;
- onboarding completed.

The final Phase 13 patch should preset that state and bypass the obsolete onboarding flow semantically. It must not merely hide UI.

## Mapper

The file tools/profile_phase13_onboarding_map.ps1 is read-only.

It only analyzes an AMS.exe whose SHA-256 matches the verified Phase 5 hash:

56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3

It maps:

1. onboarding/profile vocabulary in AMS.exe;
2. direct RVA/VA xrefs;
3. nearby conditional branches/calls;
4. the known native-profile constructor window around 0x0069B7A0;
5. the known startup/profile state-machine window around 0x0092B82A;
6. targeted age/gender/consent text hits in package resources.

Output:

_PACKAGE_PHASE5\PROFILE-PHASE13-ONBOARDING-MAP.zip

No game binary, resource, LocalState file, package registration, or save data is changed.

## Run

Use RUN-PROFILE-PHASE13-ONBOARDING-MAP.cmd.

GET-PHASE13-ONBOARDING-MAP.cmd can bootstrap the two required mapper files into an existing project tree.

## Guardrail

Do not commit a Phase 13 binary patch until a concrete success-state branch or field is identified. Unknown onboarding offsets must not be guessed.
