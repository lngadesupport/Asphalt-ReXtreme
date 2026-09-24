# Campaign Profile Adapter v1

Campaign Profile Adapter v1 retires the legacy remote/cloud profile authority
while preserving the original local profile object and completion observers.

## Startup policy

- global `IsOnline` remains FALSE;
- the native/default profile object is accepted locally;
- all three known `STR_MENU_SYNC_LOADING` construction paths are bypassed;
- the runtime pending sync flag is consumed locally;
- GlobalSync submit completes through the game's existing completion callback
  with result code `0`;
- no network transport is started;
- the obsolete sync/network popup wrapper is reduced to a local no-op.

## Profile flow

```text
startup
  -> native profile object
  -> Campaign Profile Adapter
  -> local validation
  -> local GlobalSync completion SUCCESS=0
  -> original completion observers
  -> profile READY
```

The adapter does not report fake internet availability and does not restore any
retired backend endpoint.

## Known separation

This adapter is independent from Campaign Garage ownership routing. Startup
profile synchronization and Garage ownership must be debugged separately.
