# Asphalt ReXtreme: Campaign Edition — ReX Runtime

This branch is a clean-room Campaign Edition runtime.

## Architecture rules

- Only `src/campaign-edition` contains active runtime code.
- No legacy Campaign Core, Campaign Runtime V2, patch-phase runtime, backend synchronizer, or old adapter code is present in this branch.
- The game's existing frontend remains presentation/input only and is not redesigned by this runtime.
- Racing gameplay remains outside this runtime and is not modified.
- Proprietary game binaries and assets are not stored here.

## Runtime

```text
RexGaragePresenter
    -> RexGarageViewModel
    -> RexTutorialController
    -> RexCampaign
    -> RexState
    -> RexContent
```

`RexCampaign` owns local garage transactions.
`RexState` owns versioned local persistence with `.bak` recovery.
`RexContent` is the local content authority.

Future integration with the existing presentation layer may only forward input and render state. It may not import old business logic.
